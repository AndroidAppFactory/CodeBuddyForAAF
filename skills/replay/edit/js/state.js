// ===== 状态管理 =====
let state = {
  data: null,           // 完整 JSON 数据
  events: [],           // 事件数组
  resolution: [1080, 2340],
  device: '',
  selectedIndex: -1,    // 当前选中事件索引
  multiSelected: new Set(), // 多选索引集合
  mode: 'select',       // select | draw
  scale: 1.0,          // 画布缩放
  isDirty: false,       // 是否有未保存修改
  sourceFile: '',       // 原始文件名（保存时用新名）
  screenshotDir: '',    // 截屏目录
  isPlaying: false,     // 是否正在模拟重放
  playIndex: -1,        // 当前重放到的事件索引
};

// 手机屏幕尺寸（CSS 像素）
const PHONE_W = 270;
const PHONE_H = 585;

// ===== 文件操作 =====

function handleFileSelect(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (ev) => {
    try {
      const data = JSON.parse(ev.target.result);
      loadData(data);
    } catch (err) {
      alert('JSON 解析失败: ' + err.message);
    }
  };
  reader.readAsText(file);
  e.target.value = '';
}

function loadData(data) {
  state.data = data;
  state.events = data.events || [];
  state.resolution = data.resolution || [1080, 2340];
  state.device = data.device || 'unknown';
  state.sourceFile = data.source_file || '';
  state.screenshotDir = data.screenshot_dir || '';
  state.selectedIndex = -1;
  state.multiSelected.clear();
  state.isDirty = false;
  state.isPlaying = false;
  state.playIndex = -1;

  const hasScreenshots = state.events.some(e => e.screenshots);
  document.getElementById('phone-info').textContent =
    `${state.device} · ${state.resolution[0]}×${state.resolution[1]}` +
    (hasScreenshots ? ' · 📸 含截屏' : '');
  
  // 截屏切换按钮初始隐藏，选中事件时才显示
  const switchEl = document.getElementById('screenshot-switch');
  if (switchEl) switchEl.style.display = 'none';

  // 初始化分辨率 Profile 选择器（flow edit 模式）
  initProfileSelector();

  updateStats();
  renderEventList();
  renderCanvas();
  showScreenshot(-1);
  updateStatusBar();
  updateStatistics();
}

function saveFile() {
  if (!state.events.length && !state.data) {
    alert('没有数据可保存');
    return;
  }

  // 保存时去掉 screenshots 字段，迁移旧 delay_ms 为 delay_before_ms
  const cleanEvents = state.events.map(ev => {
    const copy = {...ev};
    delete copy.screenshots;
    // 兼容迁移：旧 delay_ms → delay_before_ms
    if ('delay_ms' in copy && !('delay_before_ms' in copy)) {
      copy.delay_before_ms = copy.delay_ms;
    }
    delete copy.delay_ms;
    // 确保字段存在
    if (!('delay_before_ms' in copy)) copy.delay_before_ms = EVENT_DEFAULTS.delay_before_ms;
  if (!('delay_after_ms' in copy)) copy.delay_after_ms = getDelayAfterDefault(copy.type, copy.action);
    // 保留 is_critical（默认 false 时不写入以保持 JSON 简洁）
    if (!copy.is_critical) delete copy.is_critical;
    // 保留 capture_mode（默认 screenshot 时不写入）
    if (!copy.capture_mode || copy.capture_mode === 'screenshot') delete copy.capture_mode;
    return copy;
  });

  const output = {
    device: state.device || 'unknown',
    resolution: state.resolution,
    events: cleanEvents,
  };

  const jsonStr = JSON.stringify(output, null, 2);

  // 尝试 POST 到服务端保存（aaf replay edit 模式）
  const saveUrl = window.__REPLAY_DIR ? `/save?dir=${encodeURIComponent(window.__REPLAY_DIR)}` : '/save';
  fetch(saveUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: jsonStr,
  })
    .then(r => r.json())
    .then(data => {
      if (data.ok) {
        state.isDirty = false;
        alert('✅ 已保存到录制目录的 data.json');
      } else {
        throw new Error(data.error || '保存失败');
      }
    })
    .catch(err => {
      console.error('保存失败:', err);
      alert('❌ 保存失败：' + err.message + '\n请确认编辑服务正在运行');
    });
}

function saveFileAs() {
  if (!state.events.length && !state.data) {
    alert('没有数据可保存');
    return;
  }
  var newName = prompt('另存为（输入新录制名称）：', '');
  if (!newName || !newName.trim()) return;
  newName = newName.trim();

  // 构建干净的输出（同 saveFile 逻辑）
  var cleanEvents = state.events.map(function(ev) {
    var copy = {};
    for (var k in ev) {
      if (k === 'screenshots') continue;
      if (k === 'delay_ms' && !ev.delay_before_ms) {
        copy.delay_before_ms = ev.delay_ms;
        continue;
      }
      copy[k] = ev[k];
    }
    delete copy.delay_ms;
    if (!('delay_before_ms' in copy)) copy.delay_before_ms = 1000;
    if (!('delay_after_ms' in copy)) copy.delay_after_ms = 1000;
    if (!copy.is_critical) delete copy.is_critical;
    return copy;
  });

  var output = {
    device: state.device || 'unknown',
    resolution: state.resolution,
    events: cleanEvents,
  };

  fetch('/api/save-as', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({name: newName, device: output.device, resolution: output.resolution, events: output.events}),
  })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.ok) {
        state.isDirty = false;
        alert('✅ 已另存为: ' + data.name + '\n目录: ' + data.dir);
      } else {
        throw new Error(data.error || '另存失败');
      }
    })
    .catch(function(err) {
      console.error('另存失败:', err);
      alert('❌ 另存失败：' + err.message);
    });
}

// 更新状态栏信息
function updateStatusBar() {
  const statusIndicator = document.getElementById('status-indicator');
  const statusText = document.getElementById('status-text');
  const deviceInfo = document.getElementById('device-info');
  const resolutionInfo = document.getElementById('resolution-info');

  if (statusIndicator && statusText) {
    if (state.isPlaying) {
      statusIndicator.className = 'status-indicator playing';
      statusText.textContent = '正在重放中...';
    } else if (state.events.length > 0) {
      statusIndicator.className = 'status-indicator ready';
      statusText.textContent = `就绪 - ${state.events.length} 个事件`;
    } else {
      statusIndicator.className = 'status-indicator ready';
      statusText.textContent = '就绪';
    }
  }

  if (deviceInfo && resolutionInfo) {
    deviceInfo.textContent = `设备: ${state.device}`;
    resolutionInfo.textContent = `分辨率: ${state.resolution[0]}×${state.resolution[1]}`;
  }
}

// 更新统计信息
function updateStatistics() {
  const totalEvents = document.getElementById('total-events');
  const totalDuration = document.getElementById('total-duration');
  const eventTypes = document.getElementById('event-types');

  if (totalEvents && totalDuration && eventTypes) {
    // 计算总事件数
    totalEvents.textContent = state.events.length;

    // 计算总时长
    const totalMs = state.events.reduce((sum, event) => {
return sum + (event.delay_before_ms || event.delay_ms || 1000) + (event.delay_after_ms || 1000);
    }, 0);
    totalDuration.textContent = `${(totalMs / 1000).toFixed(1)}s`;

    // 统计事件类型分布
    const typeCount = {};
    state.events.forEach(event => {
      typeCount[event.type] = (typeCount[event.type] || 0) + 1;
    });
    
    const typeList = Object.entries(typeCount)
      .map(([type, count]) => `${type}(${count})`)
      .join(', ');
    
    eventTypes.textContent = typeList || '-';
  }
}

// 拖拽文件支持
document.addEventListener('dragover', (e) => { e.preventDefault(); });
document.addEventListener('drop', (e) => {
  e.preventDefault();
  const file = e.dataTransfer.files[0];
  if (file && file.name.endsWith('.json')) {
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        loadData(JSON.parse(ev.target.result));
      } catch (err) {
        alert('JSON 解析失败: ' + err.message);
      }
    };
    reader.readAsText(file);
  }
});

// ===== 分辨率 Profile 管理 =====

var currentProfileKey = '';
var deviceProfiles = {};

function initProfileSelector() {
  var sel = document.getElementById('profile-switch');
  var s = document.getElementById('profile-select');
  if (!sel || !s) return;

  deviceProfiles = window.__DEVICE_PROFILES || {};
  var defaultKey = window.__DEFAULT_PROFILE || '';
  var keys = Object.keys(deviceProfiles);

  sel.style.display = 'block';  // 始终显示，让用户可通过 + 按钮添加
  if (keys.length === 0) {
    s.style.display = 'none';   // 无 profile 时隐藏下拉框，但保留 + 按钮
    return;
  }

  s.style.display = '';
  s.innerHTML = '';
  keys.forEach(function(k) {
    var p = deviceProfiles[k];
    var label = k.replace('x', '×') + (p.device ? ' (' + p.device + ')' : '');
    s.innerHTML += '<option value="' + k + '"' + (k === defaultKey ? ' selected' : '') + '>' + label + '</option>';
  });
  currentProfileKey = defaultKey || keys[0];
}

function switchResolution(resKey) {
  if (!resKey || resKey === currentProfileKey) return;
  var parts = resKey.split('x');
  var newW = parseInt(parts[0]), newH = parseInt(parts[1]);
  if (!newW || !newH) return;

  var oldRes = state.resolution;
  state.resolution = [newW, newH];
  currentProfileKey = resKey;

  // 更新每个 event 的坐标
  state.events.forEach(function(ev) {
    var overrides = ev.overrides || {};
    if (overrides[resKey]) {
      // 该分辨率有 override，直接使用
      if (overrides[resKey].x !== undefined) ev.x = overrides[resKey].x;
      if (overrides[resKey].y !== undefined) ev.y = overrides[resKey].y;
    } else if (ev.x !== undefined) {
      // 无 override，等比缩放
      ev.x = Math.round(ev.x * newW / oldRes[0]);
      ev.y = Math.round(ev.y * newH / oldRes[1]);
    }
    // swipe 坐标同理
    if (overrides[resKey] && overrides[resKey].x1 !== undefined) {
      ev.x1 = overrides[resKey].x1; ev.y1 = overrides[resKey].y1;
      ev.x2 = overrides[resKey].x2; ev.y2 = overrides[resKey].y2;
    } else if (ev.x1 !== undefined) {
      ev.x1 = Math.round(ev.x1 * newW / oldRes[0]);
      ev.y1 = Math.round(ev.y1 * newH / oldRes[1]);
      ev.x2 = Math.round(ev.x2 * newW / oldRes[0]);
      ev.y2 = Math.round(ev.y2 * newH / oldRes[1]);
    }
  });

  state.isDirty = true;
  renderEventList();
  renderCanvas();
  var phoneInfo = document.getElementById('phone-info');
  if (phoneInfo) phoneInfo.textContent = (state.device || '') + ' · ' + state.resolution[0] + '×' + state.resolution[1];
}

var pendingProfileRes = '', pendingProfileDevice = '';

function addProfile() {
  document.getElementById('profile-modal').style.display = 'flex';
  document.getElementById('profile-paste').value = '';
  document.getElementById('profile-paste').focus();
  document.getElementById('profile-preview').style.display = 'none';
  document.getElementById('btn-confirm-profile').disabled = true;
  pendingProfileRes = '';
  pendingProfileDevice = '';
}

function parseProfilePaste() {
  var raw = document.getElementById('profile-paste').value;
  // 支持格式: "Pixel 6 Physical size: 1080x2400" 或直接 "1080x2400"
  var resM = raw.match(/(\d{3,5})\s*[x×X]\s*(\d{3,5})/);
  // 提取设备名：分辨率之前的非数字内容（排除 Physical size: 字样）
  var devM = raw.match(/^([\s\S]+?)\s*(?:Physical size:|\d{3,5}\s*[x×X])/);
  var preview = document.getElementById('profile-preview');
  var btn = document.getElementById('btn-confirm-profile');
  if (resM) {
    pendingProfileRes = resM[1] + 'x' + resM[2];
    pendingProfileDevice = devM ? devM[1].trim().replace(/\s+$/, '') : '';
    var name = pendingProfileDevice || '?';
    document.getElementById('profile-preview-res').textContent = name + ' · ' + resM[1] + '×' + resM[2];
    preview.style.display = 'block';
    btn.disabled = false;
  } else {
    pendingProfileRes = '';
    pendingProfileDevice = '';
    preview.style.display = 'none';
    btn.disabled = true;
  }
}

function closeProfileModal() {
  document.getElementById('profile-modal').style.display = 'none';
}

function confirmAddProfile() {
  if (!pendingProfileRes) return;
  var name = pendingProfileDevice;
  var parts = pendingProfileRes.split('x');
  var w = parts[0], h = parts[1];

  deviceProfiles[pendingProfileRes] = { device: name || '', source: 'adapted' };
  window.__DEVICE_PROFILES = deviceProfiles;

  var sel = document.getElementById('profile-select');
  sel.style.display = '';
  var label = w + '×' + h + (name ? ' (' + name + ')' : '');
  sel.innerHTML += '<option value="' + pendingProfileRes + '">' + label + '</option>';
  sel.value = pendingProfileRes;
  closeProfileModal();
  document.getElementById('profile-paste').value = '';
  switchResolution(pendingProfileRes);
}