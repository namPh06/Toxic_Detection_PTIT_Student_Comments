"""Icon and Emoji Toxicity Scoring & Feature Extraction for Vietnamese Comments.

Assigns toxicity scores to emojis and emoticons, transforming icons from mere
text tokens into explicit continuous features for machine learning models.
"""
import re
import numpy as np
from scipy.sparse import hstack, csr_matrix
from sklearn.base import BaseEstimator, TransformerMixin

# Emoji & Emoticon Toxicity Lexicon (Thang điểm độc hại từ 0.0 đến 1.0)
ICON_TOXIC_WEIGHTS = {
    # Cực kỳ độc hại / Xúc phạm nặng / Đe dọa (0.85 - 1.0)
    '🖕': 1.0, '🖕🏻': 1.0, '🖕🏼': 1.0, '🖕🏽': 1.0, '🖕🏾': 1.0, '🖕🏿': 1.0,
    '🤬': 0.95,
    '🤮': 0.90,
    '💩': 0.85,
    '🔪': 0.85,
    '👿': 0.85,
    '👺': 0.80,
    '😡': 0.80,

    # Độc hại cao / Thù địch / Mỉa mai hạ bệ (0.60 - 0.79)
    '😠': 0.75,
    '>:(': 0.75,
    '>:-(': 0.75,
    '☠️': 0.70,
    '☠': 0.70,
    '🤡': 0.70,
    '💀': 0.65,
    '😤': 0.60,
    '👎': 0.55,

    # Khinh miệt / Mỉa mai nhẹ / Tiêu cực (0.30 - 0.54)
    '😒': 0.50,
    '🙄': 0.50,
    '🥱': 0.45,
    '🤦': 0.40,
    '🤦‍♂️': 0.40,
    '🤦‍♀️': 0.40,
    '🤥': 0.40,
    '🤨': 0.35,
    'emoticon_sad': 0.30,
    ':(': 0.30,
    ':-(': 0.30,
    ':<': 0.30,

    # Trung tính / Tích cực (0.0)
    'emoticon_smile': 0.0,
    ':)': 0.0,
    ':-)': 0.0,
    ':D': 0.0,
    ':3': 0.0,
    '❤️': 0.0,
    '💖': 0.0,
    '💕': 0.0,
    '👍': 0.0,
    '😊': 0.0,
    '🥰': 0.0,
    '😍': 0.0,
    '👏': 0.0,
    '🎉': 0.0,
    '🌸': 0.0,
    '🍀': 0.0,
    '🙏': 0.0,
    '🤝': 0.0,
    '✨': 0.0,
}


def extract_icons(text):
    """Detect and return a list of (icon, score, count) in the text."""
    if not text:
        return []
    found = []
    for icon, weight in ICON_TOXIC_WEIGHTS.items():
        count = text.count(icon)
        if count > 0:
            found.append({'icon': icon, 'score': weight, 'count': count})
    return found


def calculate_icon_toxic_score(text):
    """Calculate an overall icon toxicity score in [0.0, 1.0] for a text string."""
    if not text or not isinstance(text, str):
        return 0.0
    scores = []
    for icon, weight in ICON_TOXIC_WEIGHTS.items():
        count = text.count(icon)
        if count > 0:
            scores.extend([weight] * count)
    if not scores:
        return 0.0
    max_score = max(scores)
    toxic_count = sum(1 for s in scores if s >= 0.5)
    # Consecutive or multiple toxic icons amplify the toxicity signal
    boost = min(0.15, (toxic_count - 1) * 0.05) if toxic_count > 1 else 0.0
    return round(float(min(1.0, max_score + boost)), 3)


class TextAndIconTransformer(BaseEstimator, TransformerMixin):
    """Combines text n-gram vectorizer features with the continuous icon toxicity score."""

    def __init__(self, vectorizer=None):
        self.vectorizer = vectorizer

    def fit(self, X, y=None):
        if self.vectorizer is not None:
            self.vectorizer.fit(X)
        return self

    def transform(self, X):
        if self.vectorizer is not None:
            text_matrix = self.vectorizer.transform(X)
        else:
            text_matrix = csr_matrix((len(X), 0))
        scores = np.array([[calculate_icon_toxic_score(text)] for text in X], dtype=np.float32)
        score_matrix = csr_matrix(scores)
        return hstack([text_matrix, score_matrix])

    def get_feature_names_out(self, input_features=None):
        if self.vectorizer is not None and hasattr(self.vectorizer, 'get_feature_names_out'):
            base_names = list(self.vectorizer.get_feature_names_out(input_features))
        else:
            base_names = []
        return np.array(base_names + ['__feature_icon_toxic_score__'])

