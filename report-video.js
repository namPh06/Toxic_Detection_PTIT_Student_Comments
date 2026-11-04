(() => {
  const player = document.getElementById('report-video-player');
  const state = document.getElementById('report-video-state');
  const chapters = document.getElementById('report-video-chapters');
  const retry = document.getElementById('report-video-retry');
  if (!player) return;
  let current = null;
  async function update() {
    try {
      const response = await fetch('/api/system-report-video');
      if (!response.ok) throw new Error('Hãy khởi động lại công cụ để nạp chức năng video mới.');
      const data = await response.json();
      const job = data.job;
      const ready = data.ready;
      const progress = job && job.state === 'running' ? ` Đang dựng bản mới: ${job.progress}%.` : '';
      state.textContent = ready ? `Video: ${ready.run}.${data.stale ? ' Đây là bản trước; bản mới chưa sẵn sàng.' : ''}${progress}` :
        (progress || 'Chưa có video. Chọn Cập nhật video để dựng bản đầu tiên.');
      if (job && job.state === 'error') state.textContent += ` Dựng lỗi: ${job.error}. Bạn có thể thử lại; bản đã có vẫn phát được.`;
      retry.disabled = !!data.updating;
      if (ready && ready.id !== current) {
        current = ready.id;
        player.src = `/api/system-report-video.mp4?id=${encodeURIComponent(ready.id)}`;
        player.hidden = false;
        chapters.replaceChildren();
        ready.chapters.forEach(chapter => {
          const button = document.createElement('button');
          button.type = 'button'; button.className = 'button small';
          const seconds = Math.floor(chapter.start);
          button.textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')} · ${chapter.title}`;
          button.addEventListener('click', () => { player.currentTime = chapter.start; player.play().catch(() => {}); });
          chapters.append(button);
        });
      }
    } catch (error) { state.textContent = error.message; }
  }
  retry.addEventListener('click', async () => {
    retry.disabled = true;
    try {
      const response = await fetch('/api/system-report-video', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Không bắt đầu được lượt dựng video.');
      await update();
    } catch (error) { state.textContent = error.message; retry.disabled = false; }
  });
  update();
  setInterval(update, 5000);
})();
