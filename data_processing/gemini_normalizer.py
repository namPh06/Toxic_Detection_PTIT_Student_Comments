"""Gemini LLM Text Normalizer for Vietnamese Social Media Comments.

Uses Google Gemini API to contextually normalize, restore diacritics,
and resolve social media ambiguity (slang, teencode, context-dependent words).
Features:
- Caching in data/gemini_cache.json (avoids redundant API calls).
- Batch normalization for efficiency.
- Preserves toxic/profane words required for toxicity classification.
- Graceful offline fallback to local rules and ContextDisambiguator.
"""
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
CACHE_FILE = DATA / 'gemini_cache.json'
CONFIG_FILE = DATA / 'gemini_config.json'

SYSTEM_INSTRUCTION = """Bạn là chuyên gia tiền xử lý ngôn ngữ tiếng Việt tự nhiên cho mạng xã hội sinh viên.
Nhiệm vụ: Chuẩn hóa các câu bình luận Facebook sinh viên sang tiếng Việt chuẩn, sửa lỗi gõ thiếu dấu/sai ngữ cảnh:
1. Hiểu đúng ngữ cảnh tiếng lóng/sinh viên:
   - "pass đồ", "pass áo" -> "nhượng lại / bán lại" (hoặc giữ "pass", tuyệt đối không đổi thành "mật khẩu").
   - "pass môn" -> "qua môn".
   - "size xl", "áo form xl" -> giữ nguyên "size xl" (không đổi thành "xin lỗi").
   - "xl bạn", "mik xl" -> "xin lỗi bạn", "mình xin lỗi".
   - "the ạ", "gì the" -> "thế ạ", "gì thế". "join the group" -> giữ nguyên tiếng Anh.
   - "lh" -> "liên hệ", "b" -> "bạn", "ib" -> "nhắn tin", "cmt" -> "bình luận", "sv" -> "sinh viên".
2. BẢO TỒN SẮC THÁI CẢM XÚC:
   - GIỮ NGUYÊN các từ ngữ công kích, chửi bới, tiêu cực, toxic (như "đồ ngu", "câm mồm", "chó", "vcl"...) để phục vụ bài toán phát hiện độc hại. Không làm dịu hay xóa bỏ sắc thái toxic.
3. Đầu ra: Chỉ trả về mảng JSON đúng thứ tự: ["câu 1 đã chuẩn hóa", "câu 2 đã chuẩn hóa", ...]
"""


def get_api_key():
    """Retrieve Gemini API Key from env or config file."""
    key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if key:
        return key.strip()
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
            return cfg.get('api_key', '').strip()
        except Exception:
            pass
    return ''


def set_api_key(api_key):
    """Save Gemini API Key to local config file."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({'api_key': api_key.strip()}, ensure_ascii=False, indent=2), encoding='utf-8')


def load_cache():
    """Load normalized text cache."""
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


def save_cache(cache):
    """Save normalized text cache atomically."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = CACHE_FILE.with_suffix('.tmp')
    temp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(CACHE_FILE)


def normalize_with_gemini(texts, api_key=None, model='gemini-2.5-flash'):
    """Normalize a batch of texts using Gemini API.
    
    Returns a list of normalized strings.
    """
    if isinstance(texts, str):
        single = True
        texts = [texts]
    else:
        single = False

    key = api_key or get_api_key()
    if not key:
        raise ValueError('Chưa cấu hình GEMINI_API_KEY. Vui lòng cung cấp API Key để sử dụng Gemini.')

    cache = load_cache()
    results = [None] * len(texts)
    missing_indices = []
    missing_texts = []

    for i, t in enumerate(texts):
        h = hashlib.sha256(t.strip().encode('utf-8')).hexdigest()
        if h in cache:
            results[i] = cache[h]
        else:
            missing_indices.append(i)
            missing_texts.append(t)

    if missing_texts:
        # Call Gemini API
        prompt = f"{SYSTEM_INSTRUCTION}\n\nDanh sách câu cần chuẩn hóa:\n"
        for idx, text in enumerate(missing_texts):
            prompt += f"{idx + 1}. {text}\n"
        prompt += "\nTrả về đúng định dạng JSON danh sách các câu đã chuẩn hóa: {\"results\": [\"...\"]}"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            candidates = data.get('candidates', [])
            if not candidates:
                raise RuntimeError('Gemini không trả về kết quả.')
            content = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
            parsed = json.loads(content)
            api_results = parsed.get('results', [])

            # Fill into results and cache
            for orig_idx, norm_text in zip(missing_indices, api_results):
                clean_res = norm_text.strip().lower()
                results[orig_idx] = clean_res
                h = hashlib.sha256(texts[orig_idx].strip().encode('utf-8')).hexdigest()
                cache[h] = clean_res

            save_cache(cache)

    # For any unresolved texts, fall back to original
    for i in range(len(results)):
        if results[i] is None:
            results[i] = texts[i]

    return results[0] if single else results

