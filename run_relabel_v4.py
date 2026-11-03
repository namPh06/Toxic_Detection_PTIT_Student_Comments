"""Run the local v4 migration with a mandatory semantic qualification gate."""
import json,time,subprocess,sys
from relabel_v4 import ROOT, OUT, MODEL, POLICY, SYSTEM, load, now
from semantic_labeling import request,SCHEMA,validate
from dataset import atomic_json

def qualify():
 cases=[
  ('Học phí đắt vcl.','','non-toxic'),
  ('Trường có phòng học xuống cấp.','','non-toxic'),
  ('Đừng gọi bạn ấy là đồ ngu.','','non-toxic'),
  ('Mày ngu thế, học làm gì.','','toxic'),
  ('Tao sẽ tìm đánh mày.','','toxic'),
  ('Nam nhưng muốn nụ hôn lốc xoáy kiểu Ấn Độ được không bản','Nữ free\nNam 1 nụ hôn lốc xoáy kiểu Pháp','non-toxic'),
  ('Em xin lịch thi với ạ.','','non-toxic'),
  ('Đồ ngốc :))','','uncertain'),
  ('Không nên xúc phạm bạn ấy, nhưng mày là đồ ngu.','','toxic'),
  ('Trường báo nghỉ muộn quá, tôi đã đến nơi rồi.','','non-toxic'),
 ]
 results=[]
 for text,post,expected in cases:
  schema={k:v for k,v in SCHEMA.items()}
  response=request('/api/chat',dict(model=MODEL,stream=False,keep_alive='10m',messages=[dict(role='system',content=SYSTEM+(ROOT/'QUY_TAC_GAN_NHAN.md').read_text(encoding='utf-8')+'\nFor this single item return label,category,evidence,reason only. Category must be insult/threat/hate/harassment for toxic, none for non-toxic, uncertain for uncertain.'),dict(role='user',content=json.dumps(dict(comment=text,post=post,parents=[]),ensure_ascii=False))],format=schema,options=dict(temperature=0,seed=42,num_ctx=8192,num_predict=512)),timeout=240)
  if not response.get('done') or response.get('done_reason')=='length':raise ValueError('Incomplete qualification response')
  answer=json.loads(response['message']['content'])
  if answer.get('label')!='toxic':answer['evidence']=[]
  answer=validate(answer,text)
  results.append(dict(text=text,expected=expected,answer=answer))
  print('Qualification',len(results),answer['label'],expected,flush=True)
 if any(r['expected']!=r['answer']['label'] and not ('nụ hôn' in r['text'] and r['answer']['label']=='uncertain') for r in results):raise ValueError('Semantic qualification failed: '+json.dumps(results,ensure_ascii=False))
 return dict(total=len(results),exact_matches=sum(r['expected']==r['answer']['label'] for r in results),conservative_abstentions=sum(r['expected']!=r['answer']['label'] for r in results),passed=True)

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 for _ in range(120):
  if any(m['name']==MODEL for m in request('/api/tags')['models']):break
  time.sleep(10)
 else:raise RuntimeError('Model download did not finish')
 request('/api/generate',dict(model='gemma3:4b',keep_alive=0,stream=False),timeout=30)
 qualification=load(OUT/'qualification.json') if (OUT/'qualification.json').exists() else qualify()
 if not qualification.get('passed') or qualification.get('model',MODEL)!=MODEL:raise ValueError('Invalid qualification gate')
 atomic_json(OUT/'qualification.json',dict(qualification,model=MODEL,policy_version=POLICY,checked_at=now(),note='Policy sanity checks only, not accuracy on the corpus'))
 subprocess.run([sys.executable,'-u',str(ROOT/'relabel_v4.py')],cwd=ROOT,check=True)
 subprocess.run([sys.executable,'-u',str(ROOT/'apply_relabel_v4.py')],cwd=ROOT,check=True)
if __name__=='__main__':
 try:main()
 except Exception as e:
  atomic_json(OUT/'job_error.json',dict(error=str(e),at=now(),active_data_unchanged=not (OUT/'applied.json').exists()))
  raise
