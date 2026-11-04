from __future__ import annotations

import math
import os
import re
from difflib import SequenceMatcher

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ============================================================== Giao diện / màu sắc
W, H = 1280, 720
BG, CARD, CARD2 = (11, 18, 32), (22, 32, 52), (34, 48, 76)
TEXT, MUTED, GRAY = (226, 232, 240), (130, 145, 170), (148, 163, 184)
ACCENT, GOOD, BAD, WARN = (56, 189, 248), (52, 211, 153), (251, 76, 106), (251, 191, 36)

STAGES = ['Văn bản gốc', 'Chữ thường', 'Chuẩn hoá', 'Khôi phục từ', 'Emoji', 'Đặc trưng', 'Mô hình', 'Kết luận']
ORDER = ['raw', 'lower', 'norm', 'restore', 'emoji', 'feat', 'model', 'verdict']
DEFAULT_DURS = {'raw': 4.0, 'lower': 4.0, 'norm': 4.8, 'restore': 5.2, 'emoji': 4.6,
                'feat': 5.6, 'model': 4.6, 'verdict': 8.0}

# ---- Đồ thị + camera: mỗi bước là một "thẻ" (node) trên canvas, nối nhau bằng cạnh có mũi tên.
CW, CH, CY0 = 1280, 556, 86     # vùng nội dung của mỗi scene (toạ độ logic) -> kích thước một thẻ
GX, GY, COLS = 260, 200, 4      # khoảng cách giữa các thẻ, số thẻ mỗi hàng (đi theo hình chữ S)
S_FOCUS, SCY = 0.93, 352        # độ zoom khi "đọc" một thẻ, và toạ độ y tâm vùng nhìn
CAM_FIRST, CAM_IN = 0.5, 1.2    # giây dành cho camera trước khi nội dung của scene bắt đầu chạy
OV_LEN, OV_TAIL = 1.6, 2.8      # cuối video: lùi camera để thấy toàn bộ đồ thị (thời lượng / thời điểm trước khi hết)
EDGE_OPS = ['lower', 'chuẩn hoá', 'khôi phục', 'emoji', 'đặc trưng', 'mô hình', 'kết luận']


def _card_xy(i):
    row, c = divmod(i, COLS)
    col = c if row % 2 == 0 else COLS - 1 - c      # hàng lẻ đi ngược lại -> cạnh nối giữa 2 hàng là đường thẳng đứng
    return col * (CW + GX), row * (CH + GY)


def _edge_pts(j):
    """Điểm đầu/cuối (toạ độ world) của cạnh nối thẻ j -> j+1."""
    (x0, y0), (x1, y1), m = _card_xy(j), _card_xy(j + 1), 12
    if y0 == y1:
        cy = y0 + CH / 2
        return ((x0 + CW + m, cy), (x1 - m, cy)) if x1 > x0 else ((x0 - m, cy), (x1 + CW + m, cy))
    return (x0 + CW / 2, y0 + CH + m), (x1 + CW / 2, y1 - m)


def _focus(i):
    x, y = _card_xy(i)
    return (x + CW / 2, y + CH / 2, S_FOCUS)


def _fit(n):
    """Camera nhìn vừa n thẻ đầu tiên (kèm nhãn phía trên thẻ)."""
    pts = [_card_xy(i) for i in range(n)]
    x0, x1 = min(p[0] for p in pts) - 50, max(p[0] for p in pts) + CW + 50
    y0, y1 = min(p[1] for p in pts) - 120, max(p[1] for p in pts) + CH + 40
    s = min(S_FOCUS, 1200 / (x1 - x0), 505 / (y1 - y0))
    return ((x0 + x1) / 2, (y0 + y1) / 2, s)


def _cam_lerp(a, b, e):
    """Nội suy camera: zoom theo hàm mũ, tâm di chuyển cùng nhịp zoom -> cảm giác 'bay' mượt."""
    s = math.exp(lerp(math.log(a[2]), math.log(b[2]), e))
    d = 1 / b[2] - 1 / a[2]
    u = e if abs(d) < 1e-9 else clamp((1 / s - 1 / a[2]) / d)
    return (lerp(a[0], b[0], u), lerp(a[1], b[1], u), s)

CAPTIONS = {
    'raw': 'Văn bản gốc do người dùng nhập — chưa qua xử lý nào.',
    'lower': 'Chuyển toàn bộ về chữ thường để "NGU" và "ngu" được coi là một từ.',
    'norm': 'Chuẩn hoá: Unicode, ký tự lặp, dấu thanh, thông tin cá nhân...',
    'restore': 'Khôi phục từ viết tắt / né lọc về dạng gốc: ko → không, đ!t → địt.',
    'emoji': 'Mỗi emoji có điểm toxic riêng (−1: thân thiện … +1: độc hại).',
    'feat': 'Biến văn bản thành vector số để mô hình có thể tính toán.',
    'model': 'Vector đặc trưng được đưa vào mô hình để tính điểm toxic.',
    'verdict': 'Kết luận: điểm càng gần +1 càng toxic, càng gần −1 càng an toàn.',
}


_EMO_PAT = re.compile('([\U0001F000-\U0001FAFF\u2600-\u27BF\u2B50\u2764])(\ufe0f?)')
EMO_ADV = 1.2   # độ rộng một emoji = EMO_ADV * cỡ chữ


def split_emoji(s):
    """'ab🤡c' -> [(False,'ab'), (True,'🤡'), (False,'c')]  (bỏ ký tự chọn biến thể U+FE0F)"""
    out, pos = [], 0
    for m in _EMO_PAT.finditer(s):
        if m.start() > pos:
            out.append((False, s[pos:m.start()]))
        out.append((True, m.group(1)))
        pos = m.end()
    if pos < len(s):
        out.append((False, s[pos:]))
    return [(e, t) for e, t in out if t.replace('\ufe0f', '')]


def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out(x): x = clamp(x); return 1 - (1 - x) ** 3
def ease_io(x): x = clamp(x); return x * x * (3 - 2 * x)
def ease_back(x):
    x = clamp(x); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2
def lerp(a, b, t): return a + (b - a) * t
def lerp_c(c1, c2, t): return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))
def score_color(s): return lerp_c(GRAY, BAD, clamp(s)) if s >= 0 else lerp_c(GRAY, GOOD, clamp(-s))


# ============================================================== Font
def _first(paths):
    return next((p for p in paths if p and os.path.exists(p)), None)


def _find_fonts(font_path=None, bold_path=None, emoji_font_path=None):
    try:
        import matplotlib
        mpl = os.path.join(matplotlib.get_data_path(), 'fonts', 'ttf')
    except Exception:
        mpl = ''
    reg = _first([font_path, '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/segoeui.ttf',
                  'C:/Windows/Fonts/arial.ttf', '/System/Library/Fonts/Supplemental/Arial.ttf',
                  '/Library/Fonts/Arial.ttf', os.path.join(mpl, 'DejaVuSans.ttf')])
    bold = _first([bold_path, '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/segoeuib.ttf',
                   'C:/Windows/Fonts/arialbd.ttf', '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
                   os.path.join(mpl, 'DejaVuSans-Bold.ttf')]) or reg
    emo = _first([emoji_font_path, '/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf',
                  '/usr/share/fonts/noto/NotoColorEmoji.ttf', '/System/Library/Fonts/Apple Color Emoji.ttc',
                  'C:/Windows/Fonts/seguiemj.ttf'])
    if not reg:
        raise RuntimeError('Không tìm thấy font có dấu tiếng Việt. Hãy truyền font_path=... (vd DejaVuSans.ttf).')
    return reg, bold, emo


_font_cache, _emoji_cache = {}, {}


def _font(path, size):
    k = (path, size)
    if k not in _font_cache:
        _font_cache[k] = ImageFont.truetype(path, size)
    return _font_cache[k]


def _emoji_tile(path, ch):
    """Vẽ emoji màu ở kích thước gốc rồi cắt thành ô vuông. Trả về None nếu font không vẽ được."""
    k = (path, ch)
    if k in _emoji_cache:
        return _emoji_cache[k]
    tile = None
    for native in (109, 136, 160, 96, 72):
        try:
            f = ImageFont.truetype(path, native)
            im = Image.new('RGBA', (native * 3, int(native * 1.6)), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((6, 6), ch, font=f, embedded_color=True)
            bb = im.getbbox()
            if bb:
                im = im.crop(bb)
                side = max(im.size)
                sq = Image.new('RGBA', (side, side), (0, 0, 0, 0))
                sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
                tile = sq
                break
        except Exception:
            continue
    _emoji_cache[k] = tile
    return tile


# ============================================================== Painter (vẽ với siêu lấy mẫu, toạ độ logic 1280x720)
class Painter:
    def __init__(self, base: Image.Image, ss, fonts, layout_cache):
        self.img, self.ss = base, ss
        self.d = ImageDraw.Draw(self.img)
        self.reg, self.bold, self.emo = fonts
        self.opacity = 1.0
        self._lc = layout_cache
        self._emo_sized = {}

    def _a(self, alpha): return int(255 * clamp(alpha * self.opacity))

    def font(self, size, bold=False):
        return _font(self.bold if bold else self.reg, max(1, int(round(size * self.ss))))

    def tw(self, s, size, bold=False):
        f = self.font(size, bold)
        return sum(EMO_ADV * size if e else f.getlength(t) / self.ss for e, t in split_emoji(s))

    def _run(self, box, fn, a, pad=2):
        if a >= 255:
            fn(self.d, 0, 0)
            return
        x0, y0 = max(0, box[0] - pad), max(0, box[1] - pad)
        x1, y1 = min(self.img.width, box[2] + pad), min(self.img.height, box[3] + pad)
        if x1 <= x0 or y1 <= y0:
            return
        ov = Image.new('RGBA', (x1 - x0, y1 - y0), (0, 0, 0, 0))
        fn(ImageDraw.Draw(ov), x0, y0)
        self.img.alpha_composite(ov, dest=(x0, y0))

    def rrect(self, x0, y0, x1, y1, r=12, fill=None, outline=None, width=1, alpha=1.0):
        a = self._a(alpha)
        if a <= 0:
            return
        s = self.ss
        box = [int(x0 * s), int(y0 * s), int(x1 * s), int(y1 * s)]

        def fn(d, ox, oy):
            d.rounded_rectangle([box[0] - ox, box[1] - oy, box[2] - ox, box[3] - oy], radius=int(r * s),
                                fill=(tuple(fill) + (a,)) if fill else None,
                                outline=(tuple(outline) + (a,)) if outline else None, width=max(1, int(width * s)))
        self._run(box, fn, a, pad=int(width * s) + 3)

    def ellipse(self, cx, cy, r, fill, alpha=1.0):
        a = self._a(alpha)
        if a <= 0:
            return
        s = self.ss
        box = [int((cx - r) * s), int((cy - r) * s), int((cx + r) * s), int((cy + r) * s)]

        def fn(d, ox, oy):
            d.ellipse([box[0] - ox, box[1] - oy, box[2] - ox, box[3] - oy], fill=tuple(fill) + (a,))
        self._run(box, fn, a)

    def line(self, x0, y0, x1, y1, color, width=2, alpha=1.0):
        a = self._a(alpha)
        if a <= 0:
            return
        s = self.ss
        box = [int(min(x0, x1) * s), int(min(y0, y1) * s), int(max(x0, x1) * s), int(max(y0, y1) * s)]

        def fn(d, ox, oy):
            d.line([(x0 * s - ox, y0 * s - oy), (x1 * s - ox, y1 * s - oy)], fill=tuple(color) + (a,),
                   width=max(1, int(width * s)))
        self._run(box, fn, a, pad=int(width * s) + 3)

    def poly(self, pts, color, alpha=1.0):
        a = self._a(alpha)
        if a <= 0:
            return
        s = self.ss
        xs, ys = [p[0] * s for p in pts], [p[1] * s for p in pts]
        box = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]

        def fn(d, ox, oy):
            d.polygon([(x - ox, y - oy) for x, y in zip(xs, ys)], fill=tuple(color) + (a,))
        self._run(box, fn, a, pad=3)

    def text(self, x, y, s_, size, color=TEXT, anchor='lm', bold=False, alpha=1.0):
        a = self._a(alpha)
        if a <= 0 or not s_:
            return 0
        if _EMO_PAT.search(s_):
            return self._rich_text(x, y, s_, size, color, anchor, bold, alpha)
        f, ss = self.font(size, bold), self.ss
        pos = (x * ss, y * ss)
        bb = self.d.textbbox(pos, s_, font=f, anchor=anchor)

        def fn(d, ox, oy):
            d.text((pos[0] - ox, pos[1] - oy), s_, font=f, fill=tuple(color) + (a,), anchor=anchor)
        self._run([int(b) for b in bb], fn, a, pad=4)
        return f.getlength(s_) / ss

    def _rich_text(self, x, y, s_, size, color, anchor, bold, alpha):
        total = self.tw(s_, size, bold)
        h, v = anchor[0], anchor[1:] or 'm'
        cx = x - (total / 2 if h == 'm' else total if h == 'r' else 0)
        for is_e, seg in split_emoji(s_):
            if is_e:
                self.emoji(seg, cx + EMO_ADV * size / 2, y, size * 1.05, alpha)
                cx += EMO_ADV * size
            else:
                cx += self.text(cx, y, seg, size, color, 'l' + v, bold, alpha)
        return total

    def arrow(self, x0, y0, x1, y1, color, width=3, alpha=1.0, head=11):
        self.line(x0, y0, x1, y1, color, width, alpha)
        ang = math.atan2(y1 - y0, x1 - x0)
        pts = [(x1, y1), (x1 - head * math.cos(ang - 0.45), y1 - head * math.sin(ang - 0.45)),
               (x1 - head * math.cos(ang + 0.45), y1 - head * math.sin(ang + 0.45))]
        self.poly(pts, color, alpha)

    def chip(self, cx, cy, s_, size=18, fill=CARD2, outline=None, color=TEXT, scale=1.0, alpha=1.0,
             bold=False, padx=14, h=None):
        """Chip căn giữa tại (cx, cy); scale>1 để tạo hiệu ứng pop. Trả về chiều rộng."""
        size_s = size * scale
        w = self.tw(s_, size_s, bold) + 2 * padx * scale
        hh = (h or size * 1.9) * scale
        self.rrect(cx - w / 2, cy - hh / 2, cx + w / 2, cy + hh / 2, r=hh / 2.4 if hh < 60 else 14,
                   fill=fill, outline=outline, width=1.5, alpha=alpha)
        self.text(cx, cy, s_, size_s, color, 'mm', bold, alpha)
        return w

    def emoji(self, ch, cx, cy, size, alpha=1.0, label='?'):
        a = clamp(alpha * self.opacity)
        px = max(2, int(size * self.ss))
        tile = _emoji_tile(self.emo, ch) if self.emo else None
        if tile is None:   # không có font emoji -> vẽ ô chữ thay thế
            self.ellipse(cx, cy, size / 2, CARD2, alpha)
            self.text(cx, cy, (label or '?')[:2], size * 0.4, MUTED, 'mm', True, alpha)
            return
        k = (ch, px)
        if k not in self._emo_sized:
            self._emo_sized[k] = tile.resize((px, px), Image.LANCZOS)
        t = self._emo_sized[k].copy()
        t.putalpha(t.getchannel('A').point(lambda v: int(v * a)))
        self.img.alpha_composite(t, dest=(max(0, int(cx * self.ss - px / 2)), max(0, int(cy * self.ss - px / 2))))

    def gradient_bar(self, x0, y0, x1, y1, stops, r=14, alpha=1.0):
        s = self.ss
        w, h = int((x1 - x0) * s), int((y1 - y0) * s)
        xs = np.linspace(0, 1, w)
        pos = [p for p, _ in stops]
        arr = np.zeros((h, w, 4), np.uint8)
        for ch in range(3):
            arr[:, :, ch] = np.interp(xs, pos, [c[ch] for _, c in stops])[None, :]
        arr[:, :, 3] = int(255 * clamp(alpha * self.opacity))
        im = Image.fromarray(arr, 'RGBA')
        mask = Image.new('L', (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=int(r * s), fill=255)
        im.putalpha(Image.fromarray((np.array(mask, np.float32) * np.array(im.getchannel('A'), np.float32) / 255)
                                    .astype(np.uint8)))
        self.img.alpha_composite(im, dest=(int(x0 * s), int(y0 * s)))

    # ---------- bố cục chữ theo ký tự (để highlight / hiệu ứng từng ký tự)
    def layout(self, text, size, max_w, bold=False):
        key = (text, size, bold, max_w, self.ss)
        if key in self._lc:
            return self._lc[key]
        f, s = self.font(size, bold), self.ss
        lines, cur, x = [], [], 0.0
        for m in re.finditer(r'\n|\s+|\S+', text):
            tok, st = m.group(), m.start()
            if tok == '\n':
                lines.append(cur); cur, x = [], 0.0
                continue
            w = self.tw(tok, size, bold)
            if not tok.isspace() and x > 0 and x + w > max_w:
                lines.append(cur); cur, x = [], 0.0
            if tok.isspace() and not cur and lines:
                continue
            if w > max_w and not tok.isspace():   # từ quá dài: ngắt theo ký tự
                for k, ch in enumerate(tok):
                    cw = f.getlength(ch) / s
                    if x + cw > max_w:
                        lines.append(cur); cur, x = [], 0.0
                    cur.append((st + k, ch, x)); x += cw
                continue
            if _EMO_PAT.search(tok):   # token có emoji: cộng dồn từng ký tự
                xx = x
                for k, ch in enumerate(tok):
                    cur.append((st + k, ch, xx))
                    xx += 0 if ch == '\ufe0f' else (EMO_ADV * size if _EMO_PAT.match(ch) else f.getlength(ch) / s)
                x = xx
            else:
                for k, ch in enumerate(tok):
                    cur.append((st + k, ch, x + f.getlength(tok[:k]) / s))
                x += w
        lines.append(cur)
        self._lc[key] = lines
        return lines

    def draw_layout(self, lines, x, y, size, style_fn, line_h=None, bold=False):
        """style_fn(idx, ch) -> (color, alpha, bg|None, bg_alpha). Gom các ký tự cùng kiểu thành một đoạn."""
        line_h = line_h or size * 1.45
        for li, line in enumerate(lines):
            yy = y + li * line_h
            runs, cur = [], None
            for idx, ch, cx in line:
                st = style_fn(idx, ch)
                if cur and cur['st'] == st:
                    cur['s'] += ch
                else:
                    cur = {'x': cx, 's': ch, 'st': st}
                    runs.append(cur)
            for r in runs:
                color, a, bg, bga = r['st']
                if bg is not None and bga > 0 and r['s'].strip() != '':
                    w = self.tw(r['s'], size, bold)
                    self.rrect(x + r['x'] - 2, yy - line_h * 0.42, x + r['x'] + w + 2, yy + line_h * 0.42,
                               r=6, fill=bg, alpha=bga)
                if a > 0 and r['s'].strip() != '':
                    self.text(x + r['x'], yy, r['s'], size, color, 'lm', bold, a)


# ============================================================== Bộ dựng cảnh
class _Renderer:
    def __init__(self, trace):
        self.tr = trace
        self.order = [str(i) for i in range(len(trace['stages']))]
        self.titles = [s['title'] for s in trace['stages']]
        self.edge_ops = ['tiếp tục'] * len(self.order)
        self.ssaa = 1
        self.fonts = _find_fonts()
        self.durs = {k: 4.5 for k in self.order}
        self.durs[self.order[-1]] = 7.0
        self.cstart = {k: CAM_IN for k in self.order}
        self.caps = {k: trace['model'] + ' · ' + self.titles[int(k)] for k in self.order}
        self.timeline = []
        now = 0.0
        for k in self.order:
            end = now + self.cstart[k] + self.durs[k]
            self.timeline.append((k, now, end))
            now = end
        self.total = now
        self._lc, self._frozen = {}, {}
        self.base = Image.new('RGBA', (W, H), BG + (255,))

    def __getattr__(self, name):
        if name.startswith('scene_'):
            return lambda p, t, dur: self.scene(p, t, dur, int(name[6:]))
        raise AttributeError(name)

    # ---------------------------------------------------------------- thẻ (node) của đồ thị
    def _card_img(self, key, ls, dur):
        """Render nội dung scene `key` ở thời điểm nội dung ls thành ảnh của một thẻ (kích thước ssaa)."""
        ss = self.ssaa
        p = Painter(self.base.copy(), ss, self.fonts, self._lc)
        p.opacity = ease_out(clamp(ls / 0.35))
        getattr(self, 'scene_' + key)(p, max(0.0, ls), dur)
        p.opacity = 1.0
        return p.img.crop((0, CY0 * ss, W * ss, (CY0 + CH) * ss))

    def _frozen_img(self, key):
        """Ảnh 'đóng băng' của thẻ ở trạng thái cuối, dùng khi thẻ đã xong và chỉ còn nằm trong đồ thị."""
        if key not in self._frozen:
            self._frozen[key] = self._card_img(key, self.durs[key], self.durs[key])
        return self._frozen[key]

    def _camera(self, idx, lt):
        """Trả về (camera, ov). ov>0 khi đang lùi ra để xem toàn cảnh ở cuối video."""
        if idx == 0:
            f = _focus(0)
            cam = _cam_lerp((f[0], f[1], 0.5), f, ease_io((lt - 0.1) / 0.8))
        else:
            fp, ft, ff = _focus(idx - 1), _fit(idx + 1), _focus(idx)
            if lt < 0.6:
                cam = _cam_lerp(fp, ft, ease_io(lt / 0.6))          # lùi ra: thấy 1..idx
            elif lt < 0.95:
                cam = ft
            else:
                cam = _cam_lerp(ft, ff, ease_io((lt - 0.95) / 0.6))  # zoom vào bước mới
        ov = 0.0
        if idx == len(self.order) - 1:
            lc = lt - self.cstart[self.order[idx]]
            ov = ease_io((lc - (self.durs[self.order[idx]] - OV_TAIL)) / OV_LEN)
            if ov > 0:
                cam = _cam_lerp(cam, _fit(len(self.order)), ov)
        return cam, ov

    def _grid(self, P, cam):
        """Lưới chấm nền chuyển động theo camera -> cảm giác canvas vô hạn."""
        cx, cy, s = cam
        step, ss = 200, self.ssaa
        r = max(1.2, 3 * s) * ss
        gx0, gx1 = int((cx - 640 / s) // step) - 1, int((cx + 640 / s) // step) + 2
        gy0, gy1 = int((cy - SCY / s) // step) - 1, int((cy + (H - SCY) / s) // step) + 2
        for gx in range(gx0, gx1):
            for gy in range(gy0, gy1):
                x, y = ((gx * step - cx) * s + 640) * ss, ((gy * step - cy) * s + SCY) * ss
                P.d.ellipse([x - r, y - r, x + r, y + r], fill=(27, 39, 64, 255))

    def _draw_card(self, P, cam, j, img, pop, dim, active, ov, ghost=0.0):
        cx, cy, s = cam
        ss = self.ssaa
        x, y = _card_xy(j)
        sc = lerp(0.86, 1.0, pop)
        sx, sy = (x + CW / 2 - cx) * s + 640, (y + CH / 2 - cy) * s + SCY
        w, h = CW * s * sc, CH * s * sc
        x0, y0, x1, y1 = sx - w / 2, sy - h / 2, sx + w / 2, sy + h / 2
        if x1 < -40 or x0 > W + 40 or y1 < -40 or y0 > H + 40:
            return
        a = clamp(pop * 1.6)
        P.opacity = a
        m = 12 * s * sc
        border = lerp_c(CARD2, ACCENT, (1 - 0.6 * ov) if active else 0.0)
        P.rrect(x0 - m, y0 - m, x1 + m, y1 + m, r=max(6, 30 * s), fill=BG, outline=border, width=max(1.5, 3 * s))
        if ghost > 0:   # số bước mờ trong thẻ trống, biến mất khi nội dung hiện ra
            P.text(sx, sy, str(j + 1), 280 * s * sc, CARD2, 'mm', True, ghost)
        if img is not None:
            dw, dh = max(1, int(round(w * ss))), max(1, int(round(h * ss)))
            t = img.resize((dw, dh), Image.LANCZOS if s > 0.45 else Image.BILINEAR)
            ox, oy = int(round(x0 * ss)), int(round(y0 * ss))
            c0, r0 = max(0, -ox), max(0, -oy)
            c1, r1 = min(dw, P.img.width - ox), min(dh, P.img.height - oy)
            if c1 > c0 and r1 > r0:
                t = t.crop((c0, r0, c1, r1))
                if a < 1:
                    t.putalpha(int(255 * a))
                P.img.alpha_composite(t, dest=(ox + c0, oy + r0))
        if dim > 0.01:
            P.rrect(x0, y0, x1, y1, r=0, fill=BG, alpha=dim)
        if s < 0.6:   # nhãn bước phía trên thẻ khi đang zoom xa
            la = clamp((0.6 - s) / 0.2)
            size = max(12, min(44, 74 * s))
            col = TEXT if ov > 0.5 else (ACCENT if active else MUTED)
            P.text(x0, y0 - m - size * 0.9, f'{j + 1}. {self.titles[j]}', size, col, 'lm', True, la)
        P.opacity = 1.0

    def _draw_edges(self, P, cam, t, idx, lt):
        cx, cy, s = cam
        to_s = lambda q: ((q[0] - cx) * s + 640, (q[1] - cy) * s + SCY)
        for j in range(idx):
            prog = 1.0 if j + 1 < idx else ease_io((lt - 0.35) / 0.5)
            if prog <= 0:
                continue
            (ax, ay), (bx, by) = to_s(_edge_pts(j)[0]), to_s(_edge_pts(j)[1])
            if max(ax, bx) < -40 or min(ax, bx) > W + 40 or max(ay, by) < -40 or min(ay, by) > H + 40:
                continue
            hx, hy = lerp(ax, bx, prog), lerp(ay, by, prog)
            wd = max(2.0, 9 * s)
            P.arrow(ax, ay, hx, hy, (22, 132, 168) if prog >= 1 else ACCENT, wd, head=max(9, 36 * s))
            if prog < 1:
                P.ellipse(hx, hy, max(4, 14 * s), ACCENT, alpha=0.35)
            else:
                for k in range(2):   # hạt sáng chạy dọc cạnh = dữ liệu đang chảy
                    u = (t * 0.45 + k * 0.5 + j * 0.13) % 1
                    P.ellipse(lerp(ax, bx, u), lerp(ay, by, u), max(2.5, 7 * s), (190, 235, 255),
                              alpha=0.9 * math.sin(math.pi * u))
            op, size = self.edge_ops[j], max(11, min(28, 44 * s))
            w_chip = P.tw(op, size) + 20
            if prog > 0.6 and (abs(bx - ax) < 1 or w_chip <= abs(bx - ax) * 0.9):
                q = clamp((prog - 0.6) / 0.4)
                P.chip((ax + bx) / 2, (ay + by) / 2, op, size, fill=(14, 60, 90), outline=ACCENT, color=ACCENT,
                       alpha=q, padx=10, h=size * 1.8)

    # ---------------------------------------------------------------- HUD: đồ thị thu nhỏ + chú thích
    def _hud(self, P, t, idx, lt):
        n, x0, sp, cy, r = len(self.order), 90, 1100 / max(1, len(self.order) - 1), 31, 14
        first = idx == 0
        for k in range(n):
            cxk = x0 + k * sp
            if k:   # cạnh nối k-1 -> k: mờ nếu chưa tới, vẽ dần khi bước k xuất hiện
                xa, xb = cxk - sp + r + 8, cxk - r - 8
                P.line(xa, cy, xb, cy, CARD2, 3, 0.6)
                lp = 1.0 if k < idx else (ease_io((lt - 0.3) / 0.45) if k == idx else 0.0)
                if lp > 0:
                    P.line(xa, cy, lerp(xa, xb, lp), cy, ACCENT if k == idx else (14, 116, 144), 3)
            pop = 1.0 if k < idx else (ease_back((lt - (0.1 if first else 0.5)) / 0.45) if k == idx else 0.0)
            if pop <= 0:
                P.ellipse(cxk, cy, 5, CARD2, 0.8)
                continue
            act, rr = k == idx, r * clamp(pop, 0.01, 1.25)
            if act:
                pulse = 0.5 + 0.5 * math.sin(t * 4)
                P.ellipse(cxk, cy, rr + 5 + 3 * pulse, ACCENT, alpha=0.18 + 0.12 * pulse)
            P.ellipse(cxk, cy, rr, ACCENT if act else (14, 116, 144))
            P.text(cxk, cy, str(k + 1), 14, (6, 24, 44) if act else TEXT, 'mm', True, clamp(pop))
            P.text(cxk, cy + 27, self.titles[k][:19], 12, TEXT if act else MUTED, 'mm', act, clamp(pop))
        P.rrect(40, 74, 1240, 77, r=2, fill=CARD)
        P.rrect(40, 74, 40 + max(6, 1200 * t / self.total), 77, r=2, fill=ACCENT)
        # chú thích: câu cũ mờ đi, câu mới hiện lên khi camera đã gần tới nơi
        P.rrect(40, 628, 1240, 692, r=16, fill=CARD, outline=CARD2, width=1.5)

        def put(k, al):
            cap, size = self.caps[k], 24
            while P.tw(cap, size) > 1130 and size > 15:
                size -= 1
            P.text(640, 660, cap, size, TEXT, 'mm', False, al)
        a_new = ease_out((lt - (0.3 if first else 0.35)) / 0.4)
        if idx:
            put(self.order[idx - 1], 1 - ease_out(lt / 0.25))
        put(self.order[idx], a_new)

    # ---------------------------------------------------------------- khung hình
    def frame(self, t):
        ss = self.ssaa
        idx = next((i for i, (k, a, b) in enumerate(self.timeline) if a <= t < b), len(self.timeline) - 1)
        key, s0, _ = self.timeline[idx]
        lt = t - s0
        ls = lt - self.cstart[key]                      # thời gian nội dung của scene (âm = camera còn đang bay)
        cam, ov = self._camera(idx, lt)

        P = Painter(self.base.copy(), ss, self.fonts, self._lc)
        self._lc.clear()
        self._grid(P, cam)
        pop_new = ease_back((lt - (0.0 if idx == 0 else 0.75)) / 0.45)
        for j in range(idx + 1):
            if j == idx:
                img = self._card_img(key, ls, self.durs[key]) if ls > 0 else None
                self._draw_card(P, cam, j, img, pop_new, 0.0, True, ov, ghost=1 - ease_out(ls / 0.35))
            else:
                dim = 0.5 * (ease_out(lt / 0.5) if j == idx - 1 else 1.0) * (1 - ov)
                self._draw_card(P, cam, j, self._frozen_img(self.order[j]) if self._visible(cam, j) else None,
                                1.0, dim, False, ov)
        self._draw_edges(P, cam, t, idx, lt)
        self._hud(P, t, idx, lt)
        return P.img.resize((W, H), Image.LANCZOS).convert('RGB')

    @staticmethod
    def _visible(cam, j):
        cx, cy, s = cam
        x, y = _card_xy(j)
        return not ((x + CW - cx) * s + 640 < -40 or (x - cx) * s + 640 > W + 40 or
                    (y + CH - cy) * s + SCY < -40 or (y - cy) * s + SCY > H + 40)

    def _title(self, p, n, title, sub=''):
        p.text(60, 108, f'{n}  {title}', 26, ACCENT, 'lm', True)
        if sub:
            p.text(60 + p.tw(f'{n}  {title}', 26, True) + 18, 109, sub, 17, MUTED, 'lm')

    def _transform(self, p, t, n, title, sub, before, after, lab_b, lab_a, op, notes):
        self._title(p, n, title, sub)
        size, avail = 28, (400 if notes else 440)
        while True:
            lb, la = p.layout(before, size, 1090), p.layout(after, size, 1090)
            lh = size * 1.45
            hb, ha = 66 + len(lb) * lh, 66 + len(la) * lh
            if hb + ha + 90 <= avail or size <= 17:
                break
            size -= 2
        y0 = 125 + max(0, (avail - hb - ha - 90) / 2)
        y1 = y0 + hb + 90
        sm = SequenceMatcher(None, before, after, autojunk=False)
        cb, ca = [], []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != 'equal':
                cb += range(i1, i2); ca += range(j1, j2)
        rb, ra = {i: r for r, i in enumerate(cb)}, {i: r for r, i in enumerate(ca)}
        # thẻ trước
        p.rrect(60, y0, 1220, y0 + hb, r=16, fill=CARD, outline=CARD2, width=2)
        p.text(86, y0 + 24, lab_b, 15, MUTED, 'lm', True)

        def sb(i, c):
            if i in rb:
                pr = ease_out((t - 0.5 - 0.03 * min(rb[i], 25)) / 0.3)
                return (lerp_c(TEXT, (255, 200, 210), pr), 1.0, BAD, 0.34 * pr)
            return (TEXT, 1.0, None, 0)
        p.draw_layout(lb, 90, y0 + 60, size, sb, lh)
        # mũi tên + nhãn thao tác
        ya = y0 + hb + 45
        q = ease_out((t - 0.9) / 0.4)
        p.arrow(640, y0 + hb + 6, 640, y1 - 6, ACCENT, 3, alpha=q)
        p.chip(640, ya, op, 17, fill=(14, 60, 90), outline=ACCENT, color=ACCENT, scale=max(0.01, ease_back((t - 0.9) / 0.5)),
               alpha=q)
        if q > 0:
            yy = lerp(y0 + hb + 8, y1 - 8, (t * 0.9) % 1)
            if abs(yy - ya) > 20:
                p.ellipse(640, yy, 5, ACCENT, alpha=0.9 * q)
        # thẻ sau (hiện dần từ trái sang phải)
        p.rrect(60, y1, 1220, y1 + ha, r=16, fill=CARD, outline=(16, 100, 80) if ca else CARD2, width=2)
        p.text(86, y1 + 24, lab_a, 15, MUTED, 'lm', True)
        rev = len(after) * ease_io((t - 1.3) / 1.0)

        def sa(i, c):
            a = clamp(rev - i)
            if i in ca:
                pr = ease_back((t - 1.3 - 1.0 * i / max(1, len(after))) / 0.35)
                return (lerp_c(TEXT, (190, 255, 225), clamp(pr)), a, GOOD, 0.32 * clamp(pr) * a)
            return (TEXT, a, None, 0)
        p.draw_layout(la, 90, y1 + 60, size, sa, lh)
        if not ca and t > 1.4:
            p.chip(1090, y1 + 24, 'Không có thay đổi', 15, fill=CARD2, color=MUTED, alpha=ease_out((t - 1.4) / 0.3))
        # ghi chú các thao tác đã áp dụng
        cx, cy = 70, y1 + ha + 42
        for k, s_ in enumerate(notes):
            qq = ease_back((t - 2.5 - 0.22 * k) / 0.4)
            if qq <= 0:
                continue
            s2 = '✓ ' + s_
            w = p.tw(s2, 17) + 28
            if cx + w > 1220:
                cx, cy = 70, cy + 40
            p.chip(cx + w / 2, cy, s2, 17, fill=(16, 70, 60), color=GOOD, scale=qq, alpha=clamp(qq * 2))
            cx += w + 12

    def scene(self, p, t, dur, index):
        stage = self.tr['stages'][index]
        title = stage['title']
        self._title(p, index + 1, title)
        content = stage['content']
        if index == 1:
            self._transform(p, t, index + 1, title, '',
                            self.tr['stages'][0]['content'][:400], content[:400],
                            'Đầu vào', 'Sau chuẩn hóa', 'chuẩn hóa', [])
            return
        # Bound only the visual excerpt; the actual prediction always uses full text.
        excerpt = content[:700] + (' … [rút gọn hiển thị]' if len(content) > 700 else '')
        visible = min(len(excerpt), int(max(0, t) * 220))
        lines = p.layout(excerpt[:visible], 24, 1100)
        y = 175
        # draw_layout handles emoji and Vietnamese using the original renderer.
        p.draw_layout(lines[:7], 75, y, 24, lambda i, c: (TEXT, 1.0, None, 0), line_h=35)
        if 'Quyết định' in title or 'Encoder' in title:
            pulse = .5 + .5 * math.sin(t * 4)
            p.ellipse(640, 450, 48 + 9 * pulse, ACCENT, alpha=.15)
            p.rrect(505, 410, 775, 480, 18, fill=CARD2, outline=ACCENT)
            p.text(640, 445, self.tr['model'], 24, TEXT, 'mm', True)
        if title == 'Kết luận':
            toxic = content.split('\n')[0].strip().lower() == 'toxic'
            color = BAD if toxic else GOOD
            p.rrect(330, 380, 950, 470, 20, fill=CARD2, outline=color, width=3)
            p.text(640, 425, content.split('\n')[0], 36, color, 'mm', True)
        features = self.tr.get('features', []) if 'Đặc trưng' in title else []
        if features:
            peak = max(abs(f['value']) for f in features) or 1
            for j, f in enumerate(features[:5]):
                yy = 370 + j * 33
                p.text(75, yy, f['term'][:26], 18, MUTED)
                width = 650 * abs(f['value']) / peak * ease_out(t / 1.8)
                p.rrect(370, yy-10, 370+max(2,width), yy+10, 5, fill=ACCENT)
                p.text(1050, yy, format(f['value'], '.4g'), 18, TEXT)
        else:
            # Moving particles and expanding rings visualize flow, not token importance.
            for j in range(8):
                x = 100 + ((t * 180 + j * 140) % 1080)
                p.ellipse(x, 495, 5, ACCENT, alpha=.7)
            p.line(90, 495, 1170, 495, CARD2, 2)
        p.text(75, 590, 'Run: ' + str(self.tr['run'])[:90], 16, MUTED)


def render_trace_video(trace, path, progress=None, fps=24):
    import imageio.v2 as imageio
    renderer = _Renderer(trace)
    frames = int(math.ceil(renderer.total * fps))
    with imageio.get_writer(str(path), fps=fps, codec='libx264', quality=8,
                           pixelformat='yuv420p', macro_block_size=1) as writer:
        for i in range(frames):
            writer.append_data(np.asarray(renderer.frame(i / fps)))
            if progress and i % fps == 0:
                progress(int(100 * i / frames))
