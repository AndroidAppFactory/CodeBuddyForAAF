// ===== 实时录制模式（仅 adb 平台）=====
if ((window.__FLOW_PLATFORM || 'adb') !== 'adb') {
  window.startLive = window.stopLive = function(){};
} else {

let liveEventSource = null;
let liveEventCount = 0;
let liveResolution = [1080, 2340];

function initLiveMode() {
    liveResolution = window.__RESOLUTION || [1080, 2340];
    state.resolution = liveResolution;
    state.isLiveMode = true;

    // 替换重放控制区为录制状态条
    const replaySection = document.querySelector('.replay-section');
    if (replaySection) {
        replaySection.innerHTML = `
            <div style="display:flex;align-items:center;gap:12px;padding:8px 12px;background:rgba(231,76,60,0.1);border:1px solid rgba(231,76,60,0.3);border-radius:8px;">
                <span style="font-size:20px;animation:live-pulse 1s infinite;">🔴</span>
                <span style="font-weight:600;color:#e74c3c;">录制中</span>
                <span id="live-count" style="color:#aaa;font-size:14px;">0 个事件</span>
                <span style="flex:1"></span>
                <button onclick="stopRecording()" style="background:#e74c3c;color:#fff;border:none;padding:6px 16px;border-radius:6px;cursor:pointer;font-size:14px;">⏹ 停止</button>
            </div>`;
    }

    state.events = [];
    state.device = 'live';
    state.resolution = liveResolution;
    updateStats();
    renderEventList();

    // 注入实时模式样式
    const style = document.createElement('style');
    style.setAttribute('data-live', 'true');
    style.textContent = `
        @keyframes live-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
        @keyframes live-ripple { 0% { transform: scale(0.3); opacity: 0.8; } 100% { transform: scale(2); opacity: 0; } }
        .live-ripple { position: absolute; width: 40px; height: 40px; border-radius: 50%; border: 3px solid #e74c3c; animation: live-ripple 0.8s ease-out forwards; pointer-events: none; }
        .live-swipe-svg { position: absolute; top: 0; left: 0; pointer-events: none; opacity: 0.8; transition: opacity 1s; }
    `;
    document.head.appendChild(style);

    connectSSE();
}

function connectSSE() {
    liveEventSource = new EventSource('/api/stream');
    liveEventSource.onmessage = handleLiveMessage;
    liveEventSource.onerror = function() {
        if (liveEventSource.readyState === EventSource.CLOSED) return;
        setTimeout(() => {
            if (liveEventSource && liveEventSource.readyState !== EventSource.CLOSED) {
                connectSSE();
            }
        }, 2000);
    };
}

function handleLiveMessage(e) {
    const msg = JSON.parse(e.data);
    switch (msg.type) {
        case 'event': handleLiveEvent(msg); break;
        case 'screen': handleLiveScreen(msg); break;
        case 'done': handleRecordingDone(msg.data); break;
    }
}

function handleLiveScreen(msg) {
    if (!msg.data) return;
    const screen = document.getElementById('phone-screen');
    if (screen) {
        screen.style.backgroundImage = `url(data:image/png;base64,${msg.data})`;
        screen.style.backgroundSize = '100% 100%';
        screen.style.backgroundPosition = 'center';
        screen.style.backgroundRepeat = 'no-repeat';
    }
}

function handleLiveEvent(msg) {
    const ev = msg.data;
    const idx = msg.index !== undefined ? msg.index : state.events.length;
    state.events.push(ev);
    liveEventCount = idx + 1;

    const countEl = document.getElementById('live-count');
    if (countEl) countEl.textContent = `${liveEventCount} 个事件`;

    state.selectedIndex = state.events.length - 1;
    updateStats();
    renderEventList();
    renderCanvas();

    // 恢复实时模式 UI：关闭编辑面板、隐藏截图切换栏
    // （用户可能点击了历史步骤打开了这些面板）
    const editPanel = document.getElementById('edit-panel');
    if (editPanel) editPanel.style.display = 'none';
    const editEmpty = document.getElementById('edit-empty');
    if (editEmpty) editEmpty.style.display = 'block';
    const ssSwitch = document.getElementById('screenshot-switch');
    if (ssSwitch) ssSwitch.style.display = 'none';

    const list = document.getElementById('event-list');
    if (list) list.scrollTop = list.scrollHeight;

    drawLiveAnimation(ev);
}

function drawLiveAnimation(ev) {
    const overlay = document.getElementById('phone-overlay');
    if (!overlay) return;

    const frame = document.getElementById('phone-frame');
    const fw = frame ? frame.clientWidth : 270;
    const fh = frame ? frame.clientHeight : 585;
    const scaleX = fw / state.resolution[0];
    const scaleY = fh / state.resolution[1];

    if (ev.type === 'tap') {
        const x = ev.x * scaleX;
        const y = ev.y * scaleY;
        const ripple = document.createElement('div');
        ripple.className = 'live-ripple';
        ripple.style.left = (x - 20) + 'px';
        ripple.style.top = (y - 20) + 'px';
        overlay.appendChild(ripple);
        setTimeout(() => ripple.remove(), 800);
    } else if (ev.type === 'swipe') {
        const x1 = ev.x1 * scaleX, y1 = ev.y1 * scaleY;
        const x2 = ev.x2 * scaleX, y2 = ev.y2 * scaleY;

        const svgNS = 'http://www.w3.org/2000/svg';
        const svg = document.createElementNS(svgNS, 'svg');
        svg.classList.add('live-swipe-svg');
        svg.setAttribute('width', fw);
        svg.setAttribute('height', fh);

        const defs = document.createElementNS(svgNS, 'defs');
        const marker = document.createElementNS(svgNS, 'marker');
        marker.setAttribute('id', 'live-arrow');
        marker.setAttribute('markerWidth', '10');
        marker.setAttribute('markerHeight', '7');
        marker.setAttribute('refX', '8');
        marker.setAttribute('refY', '3.5');
        marker.setAttribute('orient', 'auto');
        const polygon = document.createElementNS(svgNS, 'polygon');
        polygon.setAttribute('points', '0 0, 10 3.5, 0 7');
        polygon.setAttribute('fill', '#e74c3c');
        marker.appendChild(polygon);
        defs.appendChild(marker);

        const line = document.createElementNS(svgNS, 'line');
        line.setAttribute('x1', x1);
        line.setAttribute('y1', y1);
        line.setAttribute('x2', x2);
        line.setAttribute('y2', y2);
        line.setAttribute('stroke', '#e74c3c');
        line.setAttribute('stroke-width', '3');
        line.setAttribute('marker-end', 'url(#live-arrow)');

        svg.appendChild(defs);
        svg.appendChild(line);
        overlay.appendChild(svg);
        setTimeout(() => { svg.style.opacity = '0'; }, 1000);
        setTimeout(() => svg.remove(), 2000);
    }
}

function stopRecording() {
    fetch('/api/stop', { method: 'POST' })
        .then(r => r.json())
        .then(d => { if (d.ok) console.log('停止请求已发送'); })
        .catch(e => console.error('停止失败:', e));
}

function handleRecordingDone(data) {
    if (liveEventSource) { liveEventSource.close(); liveEventSource = null; }
    const eventCount = data.events || liveEventCount;

    const replaySection = document.querySelector('.replay-section');
    if (replaySection) {
        replaySection.innerHTML = `
            <div style="display:flex;align-items:center;gap:12px;padding:8px 12px;background:rgba(102,187,106,0.1);border:1px solid rgba(102,187,106,0.3);border-radius:8px;">
                <span style="font-size:20px;">✅</span>
                <span style="font-weight:600;color:#66bb6a;">录制完成</span>
                <span style="color:#aaa;font-size:14px;">${state.events.length} 个事件</span>
            </div>`;
    }

    syncEventsToBackend().then(() => {
        showDoneModal(state.events.length);
    }).catch(err => {
        console.error('同步事件失败:', err);
        showDoneModal(state.events.length);
    });
}

function syncEventsToBackend() {
    const cleanEvents = state.events.map(ev => {
        const copy = {...ev};
        delete copy.screenshots;
        delete copy.__live_screenshot;
        if ('delay_ms' in copy && !('delay_before_ms' in copy)) {
            copy.delay_before_ms = copy.delay_ms;
        }
        delete copy.delay_ms;
        if (!('delay_before_ms' in copy)) copy.delay_before_ms = 5000;
        if (!('delay_after_ms' in copy)) copy.delay_after_ms = 5000;
        if (!copy.is_critical) delete copy.is_critical;
        if (!copy.capture_mode || copy.capture_mode === 'screenshot') delete copy.capture_mode;
        return copy;
    });
    const output = {
        device: state.device || 'live',
        resolution: state.resolution,
        events: cleanEvents,
    };
    return fetch('/api/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(output),
    }).then(r => r.json());
}

function showDoneModal(eventCount) {
    const existing = document.getElementById('live-done-modal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'live-done-modal';
    modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;z-index:10000;';
    modal.innerHTML = `
        <div style="background:#1a1a2e;border:1px solid #2a2a4a;border-radius:16px;padding:32px;min-width:400px;text-align:center;">
            <div style="font-size:48px;margin-bottom:12px;">✅</div>
            <h2 style="color:#e0e0e0;margin-bottom:8px;">录制完成</h2>
            <p style="color:#8899aa;margin-bottom:24px;">共 ${eventCount} 个事件</p>
            <div style="display:flex;flex-direction:column;gap:12px;">
                <button onclick="enterEditMode()" style="background:#4fc3f7;color:#000;border:none;padding:12px 24px;border-radius:8px;cursor:pointer;font-size:15px;font-weight:600;">✏️ 进入编辑模式</button>
                <button onclick="rerRecord()" style="background:#2a2a4a;color:#e0e0e0;border:1px solid #3a3a5a;padding:12px 24px;border-radius:8px;cursor:pointer;font-size:15px;">🔄 重新录制</button>
                <button onclick="closeAndSave()" style="background:transparent;color:#8899aa;border:none;padding:12px 24px;cursor:pointer;font-size:14px;">💾 已保存，关闭</button>
            </div>
        </div>`;
    document.body.appendChild(modal);
}

function enterEditMode() {
    const modal = document.getElementById('live-done-modal');
    if (modal) modal.remove();
    state.isLiveMode = false;

    const replaySection = document.querySelector('.replay-section');
    if (replaySection) {
        replaySection.innerHTML = `
            <div class="replay-controls-compact">
                <button id="btn-play" onclick="toggleReplay()" class="control-btn primary">▶️ 重放</button>
                <div class="control-row">
                    <label>间隔</label>
                    <input id="replay-delay" type="number" value="500" min="0" max="10000" step="100">
                    <span>ms</span>
                </div>
                <div class="phone-zoom-controls">
                    <button onclick="zoomOut()" class="zoom-btn">🔍−</button>
                    <span id="zoom-level">100%</span>
                    <button onclick="zoomIn()" class="zoom-btn">🔍+</button>
                </div>
            </div>`;
    }

    const liveStyle = document.querySelector('style[data-live]');
    if (liveStyle) liveStyle.remove();

    renderEventList();
    renderCanvas();
}

function rerRecord() {
    window.location.reload();
}

function closeAndSave() {
    const modal = document.getElementById('live-done-modal');
    if (modal) modal.remove();
    const replaySection = document.querySelector('.replay-section');
    if (replaySection) {
        replaySection.innerHTML = `
            <div style="padding:16px;text-align:center;color:#8899aa;">
                💾 录制已保存到 data.json<br>可关闭此页面
            </div>`;
    }
}

} // 平台守卫结束

if (window.__LIVE_MODE) {
    document.addEventListener('DOMContentLoaded', initLiveMode);
}
