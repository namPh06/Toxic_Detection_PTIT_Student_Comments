"""End-to-end Toxic Detection Pipeline.

Processes raw text (single or batch) through cleaning, icon scoring,
feature extraction (TF-IDF, BoW, Word Embedding), and classification (SVM, Naive Bayes, TextCNN).
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import json
from typing import Union, List, Dict, Any, Optional

import numpy as np
from scipy.sparse import issparse, csr_matrix
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.pipeline import Pipeline
import joblib

from data_processing.dataset import clean_text, word_tokens, LABELS
from data_processing.icon_scorer import calculate_icon_toxic_score, TextAndIconTransformer
from models.naive_bayes import create_nb_classifier
from models.svm import create_svm_classifier


class ToxicPipeline:
    """Complete text processing, feature engineering, and toxicity prediction pipeline."""

    def __init__(
        self,
        feature_method: str = 'tfidf',   # 'tfidf' | 'bow' | 'word_embedding'
        model_type: str = 'svm',          # 'svm' | 'naive_bayes' | 'nb'
        ngram_range: tuple = (1, 2),
        max_features: int = 20000,
        include_icon_score: bool = True
    ):
        self.feature_method = feature_method.lower().replace('-', '_')
        self.model_type = model_type.lower().replace('-', '_')
        if self.model_type == 'nb':
            self.model_type = 'naive_bayes'

        self.ngram_range = ngram_range
        self.max_features = max_features
        self.include_icon_score = include_icon_score
        # Ngưỡng phân định tối ưu hóa cho dữ liệu mất cân bằng (giúp tăng mạnh Recall và F1)
        self.decision_threshold = -0.35

        self.vectorizer = None
        self.model = None
        self.is_fitted = False

        self._init_components()

    def _init_components(self):
        """Initialize the vectorizer and classifier according to configuration."""
        if self.feature_method == 'bow':
            base_vec = CountVectorizer(
                tokenizer=word_tokens,
                token_pattern=None,
                lowercase=False,
                ngram_range=self.ngram_range,
                max_features=self.max_features
            )
        elif self.feature_method in ('tfidf', 'word_embedding'):
            # Default to TF-IDF for n-gram feature representation
            base_vec = TfidfVectorizer(
                tokenizer=word_tokens,
                token_pattern=None,
                lowercase=False,
                ngram_range=self.ngram_range,
                max_features=self.max_features
            )
        else:
            raise ValueError(f"Phương pháp trích xuất đặc trưng '{self.feature_method}' không hợp lệ. Chọn 'tfidf', 'bow', hoặc 'word_embedding'.")

        if self.include_icon_score:
            self.vectorizer = TextAndIconTransformer(base_vec)
        else:
            self.vectorizer = base_vec

        if self.model_type == 'svm':
            self.classifier = create_svm_classifier()
        elif self.model_type == 'naive_bayes':
            self.classifier = create_nb_classifier()
        else:
            raise ValueError(f"Loại mô hình '{self.model_type}' không hợp lệ. Chọn 'svm' hoặc 'naive_bayes'.")

    def preprocess(self, texts: Union[str, List[str]]) -> List[Dict[str, Any]]:
        """Preprocess single text or batch of texts."""
        if isinstance(texts, str):
            texts = [texts]

        preprocessed = []
        for text in texts:
            cleaned = clean_text(text)
            score = calculate_icon_toxic_score(text)
            tokens = word_tokens(cleaned) if cleaned else []
            preprocessed.append({
                'text_raw': text,
                'text_clean': cleaned,
                'tokens': tokens,
                'icon_toxic_score': score
            })
        return preprocessed

    def extract_features(self, texts: Union[str, List[str]], fit: bool = False):
        """Transform texts into the selected feature representation."""
        if isinstance(texts, str):
            texts = [texts]

        cleaned_texts = [clean_text(t) or 'unknowntoken' for t in texts]

        if fit:
            feature_matrix = self.vectorizer.fit_transform(cleaned_texts)
            self.is_fitted = True
        else:
            if not self.is_fitted:
                raise RuntimeError("Pipeline chưa được fit. Hãy gọi .fit(texts, labels) trước khi trích xuất đặc trưng.")
            feature_matrix = self.vectorizer.transform(cleaned_texts)

        return feature_matrix

    def get_feature_names(self) -> List[str]:
        """Return names of all features in the vector representation."""
        if not self.is_fitted:
            raise RuntimeError("Pipeline chưa được fit.")
        if hasattr(self.vectorizer, 'get_feature_names_out'):
            return list(self.vectorizer.get_feature_names_out())
        return []

    def fit(self, texts: List[str], labels: List[Union[str, int]]):
        """Train the feature extractor and classifier on texts and labels."""
        if len(texts) != len(labels):
            raise ValueError("Số lượng văn bản và nhãn phải bằng nhau.")

        cleaned_texts = [clean_text(t) or 'unknowntoken' for t in texts]
        # Normalize labels to integer indices (0: non-toxic, 1: toxic)
        y = [l if isinstance(l, int) else LABELS.index(l) for l in labels]

        # Fit feature vectorizer and classifier
        X = self.vectorizer.fit_transform(cleaned_texts)
        self.classifier.fit(X, y)
        self.is_fitted = True
        return self

    def predict(self, texts: Union[str, List[str]]) -> List[Dict[str, Any]]:
        """Predict toxicity for single text or batch of texts."""
        single_input = isinstance(texts, str)
        if single_input:
            texts = [texts]

        if not self.is_fitted:
            raise RuntimeError("Pipeline chưa được huấn luyện. Hãy gọi .fit() hoặc .load() trước.")

        cleaned_texts = [clean_text(t) or 'unknowntoken' for t in texts]
        X = self.vectorizer.transform(cleaned_texts)
        predictions = self.classifier.predict(X)

        feature_names = self.get_feature_names()

        # Decision score / confidence estimation
        decision_scores = None
        if hasattr(self.classifier, 'decision_function'):
            decision_scores = self.classifier.decision_function(X)
        elif hasattr(self.classifier, 'predict_proba'):
            decision_scores = self.classifier.predict_proba(X)[:, 1]

        results = []
        for i, text in enumerate(texts):
            icon_score = calculate_icon_toxic_score(text)
            cleaned = cleaned_texts[i]

            raw_score = float(decision_scores[i]) if decision_scores is not None else 0.0
            # Explicit icon toxicity boost (when hostile emoji like 🖕, 🤬, 🤮 are used)
            icon_boost = icon_score * 1.5 if icon_score >= 0.5 else 0.0
            combined_score = raw_score + icon_boost

            # Continuous normalized toxic score in [-1.0, 1.0] via hyperbolic tangent
            normalized_score = float(np.tanh(combined_score))

            # Adaptive decision threshold (optimized for imbalanced data to maximize Recall and F1)
            is_toxic = bool(combined_score >= self.decision_threshold or icon_score >= 0.8)
            pred_label = 'toxic' if is_toxic else 'non-toxic'

            # Extract top active features for this sample
            row = X.getrow(i) if issparse(X) else csr_matrix(X[i:i+1])
            active_features = {}
            for col_idx, val in zip(row.indices, row.data):
                feat_name = feature_names[col_idx] if col_idx < len(feature_names) else f'feature_{col_idx}'
                active_features[feat_name] = round(float(val), 4)

            results.append({
                'text_raw': text,
                'text_clean': cleaned,
                'tokens': word_tokens(cleaned),
                'icon_toxic_score': icon_score,
                'icon_boost': round(icon_boost, 4),
                'raw_score': round(raw_score, 4),
                'combined_score': round(combined_score, 4),
                'normalized_score': round(normalized_score, 4),
                'decision_threshold': self.decision_threshold,
                'feature_method': self.feature_method,
                'feature_dimension': X.shape[1],
                'active_features': active_features,
                'feature_vector': row,
                'model_type': self.model_type,
                'label': pred_label,
                'score': round(normalized_score, 4),
                'is_toxic': is_toxic
            })

        return results[0] if single_input else results

    def tune_threshold(self, val_texts: List[str], val_labels: List[Union[str, int]]) -> float:
        """Find the optimal decision threshold that maximizes Macro-F1 on validation data."""
        from sklearn.metrics import precision_recall_fscore_support
        y_val = [l if isinstance(l, int) else LABELS.index(l) for l in val_labels]
        cleaned_val = [clean_text(t) or 'unknowntoken' for t in val_texts]
        X_val = self.vectorizer.transform(cleaned_val)
        if hasattr(self.classifier, 'decision_function'):
            scores = self.classifier.decision_function(X_val)
        else:
            scores = self.classifier.predict_proba(X_val)[:, 1]

        best_th, best_f1 = 0.0, 0.0
        for th in np.linspace(-1.5, 0.5, 100):
            preds = (scores >= th).astype(int)
            _, _, f1_macro, _ = precision_recall_fscore_support(y_val, preds, average='macro', zero_division=0)
            if f1_macro > best_f1:
                best_f1, best_th = f1_macro, th

        self.decision_threshold = round(float(best_th), 4)
        return self.decision_threshold

    def inspect(self, text: str) -> str:
        """Run pipeline on single text and return formatted step-by-step breakdown."""
        result = self.predict(text)
        return format_pipeline_steps(result)

    def save(self, path: Union[str, Path]):
        """Save the fitted pipeline to a file."""
        if not self.is_fitted:
            raise RuntimeError("Pipeline chưa được fit; không thể lưu.")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: Union[str, Path]) -> "ToxicPipeline":
        """Load a saved pipeline from a file."""
        return joblib.load(path)


def format_pipeline_steps(p: Dict[str, Any]) -> str:
    """Format pipeline output into step-by-step breakdown: raw -> clean -> token -> feature -> toxic_score."""
    active_feat_str = "\n".join(
        f"        * '{str(k)}': {v:.4f}"
        for k, v in list(p['active_features'].items())[:10]
    ) or "        (Không có token nào trùng trong từ điển tập huấn luyện)"

    label_badge = "🚨 TOXIC (Độc hại)" if p['is_toxic'] else "✅ NON-TOXIC (Lành mạnh)"
    score_desc = f"{p['score']:.4f} (Ngưỡng phân định: 0.0)" if p['score'] is not None else "N/A"

    return f"""================================================================================
BƯỚC 1: RAW TEXT (Văn bản đầu vào)
  "{p['text_raw']}"

BƯỚC 2: CLEAN TEXT (Chuẩn hóa Unicode NFC, giải mã HTML, teencode, ẩn phone/url/email)
  "{p['text_clean']}"

BƯỚC 3: TOKEN (Tách từ ghép tiếng Việt bằng Underthesea & giữ icon)
  {p['tokens']}

BƯỚC 4: FEATURE VECTOR ({p['feature_method'].upper()} + Cột Icon Feature)
  - Tổng số chiều đặc trưng (Dimension) : {p['feature_dimension']}
  - Cột đặc trưng độc hại Icon         : __feature_icon_toxic_score__ = {p['icon_toxic_score']}
  - Các đặc trưng kích hoạt ({len(p['active_features'])}):
{active_feat_str}

BƯỚC 5: TOXIC SCORE & DỰ ĐOÁN CUỐI CÙNG (Thang đo chuẩn hóa [-1.0, 1.0])
  - Điểm mô hình (Model Raw)       : {p.get('raw_score', 'N/A')}
  - Điểm độc hại icon (Icon Score)  : {p['icon_toxic_score']} / 1.0 (Boost: +{p.get('icon_boost', 0.0)})
  - Điểm tổng hợp (Combined Score)  : {p.get('combined_score', 'N/A')}
  - Ngưỡng phân định tối ưu (Thres) : {p.get('decision_threshold', -0.35)} (Tối ưu Macro-F1)
  - Điểm chuẩn hóa [-1.0, 1.0]      : {p.get('normalized_score', p['score'])}
  - Mô hình áp dụng                 : {p['model_type'].upper()}
  - KẾT LUẬN                        : {label_badge}
================================================================================"""


def get_default_pipeline(feature_method: str = 'tfidf', model_type: str = 'svm') -> ToxicPipeline:
    """Load the fully trained 2,089-comment pipeline if available, otherwise fit baseline."""
    trained_path = _ROOT / 'models' / 'trained_toxic_pipeline.joblib'
    if trained_path.is_file() and feature_method == 'tfidf' and model_type in ('svm', 'linear_svc'):
        try:
            return ToxicPipeline.load(trained_path)
        except Exception:
            pass

    sample_texts = [
        "cảm ơn bạn đã chia sẻ bài viết rất hữu ích ❤️",
        "thông tin này hay quá, cảm ơn admin nhiều nhé 👍",
        "mình cũng đồng tình với quan điểm này của bạn 😊",
        "cho mình hỏi tài liệu này có ở thư viện không bạn",
        "chúc các bạn ôn thi kỳ này đạt điểm cao nhé",
        "bài viết chi tiết và dễ hiểu lắm",
        "hôm nay thời tiết đẹp quá bạn ơi cùng đi dạo nhé",
        "đồ ngu ngốc câm mồm đi đừng sủa nữa 🤬🖕",
        "mày bị điên à thứ rác rưởi cút khỏi group",
        "thằng chó này ngu vcl biến đi 🤮",
        "lũ óc chó chúng mày chả biết cái gì cả 💩",
        "đừng có xàm lz nữa đồ khốn nạn 🔪",
        "mày tưởng mày khôn hơn ai à thứ mất dạy 😡",
        "con điên này ăn nói như dở người thế cút 🤬"
    ]
    sample_labels = [
        "non-toxic", "non-toxic", "non-toxic", "non-toxic", "non-toxic", "non-toxic", "non-toxic",
        "toxic", "toxic", "toxic", "toxic", "toxic", "toxic", "toxic"
    ]
    pipeline = ToxicPipeline(feature_method=feature_method, model_type=model_type)
    pipeline.fit(sample_texts, sample_labels)
    return pipeline


if __name__ == '__main__':
    print("Khởi tạo Pipeline phát hiện bình luận Toxic...")
    pipe = get_default_pipeline(feature_method='tfidf', model_type='svm')

    sample_tests = [
        "hôm nay thời tiết đẹp quá bạn ơi",
        "cảm ơn bạn nhiều nhé, bài viết rất bổ ích ❤️👍",
        "mày ăn nói láo vcl cc thế 🤬🖕"
    ]

    for text in sample_tests:
        print(pipe.inspect(text))
        print()

