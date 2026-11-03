"""Wait for full inference, validate policy fixtures, then commit atomically per file."""
import time, json, subprocess, sys
from pathlib import Path
from relabel_v4 import OUT, ROOT, load, SYSTEM, POLICY
from semantic_labeling import request, validate, SCHEMA
started=time.time()
while time.time()-started<86400:
 try:
  status=load(OUT/'status.json')
  if status.get('classification_complete'):
   cases=[('Học phí đắt vcl.','non-toxic'),('Trường có phòng học xuống cấp.','non-toxic'),('Đừng gọi bạn ấy là đồ ngu.','non-toxic'),('Mày ngu thế, học làm gì.','toxic'),('Tao sẽ tìm đánh mày.','toxic')]
   checks=[]
   for text,expected in cases:
    from semantic_labeling import SYSTEM as SINGLE_SYSTEM
    response=request('/api/chat',dict(model='gemma3:4b',stream=False,messages=[dict(role='system',content=SINGLE_SYSTEM+'\n'+(ROOT/'QUY_TAC_GAN_NHAN.md').read_text(encoding='utf-8')),dict(role='user',content=json.dumps(dict(comment=text,post='',parents=[]),ensure_ascii=False))],format=SCHEMA,options=dict(temperature=0,num_ctx=8192,num_predict=400)),timeout=240)
    answer=json.loads(response['message']['content']);validate(answer,text);checks.append(dict(text=text,expected=expected,actual=answer['label']))
   from dataset import atomic_json
   atomic_json(OUT/'policy_checks.json',checks)
   if any(c['expected']!=c['actual'] for c in checks):raise ValueError('Policy fixtures failed; refusing to overwrite active data')
   result=subprocess.run([sys.executable,str(ROOT/'apply_relabel_v4.py')],cwd=ROOT,check=True)
   break
 except FileNotFoundError:pass
 except Exception as e:
  (OUT/'apply_error.txt').write_text(str(e),encoding='utf-8');raise
 time.sleep(15)
