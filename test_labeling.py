"""Offline unit checks; the model smoke check is opt-in and uses synthetic sentences."""
import hashlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dataset import text_hash
from labeling import FILES, MODEL_ID, REVISION, ensure_model, generate_suggestions, suggestion_from_logit, valid_file


class Download(io.BytesIO):
    def geturl(self):
        return 'https://huggingface.co/fixed-model'


class LabelingTests(unittest.TestCase):
    def test_scores_abstain_at_uncertainty_and_truncation(self):
        self.assertEqual(suggestion_from_logit(-4, False)[0], 'non-toxic')
        self.assertEqual(suggestion_from_logit(4, False)[0], 'toxic')
        self.assertEqual(suggestion_from_logit(0, False), ('', 0.5, 'uncertain'))
        self.assertEqual(suggestion_from_logit(4, True)[::2], ('', 'truncated'))
        self.assertEqual(suggestion_from_logit(-1000, False)[1], 0)
        self.assertEqual(suggestion_from_logit(1000, False)[1], 1)
        for value in (float('inf'), float('-inf'), float('nan')):
            with self.assertRaises(ValueError):
                suggestion_from_logit(value, False)

    def test_verified_cache_is_offline_and_bad_download_is_not_installed(self):
        data = b'synthetic model asset'
        spec = {'model.onnx': (len(data), hashlib.sha256(data).hexdigest())}
        with tempfile.TemporaryDirectory() as td, patch('labeling.FILES', spec):
            path = Path(td) / 'model.onnx'
            with patch('labeling.urllib.request.urlopen', return_value=Download(data)) as network:
                ensure_model(td)
                self.assertEqual(path.read_bytes(), data)
                self.assertIn('/resolve/', network.call_args.args[0])
            with patch('labeling.urllib.request.urlopen', side_effect=AssertionError('must remain offline')):
                ensure_model(td)
            path.write_bytes(b'previous corrupt file')
            with patch('labeling.urllib.request.urlopen', return_value=Download(b'x' * len(data))):
                with self.assertRaises(ValueError):
                    ensure_model(td)
            self.assertEqual(path.read_bytes(), b'previous corrupt file')
            self.assertEqual(list(Path(td).glob('*.tmp')), [])

    def test_no_eligible_rows_does_not_load_or_download_model(self):
        rows = [dict(quality='excluded', label=''), dict(quality='ready', label='toxic'),
                dict(quality='duplicate', label=''), dict(quality='ready', label='', text_complete=False)]
        with patch('labeling.ensure_model', side_effect=AssertionError('should not load')):
            self.assertEqual(generate_suggestions(rows, 'unused'), [])

    def test_invalid_rows_rejected_before_network(self):
        with patch('labeling.ensure_model', side_effect=AssertionError('should not load')):
            for rows in ([dict(quality='ready', label='')],
                         [dict(id='1', quality='ready', label='', text_raw='')],
                         [dict(id='1', quality='ready', label='', text_raw='test')] * 2):
                with self.assertRaises(ValueError):
                    generate_suggestions(rows, 'unused')

    def test_batched_inference_keeps_raw_text_and_abstains_on_truncation(self):
        import numpy as np
        from tokenizers import Tokenizer
        from tokenizers.models import WordLevel
        from tokenizers.pre_tokenizers import Whitespace
        from tokenizers.processors import TemplateProcessing

        tokenizer = Tokenizer(WordLevel({'<s>': 0, '<pad>': 1, '</s>': 2, '<unk>': 3, 'Xin': 4, 'chào': 5}, unk_token='<unk>'))
        tokenizer.pre_tokenizer = Whitespace()
        tokenizer.post_processor = TemplateProcessing(single='<s> $A </s>', special_tokens=[('<s>', 0), ('</s>', 2)])
        feeds = []

        def run(names, feed):
            feeds.append(feed)
            return [np.array([[-4.0], [0.0]]) if len(feeds) == 1 else np.array([[4.0]])]

        session = SimpleNamespace(
            get_inputs=lambda: [SimpleNamespace(name=name, type='tensor(int64)', shape=['batch', 'sequence'])
                                for name in ('input_ids', 'attention_mask')],
            get_outputs=lambda: [SimpleNamespace(name='logits', type='tensor(float)')], run=run)
        rows = [dict(id=str(i), text_raw=text, quality='ready', label='') for i, text in enumerate(
            [' Xin\tcha\u0300o! ', 'Xin', 'Xin chào ' * 10])]
        original = [dict(row) for row in rows]
        with tempfile.TemporaryDirectory() as td:
            tokenizer.save(str(Path(td) / 'tokenizer.json'))
            with patch('labeling.ensure_model', return_value=Path(td)), patch('onnxruntime.InferenceSession', return_value=session), \
                    patch('labeling.BATCH_SIZE', 2), patch('labeling.MAX_TOKENS', 5):
                result = generate_suggestions(rows, td)
        self.assertEqual(rows, original)
        self.assertEqual([item['suggested_label'] for item in result], ['non-toxic', '', ''])
        self.assertEqual([item['abstain_reason'] for item in result], ['', 'uncertain', 'truncated'])
        self.assertEqual([item['text_hash'] for item in result], [text_hash(row['text_raw']) for row in rows])
        self.assertTrue(all(item['model'] == MODEL_ID and item['revision'] == REVISION for item in result))
        self.assertEqual([feed['input_ids'].shape for feed in feeds], [(2, 5), (1, 5)])
        self.assertEqual(feeds[0]['input_ids'][0].tolist(), [0, 4, 5, 3, 2])
        self.assertEqual(feeds[0]['attention_mask'][1].tolist(), [1, 1, 1, 0, 0])
        self.assertEqual(feeds[0]['input_ids'].dtype, np.int64)

    @unittest.skipUnless(os.environ.get('LABELING_SMOKE') == '1', 'set LABELING_SMOKE=1 to exercise the verified local model')
    def test_real_local_model_synthetic_smoke_without_network(self):
        directory = Path(__file__).parent / 'models' / 'vietnamese-toxicity'
        self.assertTrue(all(valid_file(directory / name, *spec) for name, spec in FILES.items()), 'download verified model before smoke test')
        texts = ['Cho mình hỏi lịch thi môn lập trình nhé.', 'Mày là đồ ngu, cút đi.', 'Tôi không đồng ý với ý kiến này.'] * 6
        texts += ['xin chào ' * 1000]
        rows = [dict(id=f'synthetic-{i}', text_raw=text, quality='ready', label='') for i, text in enumerate(texts)]
        with patch('labeling.urllib.request.urlopen', side_effect=AssertionError('smoke inference must remain offline')):
            results = generate_suggestions(rows, directory)
        self.assertEqual(len(results), len(rows))
        self.assertEqual([r['id'] for r in results], [r['id'] for r in rows])
        self.assertTrue(all(0 <= r['model_score'] <= 1 for r in results))
        self.assertTrue(all(r['label'] == '' for r in rows))
        self.assertEqual(results[-1]['suggested_label'], '')
        self.assertTrue(results[-1]['truncated'])
        self.assertTrue(all(r['text_hash'] == text_hash(row['text_raw']) for r, row in zip(results, rows)))


if __name__ == '__main__':
    unittest.main()
