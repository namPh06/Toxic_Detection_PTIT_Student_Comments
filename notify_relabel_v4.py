"""Show a local Windows notification after the v4 migration commits."""
import ctypes,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'outputs/relabel_v4_20261102'
def main():
 marker=OUT/'notification_shown.json'
 if marker.exists():return
 error=OUT/'job_error.json'
 initial_error=error.stat().st_mtime_ns if error.exists() else None
 while True:
  applied=OUT/'applied.json'
  if applied.exists():
   try:r=json.loads(applied.read_text(encoding='utf-8-sig'))
   except (OSError,ValueError):time.sleep(10);continue
   labels=r.get('labels',{})
   message=f"Đã hoàn tất gán lại nhãn v4.\nTổng đã xét: {r['total']}\nMẫu dùng được: {r['usable']}\nToxic: {labels.get('toxic',0)}\nNon-toxic: {labels.get('non-toxic',0)}\nĐã loại khỏi nguồn đang dùng: {r['removed_from_active']}\n\nJSON/CSV đã cập nhật. Nhãn tự động chưa bảo đảm đúng tuyệt đối.\nChi tiết: outputs/relabel_v4_20261102/KET_QUA.md"
   marker.write_text(json.dumps({'status':'completed','at':time.time()}),encoding='utf-8')
   ctypes.windll.user32.MessageBoxW(None,message,'Gán nhãn v4 hoàn tất',0x40|0x10000)
   return
  if error.exists() and error.stat().st_mtime_ns!=initial_error:
   try:r=json.loads(error.read_text(encoding='utf-8-sig'))
   except (OSError,ValueError):time.sleep(10);continue
   ctypes.windll.user32.MessageBoxW(None,'Tiến trình gán nhãn v4 đã dừng vì lỗi. Chưa xác nhận hoàn tất.\n'+str(r.get('error',''))[:600],'Cần kiểm tra gán nhãn v4',0x30|0x10000)
   return
  time.sleep(10)
if __name__=='__main__':main()
