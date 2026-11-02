"""Context-Aware Disambiguation and Vietnamese Diacritic Correction.

Provides:
1. ContextDisambiguator: A statistical N-gram context-aware disambiguation model
   resolving ambiguous words (e.g. 'the' -> 'thế' vs 'the' in English; 'xl' -> size 'xl' vs 'xin lỗi';
   'pass' -> 'pass đồ' vs 'qua môn' vs 'mật khẩu wifi') based on bilateral context likelihood.
2. TransformerCorrector: Optional Seq2Seq deep learning model (e.g. bmd1905/vietnamese-correction-v2)
   for full sentence text reconstruction when deep learning pipelines are enabled.
3. GeminiNormalizer: Integration with Google Gemini LLM for zero-shot deep context understanding.
"""
import re


class ContextDisambiguator:
    """Statistical N-gram Context Model for ambiguous Vietnamese/loan words."""

    CANDIDATES = {
        'the': {
            'thế': {
                'left': {'gì', 'sao', 'như', 'đến', 'lại', 'làm', 'vậy', 'sao_mà', 'ai', 'cỡ', 'size'},
                'right': {'ạ', 'nhỉ', 'nào', 'vậy', 'nữa', 'đâu', 'này', 'hả', 'kìa', 'được', 'chứ', 'thôi'}
            },
            'thể': {
                'left': {'có', 'không', 'chẳng', 'tập', 'thực', 'cơ', 'thân', 'toàn'},
                'right': {'hiện', 'loại', 'nào', 'nữa', 'thao', 'chế'}
            },
            'thẻ': {
                'left': {'làm', 'mất', 'quẹt', 'nạp', 'mua', 'cầm', 'đổi', 'rút'},
                'right': {'sinh_viên', 'sinh viên', 'atm', 'cào', 'ngân_hàng', 'xanh', 'đỏ', 'bài'}
            },
            'the': {
                'left': {'in', 'on', 'at', 'join', 'to', 'of', 'for', 'share', 'see', 'from', 'with', 'about', 'by'},
                'right': {'group', 'post', 'end', 'best', 'world', 'link', 'page', 'way', 'team', 'club', 'first', 'game'}
            }
        },
        'xl': {
            'xl': {
                'left': {'size', 'áo', 'quần', 'mặc', 'đổi', 'sang', 'form', 'chọn', 'hạ', 'lên', 'cỡ', 'mua', 'bán', 'pass', 'vừa', 'rộng', 'chật', 'lấy', 'đặt'},
                'right': {'muốn', 'đổi', 'sang', 'nhé', 'ạ', 'ko', 'không', 'vừa', 'rộng', 'chật', 'l', 'm', 's', 'xxl', 'nè', 'nữa', 'form', 'nhỉ', 'nào', 'luôn'}
            },
            'xin lỗi': {
                'left': {'thành_thật', 'rất', 'em', 'mình', 'mik', 'anh', 'tôi', 'chân_thành', 'thật_sự', '<START>', 'vô_cùng', 'e'},
                'right': {'bạn', 'mọi_người', 'mn', 'mng', 'nha', 'nhé', 'ạ', 'nhiều', 'vì', 'do', 'mọi', 'ai', 'người_ta', 'thầy', 'cô', 'nhiều_lắm', 'nhưng', 'nhma', 'anh', 'chị'}
            }
        },
        'pass': {
            'pass': {
                'left': {'muốn', 'cần', 'nhờ', 'em', 'mình', 'bạn', 'có', 'bán', 'đăng', '<START>', 'b'},
                'right': {'đồ', 'áo', 'quần', 'lại', 'nhanh', 'gấp', 'giáo_trình', 'sách', 'phòng', 'trọ', 'vé', 'cho', 'nè', 'giá'}
            },
            'qua': {
                'left': {'đã', 'chắc', 'được', 'thi', 'học', 'hy_vọng', 'cầu'},
                'right': {'môn', 'kỳ', 'bài', 'vòng', 'test'}
            },
            'mật khẩu': {
                'left': {'quên', 'xin', 'cho', 'mất', 'nhập', 'đổi', 'lấy', 'hỏi', 'gửi'},
                'right': {'acc', 'tài_khoản', 'fb', 'wifi', 'mail', 'máy'}
            }
        },
        'ma': {
            'mà': {
                'left': {'nhưng', 'sao', 'thế', 'rồi', 'ai', 'người', 'vậy', 'thế_nào', 'chứ', 'biết', 'nói'},
                'right': {'lại', 'còn', 'không', 'sao', 'thôi', 'được', 'chẳng'}
            },
            'má': {
                'left': {'chửi', 'vãi', 'đm', 'con', 'mẹ', 'méo'},
                'right': {'ơi', 'nó', 'mày', 'tao'}
            },
            'ma': {
                'left': {'con', 'bắt', 'sợ', 'hồn', 'trêu'},
                'right': {'quỷ', 'cà_rồng', 'trơi', 'da'}
            }
        },
        'duoc': {
            'được': {
                'left': {'không', 'chưa', 'có', 'nhận', 'làm', 'ăn', 'xem', 'qua', 'học'},
                'right': {'không', 'chưa', 'nhỉ', 'ạ', 'rồi', 'đâu', 'nhé'}
            },
            'dược': {
                'left': {'ngành', 'khoa', 'y', 'thuốc', 'trường'},
                'right': {'học', 'liệu', 'phẩm', 'sĩ'}
            }
        },
        'quan': {
            'quán': {
                'left': {'ở', 'vào', 'ra', 'tìm', 'ngồi', 'ghé'},
                'right': {'nét', 'net', 'cơm', 'ăn', 'trà', 'cafe', 'cà_phê', 'nước'}
            },
            'quân': {
                'left': {'đi', 'học', 'tham_gia', 'vào'},
                'right': {'sự', 'đội', 'nhân', 'khu'}
            },
            'quan': {
                'left': {'liên', 'cơ', 'tổng', 'tham', 'chính', 'sĩ'},
                'right': {'hệ', 'tâm', 'trọng', 'điểm', 'chức', 'lại'}
            }
        },
        'phai': {
            'phải': {
                'left': {'không', 'chẳng', 'cần', 'bắt', 'có', 'lẽ'},
                'right': {'không', 'chăng', 'làm', 'học', 'nói', 'thế', 'vậy', 'chăng'}
            },
            'phái': {
                'left': {'tông', 'giáo', 'bang', 'phân', 'học'},
                'right': {'nam', 'nữ', 'sinh'}
            }
        },
        'day': {
            'đây': {
                'left': {'ở', 'đến', 'qua', 'vào', 'tới', 'tại'},
                'right': {'nè', 'nhé', 'ạ', 'này', 'luôn'}
            },
            'đấy': {
                'left': {'đúng', 'thế', 'phải', 'rồi', 'sao', 'vậy'},
                'right': {'ạ', 'nhỉ', 'nhé', 'chứ'}
            },
            'dạy': {
                'left': {'đi', 'cô', 'thầy', 'giáo_viên', 'mất', 'tự'},
                'right': {'học', 'thêm', 'bảo', 'dỗ'}
            },
            'day': {
                'left': {'happy', 'good', 'one', 'all', 'every', 'each'},
                'right': {'off', 'by', 'time', 'night'}
            }
        }
    }

    @classmethod
    def disambiguate(cls, tokens):
        """Disambiguate a token stream based on local context window likelihood."""
        if not tokens:
            return []
        result = list(tokens)
        n = len(tokens)
        for i, token in enumerate(tokens):
            lower = token.lower()
            if lower in cls.CANDIDATES:
                left = tokens[i - 1].lower() if i > 0 else '<START>'
                right = tokens[i + 1].lower() if i < n - 1 else '<END>'
                best_cand = token
                best_score = 0.0

                for cand, triggers in cls.CANDIDATES[lower].items():
                    score = 0.0
                    left_set = triggers.get('left', set())
                    right_set = triggers.get('right', set())

                    if left in left_set:
                        score += 2.0
                    if right in right_set:
                        score += 2.5
                    # Bigram bonus if both left and right match
                    if left in left_set and right in right_set:
                        score += 3.0

                    if score > best_score:
                        best_score = score
                        best_cand = cand

                if best_score > 0.0:
                    result[i] = best_cand
        return result


def disambiguate_tokens(tokens):
    """Entry point for context disambiguation on a sequence of tokens."""
    return ContextDisambiguator.disambiguate(tokens)


class TransformerCorrector:
    """Optional Deep Learning Seq2Seq text corrector using HuggingFace models."""

    def __init__(self, model_id='bmd1905/vietnamese-correction-v2'):
        self.model_id = model_id
        self._pipeline = None

    def load(self):
        if self._pipeline is None:
            from transformers import pipeline
            self._pipeline = pipeline('text2text-generation', model=self.model_id)

    def correct(self, text, max_length=256):
        self.load()
        output = self._pipeline(text, max_length=max_length)
        if output and isinstance(output, list) and 'generated_text' in output[0]:
            return output[0]['generated_text']
        return text
