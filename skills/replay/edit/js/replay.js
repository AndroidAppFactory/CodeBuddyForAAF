// ===== 模拟重放（仅 adb 平台）=====
if ((window.__FLOW_PLATFORM || 'adb') !== 'adb') {
  window.toggleReplay = function(){};
} else {

let replayTimer = null;

function toggleReplay() {
  if (state.isPlaying) {
    stopReplay();
  } else {
    startReplay();
  }
}

function startReplay() {
  if (!state.events.length) {
    alert('没有事件可重放');
    return;
  }

  state.isPlaying = true;
  state.playIndex = 0;
  state.selectedIndex = -1;

  const btn = document.getElementById('btn-play');
  btn.textContent = '⏹️ 停止';
  btn.classList.add('active');

  // 隐藏截屏切换按钮
  const switchEl = document.getElementById('screenshot-switch');
  if (switchEl) switchEl.style.display = 'none';
  document.getElementById('edit-panel').style.display = 'none';

  // 重放时保持当前缩放下的手机框尺寸不变，由 applyZoom() 统一管理

  const frame = document.getElementById('phone-frame');

  // 显示重放信息条
  let infoBar = document.getElementById('replay-info');
  if (!infoBar) {
    infoBar = document.createElement('div');
    infoBar.id = 'replay-info';
    infoBar.style.cssText = 'margin-top:12px;padding:8px 16px;background:#1a3e2e;border:1px solid #27ae60;border-radius:8px;color:#eee;font-size:13px;text-align:center;min-width:300px';
    frame.parentNode.insertBefore(infoBar, frame.nextSibling);
  }
  infoBar.style.display = 'block';
  infoBar.textContent = '准备重放...';

  playNextEvent();
}

function stopReplay() {
  state.isPlaying = false;
  state.playIndex = -1;

  if (replayTimer) {
    clearTimeout(replayTimer);
    replayTimer = null;
  }

  const btn = document.getElementById('btn-play');
  btn.textContent = '▶️ 模拟重放';
  btn.classList.remove('active');

  // 手机框尺寸由 applyZoom() 统一管理，不手动恢复

  // 恢复截屏切换按钮（如果有截屏数据）
  const switchEl = document.getElementById('screenshot-switch');
  if (switchEl) switchEl.style.display = 'none';

  // 隐藏重放信息条
  const infoBar = document.getElementById('replay-info');
  if (infoBar) infoBar.style.display = 'none';

  renderEventList();
  renderCanvas();
  showScreenshot(-1);
  // 清除手机屏幕背景和视频
  clearPhoneMedia();
  // 恢复 canvas 显示
  document.getElementById('phone-canvas').style.opacity = '1';
}

function playNextEvent() {
  if (!state.isPlaying || state.playIndex >= state.events.length) {
    stopReplay();
    return;
  }

  const ev = state.events[state.playIndex];
  const index = state.playIndex;

  // 更新重放信息条
  const infoBar = document.getElementById('replay-info');
  if (infoBar) {
    let desc = '';
    if (ev.type === 'tap') {
      desc = `tap(${ev.x}, ${ev.y})`;
    } else if (ev.type === 'swipe') {
desc = `swipe(${ev.x1},${ev.y1} → ${ev.x2},${ev.y2}, ${ev.duration_ms}ms)`;
    } else if (ev.type === 'adb') {
      desc = ev.action === 'wifi-connect' ? `WiFi: ${ev.ssid || ''}` : ev.action === 'lock-screen' ? '🔒 锁屏' : `adb: ${ev.action || ev.command || ''}`;
    } else if (ev.type === 'tips') {
      desc = `💡 ${ev.content || ''}`;
    } else {
      desc = ev.type;
    }
  const delayBeforeMs = ev.delay_before_ms || ev.delay_ms || EVENT_DEFAULTS.delay_before_ms;
  const delayAfterMs = ev.delay_after_ms || getDelayAfterDefault(ev.type, ev.action);
  const db = delayBeforeMs >= 1000 ? (delayBeforeMs / 1000).toFixed(1) + 's' : delayBeforeMs + 'ms';
  const da = delayAfterMs >= 1000 ? (delayAfterMs / 1000).toFixed(1) + 's' : delayAfterMs + 'ms';
    infoBar.textContent = `▶ ${index + 1}/${state.events.length}  ${desc}  前+${db}${ev.delay_after_ms ? ' 后+' + da : ''}`;
  }

  // 高亮当前事件
  renderEventList();
  renderCanvas();

  // 高亮当前播放项
  const items = document.querySelectorAll('.event-item');
  if (items[index]) {
    items[index].classList.add('playing');
    items[index].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  // 重放间隔从界面输入框读取（毫秒）
  const delayMs = parseInt(document.getElementById('replay-delay').value) || 500;
  const delay = delayMs;
  const canvas = document.getElementById('phone-canvas');
  const ss = ev.screenshots || {};
  const hasVideo = ss.before_type === 'video' || ss.after_type === 'video';

  // 阶段1：显示行为前截图/录屏，隐藏路径
  canvas.style.opacity = '0';
  currentScreenshotView = 'before';
  showScreenshot(index);

  // 阶段2：delay 后展示行为路径（视频模式下延长等待）
  const phase2Delay = hasVideo && ss.before_type === 'video' ? Math.max(delay, 2000) : delay;
  setTimeout(() => {
    if (!state.isPlaying) return;
    clearPhoneMedia();
    canvas.style.opacity = '1';
    renderCanvas();
  }, phase2Delay);

  // 阶段3：再 delay 后显示行为后截图/录屏，隐藏路径
  setTimeout(() => {
    if (!state.isPlaying) return;
    canvas.style.opacity = '0';
    currentScreenshotView = 'after';
    showScreenshot(index);
  }, phase2Delay + delay);

  // 进入下一个事件（后截图/录屏展示后）
  const phase4Delay = hasVideo && ss.after_type === 'video' ? Math.max(delay, 2000) : delay;
  replayTimer = setTimeout(() => {
    if (!state.isPlaying) return;
    state.playIndex++;
    // 最后一步：停留在后截图，不清除画面
    if (state.playIndex >= state.events.length) {
      state.isPlaying = false;
      state.playIndex = -1;
      if (replayTimer) {
        clearTimeout(replayTimer);
        replayTimer = null;
      }
      const btn = document.getElementById('btn-play');
      btn.textContent = '▶️ 模拟重放';
      btn.classList.remove('active');
      // 恢复工具栏和面板显示
      document.querySelectorAll('.phone-panel .toolbar').forEach(tb => {
        tb.style.display = '';
      });
      // 手机框尺寸由 applyZoom() 统一管理，不手动恢复
      const infoBar = document.getElementById('replay-info');
      if (infoBar) infoBar.textContent = '✅ 重放完成（停留在最后一步截图）';
      return;
    }
    playNextEvent();
  }, phase2Delay + delay + phase4Delay);
}

} // 平台守卫结束

// showScreenshot / showScreenshotBefore / showScreenshotAfter 定义在 shortcuts.js 中
