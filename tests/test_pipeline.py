"""Unit tests for the end-to-end Toxic Detection Pipeline."""
import unittest
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from models.pipeline import ToxicPipeline, get_default_pipeline


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.texts = [
            "cảm ơn bạn rất nhiều nhé ❤️",
            "thông tin hữu ích 👍",
            "đồ ngu ngốc cút đi 🤬🖕",
            "mày bị điên à 😡"
        ]
        self.labels = ["non-toxic", "non-toxic", "toxic", "toxic"]

    def test_pipeline_tfidf_svm(self):
        pipe = ToxicPipeline(feature_method='tfidf', model_type='svm')
        pipe.fit(self.texts, self.labels)

        # Preprocess
        pre = pipe.preprocess("chúc bạn ngày mới tốt lành")
        self.assertEqual(len(pre), 1)
        self.assertEqual(pre[0]['icon_toxic_score'], 0.0)

        # Feature extraction
        X = pipe.extract_features(["chúc bạn ngày mới tốt lành", "đồ khốn 🤬"])
        self.assertEqual(X.shape[0], 2)
        feature_names = pipe.get_feature_names()
        self.assertIn('__feature_icon_toxic_score__', feature_names)

        # Predict single text
        pred_single = pipe.predict("cảm ơn bạn")
        self.assertIn(pred_single['label'], ('non-toxic', 'toxic'))
        self.assertIn('feature_vector', pred_single)
        self.assertIn('icon_toxic_score', pred_single)

        # Predict batch
        pred_batch = pipe.predict(["cảm ơn bạn nhiều", "đồ ngu cút 🤬"])
        self.assertEqual(len(pred_batch), 2)
        self.assertEqual(pred_batch[0]['label'], 'non-toxic')
        self.assertEqual(pred_batch[1]['label'], 'toxic')
        self.assertGreater(pred_batch[1]['icon_toxic_score'], 0.5)

    def test_pipeline_bow_naive_bayes(self):
        pipe = ToxicPipeline(feature_method='bow', model_type='naive_bayes')
        pipe.fit(self.texts, self.labels)

        pred = pipe.predict("đồ ngu 🤬")
        self.assertEqual(pred['label'], 'toxic')
        self.assertGreater(pred['icon_toxic_score'], 0.5)


if __name__ == '__main__':
    unittest.main()

