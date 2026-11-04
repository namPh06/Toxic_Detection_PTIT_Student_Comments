"""ViSoLex: Vietnamese Social Media Lexical Normalization Module.

Based on ViSoLex (UIT-NLP, Ha Dung et al., 2024) for Non-Standard Word (NSW) normalization:
covers teencode, social media slang, typing typos, and abbreviations, standardizing them
into formal Vietnamese words while preserving profanity signals for toxic detection.
"""
import re
from typing import List, Dict

# ViSoLex Non-Standard Words (NSW) Dictionary for Vietnamese Social Media
VISOLEX_DICTIONARY: Dict[str, str] = {
    # ---- Phủ định / Nghi vấn (Negation & Question NSWs) ----
    'ko': 'không', 'k': 'không', 'kh': 'không', 'k0': 'không', 'hok': 'không',
    'hong': 'không', 'hơm': 'không', 'khum': 'không', 'khong': 'không', 'hem': 'không',
    'kô': 'không', 'hổng': 'không', 'chx': 'chưa', 'chua': 'chưa',
    's': 'sao', 'saoz': 'sao', 'z': 'sao', 'saoo': 'sao',
    'j': 'gì', 'gi': 'gì', 'gỉ': 'gì', 'zì': 'gì', 'j`': 'gì',
    'ntn': 'như thế nào', 'ntnao': 'như thế nào', 'tn': 'thế này', 'tnao': 'thế nào',
    'sao dạ': 'sao vậy', 'sao v': 'sao vậy', 'sao z': 'sao vậy', 'sao zậy': 'sao vậy',

    # ---- Đại từ nhân xưng & Đối tượng (Pronouns & Entities) ----
    'mik': 'mình', 'mềnh': 'mình', 'mk': 'mình', 'minh': 'mình',
    't': 'tao', 'to': 'tao', 'tui': 'tôi', 'toi': 'tôi',
    'm': 'mày', 'may': 'mày', 'mầy': 'mày', 'mài': 'mày',
    'c': 'chị', 'chi': 'chị', 'chj': 'chị', 'che': 'chị',
    'e': 'em', 'emg': 'em',
    'a': 'anh', 'ank': 'anh', 'ox': 'chồng', 'bx': 'vợ',
    'b': 'bạn', 'ban': 'bạn', 'bn': 'bạn', 'bồ': 'bạn', 'bẹn': 'bạn',
    'ng': 'người', 'nguoi': 'người', 'ngừi': 'người', 'ngừ': 'người',
    'ngta': 'người ta', 'nta': 'người ta', 'người t': 'người ta',
    'mng': 'mọi người', 'mn': 'mọi người', 'moi ng': 'mọi người',
    'ai do': 'ai đó', 'ai đs': 'ai đó',

    # ---- Trợ từ, Liên từ & Động từ thông dụng (Particles & Common Verbs) ----
    'dc': 'được', 'đc': 'được', 'đk': 'được', 'duoc': 'được', 'đcvoi': 'được với',
    'bt': 'biết', 'bít': 'biết', 'bik': 'biết', 'bit': 'biết', 'bít r': 'biết rồi',
    'thik': 'thích', 'thic': 'thích', 'thík': 'thích', 'tik': 'thích',
    'lm': 'làm', 'lam': 'làm', 'lèm': 'làm',
    'thực hịn': 'thực hiện', 'thuc hien': 'thực hiện',
    'ns': 'nói', 'noi': 'nói', 'bảo': 'nói',
    'nh': 'nhưng', 'nhg': 'nhưng', 'nhung': 'nhưng', 'ma': 'mà',
    'đag': 'đang', 'dag': 'đang', 'dang': 'đang',
    'r': 'rồi', 'roi': 'rồi', 'rùi': 'rồi', 'roài': 'rồi', 'ròi': 'rồi',
    'vs': 'với', 'voi': 'với', 'zới': 'với', 'w': 'với',
    'cx': 'cũng', 'cug': 'cũng', 'cung': 'cũng', 'cg': 'cũng',
    'nhìu': 'nhiều', 'nhieu': 'nhiều', 'nhiu': 'nhiều', 'nhìu nhìu': 'nhiều',
    'wa': 'quá', 'qua': 'quá', 'qúa': 'quá', 'qá': 'quá',
    'r': 'rồi', 'nghe': 'nghe', 'nghen': 'nghe',
    'oki': 'đồng ý', 'oke': 'đồng ý', 'ok': 'đồng ý', 'okie': 'đồng ý', 'uk': 'ừ', 'uhm': 'ừ',
    'v': 'vậy', 'zậy': 'vậy', 'vay': 'vậy', 'thía': 'thế',
    'hazz': 'thở dài', 'haizz': 'thở dài', 'haiz': 'thở dài', 'hizz': 'thở dài',
    'tks': 'cảm ơn', 'thx': 'cảm ơn', 'thanks': 'cảm ơn', 'cmon': 'cảm ơn', 'cảm ơn': 'cảm ơn',

    # ---- Môi trường học tập / Sinh viên (University & Academic Slang) ----
    'sv': 'sinh viên', 'svien': 'sinh viên', 'sinh vien': 'sinh viên',
    'ptit': 'ptit', 'hv': 'học viện', 'dh': 'đại học', 'đh': 'đại học',
    'clc': 'chất lượng cao', 'ktx': 'ký túc xá',
    'dky': 'đăng ký', 'đky': 'đăng ký', 'dk': 'đăng ký',
    'hp': 'học phí', 'hphi': 'học phí',
    'tn': 'tốt nghiệp', 'tnghiep': 'tốt nghiệp', 'kltn': 'khóa luận tốt nghiệp',
    'tkb': 'thời khóa biểu', 'cntt': 'công nghệ thông tin',
    'btap': 'bài tập', 'bt': 'bài tập', 'ktra': 'kiểm tra', 'thi': 'thi',
    'kq': 'kết quả', 'kqua': 'kết quả',
    'tbao': 'thông báo', 'ttin': 'thông tin',
    'yc': 'yêu cầu', 'ycau': 'yêu cầu',
    'hd': 'hướng dẫn', 'hdan': 'hướng dẫn',
    'vde': 'vấn đề', 'vđ': 'vấn đề', 'ldo': 'lý do',

    # ---- Thời gian & Địa điểm (Time & Locations) ----
    'hnay': 'hôm nay', 'hom nay': 'hôm nay',
    'hqua': 'hôm qua', 'hom qua': 'hôm qua',
    'tnay': 'tối nay', 'toi nay': 'tối nay',
    'ngmai': 'ngày mai', 'ngay mai': 'ngày mai', 'mai': 'ngày mai',
    'tgian': 'thời gian', 't/g': 'thời gian',
    'sg': 'sài gòn', 'hcm': 'hồ chí minh', 'tphcm': 'hồ chí minh', 'hn': 'hà nội',

    # ---- Mua bán / Đời sống / Công nghệ (Life & Social Tech) ----
    'sp': 'sản phẩm', 'spham': 'sản phẩm',
    'dv': 'dịch vụ', 'cty': 'công ty',
    'nv': 'nhân viên', 'nvien': 'nhân viên',
    'sdt': 'số điện thoại', 'sđt': 'số điện thoại',
    'đt': 'điện thoại', 'đthoai': 'điện thoại',
    'đchi': 'địa chỉ', 'dc': 'địa chỉ',
    'vd': 'ví dụ', 'vidu': 'ví dụ',
    'cf': 'cà phê', 'caphe': 'cà phê',
    'sn': 'sinh nhật', 'snvv': 'sinh nhật vui vẻ',
    'ib': 'nhắn tin', 'inbox': 'nhắn tin',
    'cmt': 'bình luận', 'cm': 'bình luận', 'comment': 'bình luận',
    'acc': 'tài khoản', 'ad': 'quản trị viên', 'admin': 'quản trị viên',
    'fb': 'facebook', 'yt': 'youtube', 'ig': 'instagram',
    'btw': 'nhân tiện', 'asap': 'càng sớm càng tốt'
}


def normalize_visolex_token(token: str) -> str:
    """Normalize a single token using ViSoLex Non-Standard Word mapping."""
    return VISOLEX_DICTIONARY.get(token, token)


def normalize_visolex_tokens(tokens: List[str]) -> List[str]:
    """Normalize a list of tokens via ViSoLex dictionary."""
    normalized: List[str] = []
    for token in tokens:
        expanded = VISOLEX_DICTIONARY.get(token, token)
        normalized.extend(expanded.split())
    return normalized


def normalize_visolex_text(text: str) -> str:
    """Normalize non-standard words in a full string using ViSoLex."""
    if not text:
        return ""
    words = text.split()
    normalized_words = []
    for w in words:
        clean_w = w.lower()
        if clean_w in VISOLEX_DICTIONARY:
            normalized_words.append(VISOLEX_DICTIONARY[clean_w])
        else:
            normalized_words.append(w)
    return " ".join(normalized_words)

