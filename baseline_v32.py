"""Run four assignment baselines on human development labels only.
Usage: .venv/Scripts/python.exe baseline_v32.py
Results are grouped development CV, never an independent test claim.
"""
import json, hashlib, platform
from pathlib import Path
from collections import Counter
import numpy as np
import sklearn, joblib
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from dataset import atomic_json, prepare, text_hash
from experiments import metrics
from word_preprocessing import word_text, VERSION


def main():
    load=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    canonical_path='data/manual_review/canonical_development_v32_20261031.json'
    canonical=load(canonical_path)
    protected=['data/progress.json','data/workspace.json',canonical_path]
    hashes={p:sha(p) for p in protected}
    assert canonical['source_sha256']==hashes[protected[0]]
    assert canonical['workspace_sha256']==hashes[protected[1]]
    reserved=set(map(str,load('outputs/label_review_20261031/review_manifest.json')['reserved_post_ids']))
    rows=canonical['rows']
    assert len(rows)==946 and len({r['id'] for r in rows})==946
    assert all(r['human_verified'] and text_hash(r['text_raw'])==r['text_hash'] and str(r['post_id']) not in reserved for r in rows)
    # Connect development posts sharing normalized text, including unlabelled
    # duplicate copies. Reserved posts never enter feature fitting or CV.
    corpus=prepare(load(protected[0])['rows'])
    posts={str(r['post_id']) for r in corpus if str(r['post_id']) not in reserved}
    parent={p:p for p in posts}
    def root(p):
        while parent[p]!=p:
            parent[p]=parent[parent[p]];p=parent[p]
        return p
    seen={}
    for r in corpus:
        p=str(r['post_id'])
        if p not in posts or r['quality'] not in ('ready','duplicate'):continue
        for key in [('syllable',r['text_clean']),('word',word_text(r['text_raw']))]:
            if not key[1]:continue
            old=seen.setdefault(key,p);parent[root(p)]=root(old)
    x=np.array([word_text(r['text_raw']) for r in rows])
    y=np.array([int(r['reference_label']=='toxic') for r in rows])
    groups=np.array([root(str(r['post_id'])) for r in rows])
    folds=list(StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=42).split(x,y,groups))
    assert all(len(set(y[a]))==len(set(y[b]))==2 for a,b in folds)
    out=Path('outputs/baselines_v32_20261031');out.mkdir(parents=True,exist_ok=False)
    manifest=[]
    for a,b in folds:
        assert not set(groups[a]) & set(groups[b])
        assert not set(x[a]) & set(x[b])
        manifest.append(dict(train_ids=[rows[i]['id'] for i in a],validation_ids=[rows[i]['id'] for i in b],train_labels=dict(Counter(rows[i]['reference_label'] for i in a)),validation_labels=dict(Counter(rows[i]['reference_label'] for i in b))))
    atomic_json(out/'folds.json',manifest)
    atomic_json(out/'dataset.json',[dict(r,text_word=str(t),group=str(g)) for r,t,g in zip(rows,x,groups)])
    result=dict(scope='5-fold grouped development cross-validation; AI-assisted human labels; not independent test',policy=canonical['policy_version'],preprocess_version=VERSION,hashes=hashes,seed=42,versions=dict(python=platform.python_version(),sklearn=sklearn.__version__,pyvi='0.1.1'),counts=dict(Counter(r['reference_label'] for r in rows)),groups=len(set(groups)),models=[])
    for feature,vec in [('BoW',CountVectorizer),('TF-IDF',TfidfVectorizer)]:
        for algo in ['NB','SVM']:
            name=feature+'-'+algo;pred=np.full(len(y),-1);scores=[]
            def model():
                return Pipeline([('vectorizer',vec(tokenizer=str.split,token_pattern=None,lowercase=False,ngram_range=(1,2),max_features=20000)),('classifier',MultinomialNB(alpha=1) if algo=='NB' else LinearSVC(C=1,class_weight='balanced',random_state=42,max_iter=10000))])
            for a,b in folds:
                m=model();m.fit(x[a],y[a]);pred[b]=m.predict(x[b]);scores.append(metrics(y[b],pred[b]))
            assert np.all(pred>=0)
            result['models'].append(dict(name=name,fold_metrics=scores,mean_macro_f1=float(np.mean([s['f1_macro'] for s in scores])),oof=metrics(y,pred)))
            atomic_json(out/(name+'-oof.json'),[dict(id=r['id'],actual=r['reference_label'],predicted='toxic' if p else 'non-toxic') for r,p in zip(rows,pred)])
            m=model();m.fit(x,y);joblib.dump(m,out/(name+'.joblib'))
            assert np.array_equal(m.predict(x[:10]),joblib.load(out/(name+'.joblib')).predict(x[:10]))
            print(name,result['models'][-1]['oof'],flush=True)
    result['selected_by_development_cv']=max(result['models'],key=lambda m:m['mean_macro_f1'])['name']
    result['settings']=dict(ngram_range=[1,2],max_features=20000,nb_alpha=1,svm_C=1,svm_class_weight='balanced')
    result['protected_files_unchanged']=all(sha(p)==h for p,h in hashes.items())
    assert result['protected_files_unchanged']
    result['production_model_changed']=False
    atomic_json(out/'metrics.json',result)
    lines=['# Bốn cấu hình theo đề bài — 31/10/2026','', '946 nhãn phát triển do người dùng xác nhận (114 toxic, 832 non-toxic). Tách từ Pyvi 0.1.1 trước lọc stop words; giữ phủ định, emoji và văn bản gốc. Không dùng nhãn AI chưa xác nhận.', '', 'Đánh giá chéo 5 fold theo nhóm bài; nối các bài trùng văn bản. Cùng fold cho cả bốn cấu hình. Vectorizer chỉ fit trên phần train mỗi fold. Không dùng 119 bài giữ riêng để học hoặc chọn mô hình. Đây là kết quả phát triển trên nhãn có hỗ trợ AI, không phải test độc lập hay độ chính xác toàn corpus.', '', '| Cấu hình | Accuracy OOF | Precision toxic | Recall toxic | F1 toxic | Macro-F1 OOF | Macro-F1 trung bình fold |','|---|---:|---:|---:|---:|---:|---:|']
    for m in result['models']:
        z=m['oof'];lines.append('| '+m['name']+' | '+' | '.join(f"{z[k]:.4f}" for k in ['accuracy','precision','recall','f1','f1_macro'])+f" | {m['mean_macro_f1']:.4f} |")
    lines+=['','Ứng viên theo macro-F1 trung bình fold: '+result['selected_by_development_cv']+'. Chưa thay mô hình tự động trong ứng dụng. Chỉ số đã dùng chọn ứng viên nên cần tập test độc lập mới trước kết luận chất lượng.', '', 'Confusion matrix: hàng thật, cột dự đoán; thứ tự non-toxic, toxic.']
    for m in result['models']:lines.append(m['name']+': '+str(m['oof']['confusion_matrix']))
    lines+=['', 'Giới hạn: nhãn phát triển chọn lọc, mất cân bằng và đã được AI hỗ trợ; chưa kiểm chứng mù. Quy tắc chê trường là toxic là tiêu chí riêng của dự án, có ngoại lệ góp ý đã chốt. Pyvi tách từ, không tự giải quyết ngữ cảnh hay xác định toxic.', '', 'Tiếp theo: tạo/chốt nhãn test độc lập, kiểm tra chéo, khóa trước dự đoán; đánh giá ứng viên rồi hoàn thiện báo cáo. Các file joblib là ứng viên nghiên cứu fit toàn bộ 946 nhãn, không dùng chúng để tự đánh giá lại trên 946 câu.', '', 'Tài liệu tách từ: https://github.com/trungtv/pyvi']
    (out/'BAO_CAO.md').write_text('\n'.join(lines),encoding='utf8')
    print('DONE',result['selected_by_development_cv'])

if __name__=='__main__':main()
