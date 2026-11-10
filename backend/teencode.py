"""Conservative, versioned lexical normalization for word-based features."""
import hashlib
import json
import re
import unicodedata
from pathlib import Path

DICTIONARY_PATH = Path(__file__).resolve().parents[1] / 'data' / 'teencode_dictionary.json'
_content = DICTIONARY_PATH.read_bytes()
DICTIONARY = json.loads(_content)
DICTIONARY_HASH = hashlib.sha256(_content).hexdigest()[:12]
TEENCODE = DICTIONARY['direct']
_rules = [(re.compile(r['pattern']), r['replacement']) for r in DICTIONARY['context_rules']]
_elongated = [(re.compile(pattern), replacement) for pattern, replacement in DICTIONARY['elongated'].items()]


def normalize_teencode(value):
    """Keep unknown tokens and uppercase technical abbreviations unchanged."""
    text = unicodedata.normalize('NFC', str(value or ''))
    # Unambiguous direct expansion first allows `ko dc` to match context rules.
    def expand(match):
        token = match[0]
        if not token.islower():
            return token
        if token in TEENCODE:
            return TEENCODE[token]
        for pattern, replacement in _elongated:
            if pattern.fullmatch(token):
                return replacement
        return token
    text = re.sub(r'\b\w+\b', expand, text)
    for pattern, replacement in _rules:
        text = pattern.sub(replacement, text)
    return text
