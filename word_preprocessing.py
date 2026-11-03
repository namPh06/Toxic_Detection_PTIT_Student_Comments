"""Versioned word segmentation for offline experiments; raw corpus stays intact."""
from functools import lru_cache
from dataset import clean_text, STOP_WORDS
VERSION = 'ptit-pyvi-0.1.1-word-v1'

@lru_cache(maxsize=12000)
def word_text(text):
    from pyvi import ViTokenizer
    # Segment before removing stop words so multi-syllable words stay intact.
    normalized = clean_text(text, remove_stopwords=False)
    if not normalized:
        return ''
    return ' '.join(t for t in ViTokenizer.tokenize(normalized).split() if t not in STOP_WORDS)
