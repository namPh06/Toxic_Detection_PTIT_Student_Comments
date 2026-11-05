"""Detailed report scenes on the original camera/graph animation engine."""
import math
import numpy as np
from backend.animation_renderer import (_Renderer, Painter, Image, BG, CARD, CARD2, TEXT, MUTED,
                                ACCENT, GOOD, BAD, WARN, ease_out, ease_io, clamp, _find_fonts)
from backend.system_report_video import NAMES


def probability_percent(value):
    """Keep small nonzero probabilities visible instead of rounding to zero."""
    if 0 < 1 - value < 1e-8:
        return '>99.999999%'
    return f'{value * 100:.8g}%'


def probability_comparison(ev):
    relation = '≥' if ev['score'] >= ev['threshold'] else '<'
    probability = probability_percent(ev['score'])
    approximation = '' if probability.startswith('>') else '≈ '
    return (f"P(toxic) {approximation}{probability} {relation} "
            f"ngưỡng {probability_percent(ev['threshold'])} → {ev['prediction'].upper()}")


def chapters(evidence):
    specs = [('intro', '1. Bài toán và dữ liệu', 12), ('raw', '2. Hai bình luận đầu vào', 12),
             ('clean', '3. Chuẩn hóa và teencode', 18), ('tokens', '4. Tách từ truyền thống', 16),
             ('bow', '5. Đặc trưng · BoW', 18), ('tfidf', '5. Đặc trưng · TF-IDF', 18),
             ('visofeatures', '6. Đặc trưng riêng của ViSoBERT', 24)]
    for name in NAMES:
        specs.append((f'learn:{name}', f'7. {name} · Mô hình học gì?', 24))
        for i in range(2):
            specs.append((f'model:{name}:{i}', f'7. {name} · Ví dụ {i + 1}', 28))
    for name in NAMES:
        specs.append((f'compare:{name}', '8. So sánh · ' + name, 8))
    specs.append(('end', '9. Kết luận chung', 16))
    result, now = [], 0
    for key, title, duration in specs:
        transition = 1.2 if key in ('intro', 'raw', 'clean', 'tokens', 'bow', 'end') or key.startswith('compare:BoW-NB') or key == 'model:BoW-NB:0' else .7
        result.append(dict(key=key, title=title, start=round(now, 3), duration=duration + transition, transition=transition))
        now += duration + transition
    return result


class ReportRenderer(_Renderer):
    def __init__(self, evidence):
        self.e = evidence
        self.cs = chapters(evidence)
        super().__init__(dict(model='PTIT · Báo cáo toàn hệ thống', stages=[dict(title=c['title'], content='') for c in self.cs]))
        self.timeline, now = [], 0
        for i, c in enumerate(self.cs):
            k = str(i)
            self.durs[k] = c['duration'] - c['transition']
            self.cstart[k] = c['transition']
            self.timeline.append((k, now, now + c['duration']))
            now += c['duration']
        self.total = now
        self.entries = {m['name']: m for m in evidence['metrics']['models']}
        self.edge_ops = ['đầu vào', 'chuẩn hóa', 'tách từ', 'đếm', 'trọng số', 'nhánh riêng'] + ['suy luận'] * max(0, len(self.cs) - 6)
        for i, c in enumerate(self.cs):
            self.caps[str(i)] = self.caption(c['key'])

    def caption(self, key):
        if key.startswith('learn:'):
            return 'Cấu hình từ lượt huấn luyện đã lưu · Học trên train; chọn cấu hình và ngưỡng bằng validation'
        if key.startswith('model:'):
            return 'Số liệu từ mô hình đã lưu · Trang 1: cơ chế; trang 2: tổng đầy đủ và quyết định'
        if key.startswith('compare:'):
            return f"Cùng test: {self.e['metrics']['split']['test']['count']} mẫu · Hàng = nhãn dataset, cột = dự đoán · Chọn bằng validation"
        return {'intro': 'Thu thập → làm sạch và nhãn → chia nhóm → đặc trưng → 5 mô hình → đánh giá',
                'raw': 'Giữ nguyên bản gốc để truy vết · Hai ví dụ cố định, không chọn theo kết quả dự đoán',
                'clean': 'Chuẩn hóa bảo toàn nghĩa · Không biến mọi chữ k thành không · Không xóa phủ định',
                'tokens': 'Underthesea dành cho NB/SVM · Không dùng bước này làm đầu vào ViSoBERT',
                'bow': 'Từ điển chỉ fit trên train · Vector thưa gồm cả nhánh từ và nhánh ký tự',
                'tfidf': 'Mỗi artifact giữ từ điển/IDF riêng · Không fit lại trên validation hoặc test',
                'visofeatures': 'Raw text → chuẩn hóa riêng → subword/ID/mask → embedding; không qua Underthesea',
                'end': 'Tổng hợp kết quả đánh giá và mô hình được chọn'}[key]

    def _camera(self, idx, lt):
        # Keep the original pan/zoom for chapters; a distinct slide/flip for subsections.
        c = self.cs[idx]
        if c['transition'] >= 1:
            return super()._camera(idx, lt)
        from backend.animation_renderer import _focus
        return _focus(idx), 0

    def _draw_card(self, p, cam, j, img, pop, dim, active, ov, ghost=0):
        if active and self.cs[j]['transition'] < 1 and img is not None:
            from backend.animation_renderer import CY0, CH, W
            # Sliding vector relay, or flip when switching representation.
            lt = getattr(self, '_local', 10)
            q = ease_out(lt / .7)
            if q < 1:
                layer = Image.new('RGBA', img.size, BG + (255,))
                if self.cs[j]['key'] == 'visofeatures':
                    w = max(1, int(img.width * max(.05, q)))
                    layer.paste(img.resize((w, img.height)), ((img.width-w)//2, 0))
                else:
                    layer.paste(img, (int((1-q)*W), 0))
                img = layer
        return super()._draw_card(p, cam, j, img, pop, dim, active, ov, ghost)

    def frame(self, t):
        c = next((c for c in self.cs if c['start'] <= t < c['start'] + c['duration']), self.cs[-1])
        self._local = t - c['start']
        return super().frame(t)

    def _hud(self, p, t, idx, lt):
        p.rrect(0, 0, 1280, 82, 0, fill=BG)
        groups = ['Dữ liệu','Raw','Chuẩn hóa','Tách từ','Đặc trưng','ViSoBERT','5 mô hình','So sánh','Kết luận']
        key = self.cs[idx]['key']
        active = 6 if key.startswith(('model:','learn:')) else 7 if key.startswith('compare:') else 8 if key=='end' else [0,1,2,3,4,4,5][idx]
        for j,title in enumerate(groups):
            x=100+j*135
            if j:p.line(x-110,29,x-25,29,ACCENT if j<=active else CARD2,2)
            p.ellipse(x,29,13,ACCENT if j==active else CARD2)
            p.text(x,29,str(j+1),14,BG if j==active else TEXT,'mm',True)
            p.text(x,57,title,14,TEXT if j==active else MUTED,'mm',j==active)
        p.rrect(40,74,1240,77,2,fill=CARD)
        p.rrect(40,74,40+max(4,1200*t/self.total),77,2,fill=ACCENT)
        p.rrect(40,633,1240,696,14,fill=CARD,outline=CARD2)
        caption=self.caps[str(idx)];size=23
        while p.tw(caption,size)>1140:size-=1
        p.text(640,665,caption,size,TEXT,'mm')

    def paragraph(self, p, text, x, y, width=1100, size=23, color=TEXT, maxlines=4):
        lines = p.layout(text, size, width)
        p.draw_layout(lines[:maxlines], x, y, size, lambda i,c:(color, 1, None, 0), line_h=size*1.45)

    def chips(self, p, tokens, t, y=270, color=ACCENT, limit=18):
        x, row = 75, y
        for i, token in enumerate(tokens[:limit]):
            token = str(token)[:24]
            w = min(340, p.tw(token, 20) + 28)
            if x+w > 1210:
                x, row = 75, row+51
            q = ease_out((t-i*.13)/.6)
            # Tokens physically travel from input to vector positions.
            p.chip(x+w/2, row-(1-q)*60, token, 20, outline=color, alpha=q)
            x += w+10

    def verdict(self, p, example, evidence, y=585):
        label = evidence['prediction']
        correct = label == example['label']
        color = BAD if label == 'toxic' else GOOD
        p.rrect(70, y-27, 1210, y+40, 12, fill=CARD2, outline=color, width=2)
        p.text(95, y+5, 'Dự đoán: ' + label.upper(), 25, color, bold=True)
        p.text(650, y+5, ('Trùng' if correct else 'KHÁC') + ' nhãn dataset: ' + example['label'], 20, GOOD if correct else WARN)

    def scene(self, p, t, dur, index):
        c = self.cs[index]
        key = c['key']
        p.text(65, 114, c['title'], 28, ACCENT, bold=True)
        e, m = self.e, self.e['metrics']
        if key == 'intro':
            p.text(75, 175, 'TỪ BÌNH LUẬN ĐẾN QUYẾT ĐỊNH', 34, TEXT, bold=True)
            values = [(3520, 'mẫu phát triển'), (981, 'toxic'), (2539, 'non-toxic'), (5, 'mô hình')]
            values[0] = (m['summary']['total'], 'mẫu phát triển')
            values[1] = (m['summary']['labels']['toxic'], 'toxic')
            values[2] = (m['summary']['labels']['non-toxic'], 'non-toxic')
            for j,(v,title) in enumerate(values):
                x=80+j*290
                p.rrect(x,230,x+265,355,15,fill=CARD2)
                p.text(x+22,275,str(round(v*ease_out(t/2))),38,ACCENT,bold=True)
                p.text(x+22,325,title,20,MUTED)
            split_titles = [f"{title} {m['split'][part]['count']}" for title,part in [('Train','train'),('Validation','validation'),('Test','test')]]
            for j,title in enumerate(split_titles):
                x=145+j*390
                p.chip(x+100,430,title,24,outline=GOOD if j==0 else ACCENT,alpha=ease_out((t-2-j*.6)/.5))
                if j<2:p.arrow(x+220,430,x+275,430,ACCENT)
            self.paragraph(p,'Train: học tham số · Validation: chọn cấu hình và ngưỡng · Test: đánh giá kết quả.',80,505,size=23)
        elif key in ('raw','clean'):
            for j, example in enumerate(e['examples']):
                yy=165+j*215
                p.chip(160,yy,'Ví dụ '+str(j+1)+' · '+example['label'],18,color=GOOD if j==0 else BAD)
                self.paragraph(p, example['display'],80,yy+32,size=25,maxlines=2)
                if key=='clean':
                    p.arrow(95,yy+99,95+100*ease_out(t/2),yy+99,ACCENT)
                    self.paragraph(p,example['cleaned'],225,yy+86,950,24,GOOD,maxlines=2)
                    p.text(225,yy+148,'Bản sạch NB/SVM · '+e['preprocess_version'],16,MUTED)
        elif key=='tokens':
            for j,ex in enumerate(e['examples']):
                p.text(75,170+j*200,'Ví dụ '+str(j+1)+' → từ ghép được nối bằng dấu _',21,MUTED)
                self.chips(p,ex['tokens'],t-j*.5,y=225+j*200,limit=14)
            p.text(75,583,'Giữ từ phủ định, emoji và từ mang nghĩa; chỉ loại stop words theo mã hiện tại.',20,WARN)
        elif key in ('bow','tfidf'):
            name = 'BoW-NB' if key=='bow' else 'TF-IDF-NB'
            ev=e['examples'][1]['models'][name]
            p.text(75,170,name+' · ví dụ 2 · '+str(ev['dimensions'])+' chiều, '+str(ev['nonzero'])+' khác 0',22,MUTED)
            p.text(75,212,'x[t] = số lần xuất hiện' if key=='bow' else 'idf = log((1 + n_train) / (1 + df)) + 1;  x = count × idf, chuẩn hóa L2',23,TEXT)
            for branch_index,branch in enumerate(ev['branches']):
                x=75+branch_index*590
                p.text(x,260,('TỪ / NGRAM' if branch['branch']=='word' else 'KÝ TỰ char_wb')+' · '+str(branch['dimensions'])+' chiều',21,ACCENT,bold=True)
                features=branch['features'][:6]
                peak=max((f['value'] for f in features),default=1) or 1
                for j,f in enumerate(features):
                    yy=310+j*42
                    p.text(x,yy,f['term'][:20],18,TEXT)
                    q=ease_out((t-1-j*.35)/1.2)
                    p.rrect(x+205,yy-9,x+207+190*f['value']/peak*q,yy+10,4,fill=ACCENT)
                    p.text(x+414,yy,format(f['value'],'.3g'),18,GOOD)
                if key=='tfidf' and features:
                    f=features[0]
                    p.text(x,585,f"Token đầu: count={f['count']}; idf={f['idf']:.3f}",18,WARN)
            p.text(75,617,'Hiển thị rút gọn; nhánh từ và ký tự được ghép, không chuẩn hóa L2 chung lần nữa.',16,MUTED)
        elif key=='visofeatures':
            ev=e['examples'][1]['models']['ViSoBERT']
            phase=int(t//6)%4
            labels=['RAW → CHUẨN HÓA RIÊNG','SUBWORD → TOKEN ID','ATTENTION MASK','EMBEDDING HỌC ĐƯỢC']
            p.text(75,174,labels[phase],25,WARN,bold=True)
            if phase==0:
                self.paragraph(p,e['examples'][1]['display'],80,235,size=29)
                p.arrow(150,345,1070,345,ACCENT)
                self.paragraph(p,ev['normalized'],80,400,size=29,color=GOOD)
            elif phase==1:
                self.chips(p,ev['tokens'],t%6,y=255,limit=12)
                p.text(75,420,'ID từ tokenizer đã lưu:',24,MUTED)
                self.chips(p,ev['ids'],t%6,y=480,color=WARN,limit=12)
            elif phase==2:
                self.chips(p,ev['mask'],t%6,y=270,color=GOOD,limit=16)
                self.paragraph(p,f"1 = token thật; 0 = padding. Ví dụ này có {len(ev['ids'])} token sau cắt, giới hạn {ev['max_length']}. Suy luận riêng một câu nên không thêm padding.",80,400,size=26)
            else:
                matrix=np.asarray(ev['embedding'])
                peak=max(abs(matrix).max(),.01)
                for a in range(matrix.shape[0]):
                    p.text(80,255+a*42,ev['tokens'][a][:12],19,MUTED)
                    for b in range(matrix.shape[1]):
                        v=matrix[a,b]; color=ACCENT if v>=0 else BAD
                        xx,yy=320+b*95,233+a*42
                        p.rrect(xx,yy,xx+85,yy+35,5,fill=color,alpha=.2+.7*abs(v)/peak)
                        p.text(xx+42,yy+18,f'{v:.2f}',16,TEXT,'mm')
                p.text(80,550,f"Trích 6 token × 8 chiều từ bảng word embedding; đủ {ev['hidden_size']} chiều/token.",21,WARN)
                p.text(80,585,'Encoder còn cộng embedding vị trí/loại token và chuẩn hóa trước self-attention.',20,MUTED)
        elif key.startswith('learn:'):
            name=key.split(':')[1]; entry=self.entries[name]
            params=entry['parameters']
            if name.endswith('NB'):
                lines=[f"Đầu vào: vector {entry['feature']} của nhánh từ và ký tự; nhãn train n/t.",
                       'Học prior = số câu mỗi lớp / số câu train; học phân bố đặc trưng trong từng lớp.',
                       f"Làm trơn α = {params['alpha']:g} tránh xác suất bằng 0 cho đặc trưng chưa gặp trong lớp.",
                       'Giả định các đặc trưng độc lập khi biết lớp; thực tế ngram có thể tương quan.',
                       'BoW dùng số đếm; TF-IDF-NB dùng trọng số không âm thay số đếm.',
                       'Cộng điểm log từng lớp → softmax → so ngưỡng chọn trên validation.']
            elif name.endswith('SVM'):
                lines=[f"Đầu vào: vector {entry['feature']} và nhãn train n/t.",
                       'LinearSVC học trọng số w và hệ số chặn b để phân tách hai lớp.',
                       f"C = {params['C']:g}; class_weight = {params.get('class_weight') or 'không'} (cấu hình chọn bằng validation).",
                       'Tối ưu: giảm lỗi biên phân loại, đồng thời kiểm soát độ lớn trọng số.',
                       'Suy luận f(x) = Σ w[i] × x[i] + b; đóng góp âm/dương không phải phiếu bầu.',
                       'f(x) ≥ ngưỡng: toxic; nhỏ hơn: non-toxic. Ngưỡng không nhất thiết bằng 0.']
            else:
                lines=['Đầu vào riêng: raw → chuẩn hóa nhẹ → subword → ID/mask → embedding.',
                       'Khởi tạo từ ViSoBERT tiền huấn luyện; học tiếp bằng nhãn train n/t.',
                       f"Chiến lược đã chạy: {params['fine_tuning']}; checkpoint epoch {params['best_epoch']}.",
                       'Self-attention kết hợp thông tin giữa các token trong chuỗi đầu vào.',
                       'Vector <s> cuối → dense/tanh → hai logits → softmax → so ngưỡng.',
                       'Checkpoint và ngưỡng chọn bằng validation; test chỉ dùng đánh giá.']
            for j,line in enumerate(lines):
                self.paragraph(p,line,80,186+j*67,1120,22,maxlines=2)
        elif key.startswith('model:'):
            _,name,j=key.split(':'); ex=e['examples'][int(j)]; ev=ex['models'][name]
            self.paragraph(p,ex['display'],80,158,1120,23,maxlines=2)
            if ev['kind']=='nb':self.nb(p,t,ev)
            elif ev['kind']=='svm':self.svm(p,t,ev)
            else:self.transformer(p,t,ev)
            if t>=14:self.verdict(p,ex,ev)
        elif key.startswith('compare:'):
            name=key.split(':')[1]; entry=self.entries[name]
            self.comparison(p,t,name,entry)
        elif key=='end':
            selected=m['selected_model']; entry=self.entries[selected]
            p.text(80,190,'MÔ HÌNH ĐƯỢC CHỌN: '+selected,35,GOOD,bold=True)
            p.text(80,247,f"Validation macro-F1: {entry['validation']['f1_macro']:.4f}  |  Test macro-F1: {entry['test']['f1_macro']:.4f}",26,ACCENT)
            for j,text in enumerate(['Chọn mô hình/ngưỡng bằng validation; test chỉ dùng báo cáo.',
                'Suy luận sử dụng mô hình được chọn theo kết quả validation.',
                'Bình luận đi qua bước chuẩn hóa và nhánh đặc trưng tương ứng.',
                'Điểm đầu ra được so với ngưỡng để phân loại toxic / non-toxic.',
                'So sánh kết quả bằng precision, recall, macro-F1 và ma trận nhầm lẫn.']):
                p.text(85,320+j*51,'• '+text,23,TEXT,alpha=ease_out((t-j*.8)/.6))
            p.text(80,603,e['run']+' · '+e['preprocess_version'],17,MUTED)

    def nb(self,p,t,ev):
        if t>=14:
            self.linear_decision(p,ev)
            return
        p.text(80,240,'L(c) = log prior(c) + Σ x[i] × log P(i|c)',26,WARN)
        p.text(80,279,f"P(i|c) = (tổng x[i] trong lớp c + α) / (tổng x trong c + α × D); α={ev['alpha']:g}",20,MUTED)
        p.text(80,320,'Đặc trưng',18,MUTED);p.text(630,320,'non-toxic',18,GOOD);p.text(900,320,'toxic',18,BAD)
        for i,term in enumerate(ev['terms'][:4]):
            yy=360+i*33;q=ease_out((t-1-i*.65)/.6)
            p.text(80,yy,term['term'][:28]+f"  x={term['value']:.3g}",18,TEXT)
            for j in range(2):
                value=term['contribution'][j]
                p.text(630+j*270,yy,f"× ({term['weight'][j]:.3f}) = {value*q:.3f}",18,GOOD if j==0 else BAD)
        p.text(80,505,'Mỗi ô = giá trị x[i] × log P(i|c); đây là đóng góp vào điểm log.',21,ACCENT)
        p.text(80,536,f"Trang 1/2 · {len(ev['terms'])} đặc trưng nổi bật; trang sau cộng đủ {ev['nonzero']} đặc trưng.",21,MUTED)

    def svm(self,p,t,ev):
        if t>=14:
            self.linear_decision(p,ev)
            return
        p.text(80,239,'f(x) = w · x + b = Σ w[i] × x[i] + intercept',25,WARN)
        terms=ev['terms'][:5]; peak=max((abs(v['contribution']) for v in terms),default=1) or 1
        for i,term in enumerate(terms):
            yy=295+i*40;value=term['contribution'];q=ease_out((t-1-i*.5)/.8)
            p.text(80,yy,term['term'][:23],18,TEXT)
            p.text(375,yy,f"{term['weight']:+.3f} × {term['value']:.3g}",17,MUTED)
            length=210*abs(value)/peak*q
            p.rrect(730-length if value<0 else 730,yy-10,730 if value<0 else 730+max(1,length),yy+10,4,fill=GOOD if value<0 else BAD)
            p.text(1010,yy,f'{value:+.4f}',19,TEXT)
        p.line(730,275,730,480,MUTED,1)
        p.text(80,503,'Đỏ: tăng điểm toxic; xanh: giảm điểm. Cộng độ lớn, không đếm số thanh.',22,ACCENT)
        p.text(80,534,f"Trang 1/2 · {len(terms)} đóng góp nổi bật; trang sau cộng b và {ev['remaining_count']} đặc trưng còn lại.",21,MUTED)

    def linear_decision(self,p,ev):
        p.text(80,230,'TRANG 2/2 · CỘNG ĐẦY ĐỦ → SO NGƯỠNG → KẾT LUẬN',24,WARN,bold=True)
        nb=ev['kind']=='nb'
        labels=['non-toxic','toxic'] if nb else ['Điểm SVM']
        for j,label in enumerate(labels):
            x=80+j*575
            p.text(x,278,label,23,GOOD if nb and j==0 else ACCENT,bold=True)
            lines=[('Log prior' if nb else 'Hệ số chặn b',ev['base'][j]),
                   (f"Tổng {len(ev['terms'])} đặc trưng đã chiếu",ev['shown_sum'][j]),
                   (f"Tổng {ev['remaining_count']} đặc trưng còn lại",ev['remainder'][j])]
            for i,(title,value) in enumerate(lines):
                p.text(x,320+i*38,f'{title}: {value:+.4f}',21,TEXT)
            p.text(x,442,f"Tổng đầy đủ = {ev['totals'][j]:+.4f}",25,ACCENT,bold=True)
        if nb:
            p.text(80,483,'P(toxic) = exp(L_t − log(exp(L_n) + exp(L_t)))',23,WARN)
            p.text(80,519,probability_comparison(ev),20,TEXT)
        else:
            relation='≥' if ev['score']>=ev['threshold'] else '<'
            p.text(80,486,f"f(x) = {ev['score']:+.4f} {relation} ngưỡng {ev['threshold']:+.4f} → {ev['prediction'].upper()}",25,WARN)
            p.text(80,523,'Ngưỡng chọn bằng validation; số hiển thị làm tròn, phép tính dùng đủ độ chính xác.',20,MUTED)

    def transformer(self,p,t,ev):
        if t>=14:
            p.text(80,232,'TRANG 2/2 · BIỂU DIỄN NGỮ CẢNH → ĐẦU PHÂN LOẠI',24,WARN,bold=True)
            self.paragraph(p,'Vector token đầu <s> từ encoder cuối → dense → tanh → out_proj → 2 logits. Dropout tắt khi suy luận.',80,280,size=24,maxlines=3)
            p.text(80,397,f"Logits [non-toxic, toxic] = [{ev['logits'][0]:+.4f}, {ev['logits'][1]:+.4f}]",25,ACCENT)
            p.text(80,443,'P(toxic) = exp(z_t) / (exp(z_n) + exp(z_t))',24,WARN)
            p.text(80,487,probability_comparison(ev),21,TEXT)
            p.text(80,529,'Ngưỡng quyết định lấy từ kết quả validation đã lưu.',20,MUTED)
            return
        p.text(80,234,f"{ev['layers']} encoder layers · {ev['heads']} attention heads · hidden {ev['hidden_size']}",24,WARN)
        for i in range(ev['layers']):
            x=90+(i%6)*185;y=305+(i//6)*90;q=ease_out((t-i*.38)/.7)
            p.rrect(x,y,x+148,y+62,10,fill=CARD2,outline=ACCENT,alpha=q)
            p.text(x+74,y+20,'Encoder '+str(i+1),18,TEXT,'mm',alpha=q)
            p.text(x+74,y+44,f"‖h‖ {ev['hidden_norms'][i+1]:.2f}",16,MUTED,'mm',alpha=q)
            if i%6<5:p.arrow(x+150,y+30,x+180,y+30,ACCENT,alpha=q)
            p.ellipse(x+((t*65)%145),y+60,3,GOOD,alpha=q)
        p.text(80,491,'Self-attention kết hợp thông tin giữa các token trong cùng đầu vào.',23,ACCENT)
        p.text(80,525,'‖h‖ là độ lớn vector, không phải điểm toxic hay mức quan trọng của token.',20,MUTED)
        p.text(80,548,'Trang 1/2 · Biểu diễn token qua các lớp encoder.',17,MUTED)

    def comparison(self,p,t,name,entry):
        for i,model in enumerate(NAMES):
            v=self.entries[model]['test']['f1_macro'];yy=200+i*57
            p.text(75,yy,model,22,TEXT if model==name else MUTED,bold=model==name)
            p.rrect(255,yy-13,255+max(2,420*v*ease_out(t/1.4)),yy+14,5,fill=GOOD if model==name else ACCENT,alpha=1 if model==name else .4)
            p.text(690,yy,f'{v:.4f}',21,TEXT)
        matrix=entry['test']['confusion_matrix'];peak=max(map(max,matrix))
        p.text(900,167,'Dự đoán n     t',19,MUTED)
        for a in range(2):
            p.text(800,240+a*100,'Nhãn '+('n' if a==0 else 't'),17,MUTED)
            for b in range(2):
                x,y=895+b*130,195+a*100
                p.rrect(x,y,x+115,y+88,10,fill=GOOD if a==b else BAD,alpha=.3+.6*matrix[a][b]/peak)
                p.text(x+57,y+44,str(matrix[a][b]),30,TEXT,'mm',True)
        values=entry['test']
        p.text(80,515,f"Accuracy {values['accuracy']:.4f}   Precision toxic {values['precision']:.4f}",25,ACCENT)
        p.text(80,556,f"Recall toxic {values['recall']:.4f}   F1 toxic {values['f1']:.4f}   Macro-F1 {values['f1_macro']:.4f}",25,TEXT)
        p.text(80,603,'★ Chọn theo validation: '+self.e['metrics']['selected_model'],20,WARN)


def render_report(evidence,path,progress=lambda value:None,fps=24):
    import imageio.v2 as imageio
    renderer=ReportRenderer(evidence)
    count=int(math.ceil(renderer.total*fps))
    with imageio.get_writer(str(path),fps=fps,codec='libx264',quality=7,pixelformat='yuv420p',
                           macro_block_size=1,ffmpeg_params=['-preset','veryfast','-movflags','+faststart']) as writer:
        for i in range(count):
            writer.append_data(np.asarray(renderer.frame(i/fps)))
            if i%fps==0:progress(20+int(79*i/count))
