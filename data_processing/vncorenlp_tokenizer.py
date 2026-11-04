"""VnCoreNLP Tokenizer integration for Vietnamese text segmentation.

Provides wrapper for VnCoreNLP word segmenter (Nguyen et al., 2018),
with automatic model directory detection and graceful fallback if jar assets are not yet downloaded.
"""
import os
import sys
from pathlib import Path
from typing import List, Tuple, Optional

_ROOT = Path(__file__).resolve().parent.parent
VNCORENLP_DIR = _ROOT / 'models' / 'vncorenlp'
JAR_PATH = VNCORENLP_DIR / 'VnCoreNLP-1.2.jar'

_VNCORENLP_INSTANCE = None
_INIT_ATTEMPTED = False


def is_vncorenlp_installed() -> bool:
    """Check if VnCoreNLP JAR and model files exist locally on disk."""
    return JAR_PATH.is_file() and (VNCORENLP_DIR / 'models' / 'wordsegmenter' / 'wordsegmenter.rdr').is_file()


def get_vncorenlp_segmenter():
    """Lazy initialize the VnCoreNLP word segmenter."""
    global _VNCORENLP_INSTANCE, _INIT_ATTEMPTED
    if _VNCORENLP_INSTANCE is not None:
        return _VNCORENLP_INSTANCE

    if _INIT_ATTEMPTED:
        return None
    _INIT_ATTEMPTED = True

    if not is_vncorenlp_installed():
        return None

    try:
        import py_vncorenlp
        _VNCORENLP_INSTANCE = py_vncorenlp.VnCoreNLP(save_dir=str(VNCORENLP_DIR), annotators=['wseg'])
        return _VNCORENLP_INSTANCE
    except Exception:
        try:
            from vncorenlp import VnCoreNLP
            _VNCORENLP_INSTANCE = VnCoreNLP(str(JAR_PATH), annotators="wseg", max_heap_size='-Xmx500m')
            return _VNCORENLP_INSTANCE
        except Exception:
            return None


def vncorenlp_word_tokenize(text: str) -> List[str]:
    """Tokenize and segment Vietnamese text into word tokens using VnCoreNLP.

    Words containing spaces are connected with an underscore '_' (e.g. 'hôm_nay', 'thời_tiết').
    Falls back to Underthesea if local VnCoreNLP jar files are not yet present.
    """
    if not text or not text.strip():
        return []

    segmenter = get_vncorenlp_segmenter()
    if segmenter is not None:
        try:
            # py_vncorenlp returns segmented string e.g. "Hôm_nay thời_tiết rất đẹp"
            if hasattr(segmenter, 'word_segment'):
                segmented_str = segmenter.word_segment(text)
                if isinstance(segmented_str, list):
                    return " ".join(segmented_str).split()
                return str(segmented_str).split()
            # vncorenlp.VnCoreNLP returns list of sentences of tokens
            elif hasattr(segmenter, 'tokenize'):
                sentences = segmenter.tokenize(text)
                tokens = []
                for sent in sentences:
                    tokens.extend(sent)
                return tokens
        except Exception:
            pass

    # Fallback to Underthesea if VnCoreNLP model files are not found or JVM is inactive
    from underthesea import word_tokenize
    return [word.replace(' ', '_') for word in word_tokenize(text, use_token_normalize=False) if word.strip()]

