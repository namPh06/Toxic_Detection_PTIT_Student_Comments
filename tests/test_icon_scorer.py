"""Unit tests for icon and emoji toxicity scoring."""
import unittest
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from data_processing.icon_scorer import (
    calculate_icon_toxic_score,
    extract_icons,
    TextAndIconTransformer,
    ICON_TOXIC_WEIGHTS
)
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline


class IconScorerTests(unittest.TestCase):
    def test_text_without_icons_scores_zero(self):
        self.assertEqual(calculate_icon_toxic_score("Bài viết chia sẻ rất hay"), 0.0)
        self.assertEqual(calculate_icon_toxic_score(""), 0.0)
        self.assertEqual(calculate_icon_toxic_score(None), 0.0)

    def test_positive_and_wholesome_icons_score_zero(self):
        self.assertEqual(calculate_icon_toxic_score("Cảm ơn bạn nhiều nha ❤️👍"), 0.0)
        self.assertEqual(calculate_icon_toxic_score("Chúc bạn một ngày tốt lành 😊🌸"), 0.0)
        self.assertEqual(calculate_icon_toxic_score("Tuyệt vời quá :) :D"), 0.0)

    def test_toxic_icons_high_scores(self):
        self.assertEqual(calculate_icon_toxic_score("Đồ khốn nạn 🖕"), 1.0)
        self.assertGreaterEqual(calculate_icon_toxic_score("Bực mình vcl 🤬"), 0.9)
        self.assertGreaterEqual(calculate_icon_toxic_score("Kinh tởm thật sự 🤮"), 0.85)

    def test_repeated_toxic_icons_amplify_score(self):
        single = calculate_icon_toxic_score("Điên quá 😡")
        multiple = calculate_icon_toxic_score("Điên quá 😡😡😡")
        self.assertGreaterEqual(multiple, single)
        self.assertLessEqual(multiple, 1.0)

    def test_extract_icons_details(self):
        details = extract_icons("Bực mình 🤬 và tức giận 😡 nhưng vẫn cảm ơn ❤️")
        icons_found = {d['icon']: d for d in details}
        self.assertIn('🤬', icons_found)
        self.assertIn('😡', icons_found)
        self.assertIn('❤️', icons_found)
        self.assertEqual(icons_found['❤️']['score'], 0.0)
        self.assertGreater(icons_found['🤬']['score'], 0.8)

    def test_text_and_icon_transformer_pipeline(self):
        texts = [
            "cảm ơn bạn rất nhiều ❤️",
            "đồ rác rưởi cút đi 🤬🖕",
            "thông tin hữu ích 👍",
            "mày bị điên à 😡"
        ]
        labels = [0, 1, 0, 1]

        transformer = TextAndIconTransformer(CountVectorizer())
        matrix = transformer.fit_transform(texts)

        # Number of columns must be vocab count + 1 (the icon score column)
        feature_names = transformer.get_feature_names_out()
        self.assertEqual(feature_names[-1], '__feature_icon_toxic_score__')
        self.assertEqual(matrix.shape[1], len(feature_names))

        # Pipeline integration
        pipeline = Pipeline([
            ('features', TextAndIconTransformer(CountVectorizer())),
            ('clf', MultinomialNB())
        ])
        pipeline.fit(texts, labels)
        preds = pipeline.predict(["cảm ơn bạn nhé", "cút đi 🤬"])
        self.assertEqual(len(preds), 2)
        self.assertEqual(preds[1], 1)

        # Attribute delegation (e.g. vocabulary_)
        self.assertIsInstance(transformer.vocabulary_, dict)
        self.assertIn('rác', transformer.vocabulary_)


if __name__ == '__main__':
    unittest.main()
