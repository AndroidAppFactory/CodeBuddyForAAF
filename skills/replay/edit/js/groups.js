// ===== Group 编排（收藏夹引用组合） =====
// 完整的可视化编排界面：拖拽排序、重复添加、逐步配置

// ─── API ───────────────────────────────────────────

async function loadGroups() {
  try {
    const resp = await fetch('/api/groups');
    if (!resp.ok) return [];
    return await resp.json();
  } catch { return []; }
}

async function loadGroupByName(name) {
  try {
    const resp = await fetch(`/api/groups/${encodeURIComponent(name)}`);
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

async function saveGroupToServer(group) {
  try {
    const resp = await fetch('/api/groups', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(group)
    });
    return await resp.json();
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

async function deleteGroupFromServer(name) {
  try {
    const resp = await fetch(`/api/groups/${encodeURIComponent(name)}`, {
      method: 'DELETE'
    });
    return await resp.json();
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

// ─── Group 编排状态 ─────────────────────────────────

window._groupEditor = {
  group: null,       // 当前编辑的 group 对象
  isNew: false,      // 是否为新建
  dragIdx: -1,       // 拖拽源索引
};

// 缓存的 Group 列表（编排/删除用索引查找）
window._groupsCache = [];

// ─── 主入口：显示 Group 管理 ────────────────────────

async function showGroupsModal() {
  window._groupsCache = await loadGroups();
  const groups = window._groupsCache;
  const favs = loadFavorites();

  let modal = document.getElementById('groups-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'groups-modal';
    modal.className = 'modal-overlay';
    document.body.appendChild(modal);
  }

  const listHtml = groups.length ? groups.map((g, gi) => {
    const stepsText = g.steps.map(s => s.favorite).join(' → ');
    const criticalCount = g.steps.filter(s => s.is_critical).length;
    const criticalBadge = criticalCount > 0
      ? `<span class="grp-badge grp-badge-critical">⭐${criticalCount}</span>` : '';
    return `
      <div class="grp-card">
        <div class="grp-card-info">
          <div class="grp-card-title">${g.name}${criticalBadge}</div>
          <div class="grp-card-steps">${g.steps.length} 步骤：${stepsText}</div>
          ${g.description ? `<div class="grp-card-desc">${g.description}</div>` : ''}
        </div>
        <div class="grp-card-actions">
          <button class="grp-btn grp-btn-edit" onclick="openGroupEditor(${gi})">编排</button>
          <button class="grp-btn grp-btn-delete" onclick="deleteGroupConfirm(${gi})">✕</button>
        </div>
      </div>`;
  }).join('') : '<div class="grp-empty">暂无 Group，点击「新建」开始编排。</div>';

  modal.innerHTML = `
    <div class="modal" style="max-width:640px">
      <h3 style="margin-bottom:16px">📂 Group 管理</h3>
      <div class="grp-list">${listHtml}</div>
      <div class="btn-row" style="margin-top:16px">
        <button onclick="openGroupEditor(null)">＋ 新建 Group</button>
        <button onclick="closeGroupsModal()">关闭</button>
      </div>
    </div>
    <style>${getGroupStyles()}</style>`;

  modal.classList.add('show');
}

function closeGroupsModal() {
  const modal = document.getElementById('groups-modal');
  if (modal) modal.classList.remove('show');
}

async function deleteGroupConfirm(gi) {
  const g = window._groupsCache[gi];
  if (!g || !confirm(`确定删除 Group「${g.name}」？`)) return;
  const result = await deleteGroupFromServer(g.name);
  if (result.ok) showGroupsModal();
  else alert('❌ 删除失败: ' + (result.error || '未知错误'));
}

// ─── Group 编排器 ──────────────────────────────────

async function openGroupEditor(gi) {
  closeGroupsModal();

  const favs = loadFavorites();
  if (!favs.length) {
    alert('收藏库为空，请先保存收藏后再编排 Group');
    return;
  }

  if (gi != null) {
    const group = window._groupsCache[gi];
    if (!group) { alert('加载失败'); return; }
    window._groupEditor.group = JSON.parse(JSON.stringify(group));
    window._groupEditor.isNew = false;
  } else {
    window._groupEditor.group = { name: '', description: '', steps: [] };
    window._groupEditor.isNew = true;
  }

  renderGroupEditor();
}

function renderGroupEditor() {
  const ge = window._groupEditor;
  const group = ge.group;
  const favs = loadFavorites();

  let modal = document.getElementById('group-editor-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'group-editor-modal';
    modal.className = 'modal-overlay';
    document.body.appendChild(modal);
  }

  // 步骤列表 HTML（支持拖拽）
  const stepsHtml = group.steps.length ? group.steps.map((step, i) => {
    const fav = favs.find(f => f.name === step.favorite);
    const eventCount = fav ? (fav.count || fav.events.length) : '?';
    const criticalClass = step.is_critical ? 'grp-step-critical' : '';
    const criticalChecked = step.is_critical ? 'checked' : '';
    const delay = step.delay_after_ms || 0;
    return `
      <div class="grp-step ${criticalClass}" draggable="true"
           ondragstart="grpDragStart(event,${i})"
           ondragover="grpDragOver(event,${i})"
           ondrop="grpDrop(event,${i})"
           ondragend="grpDragEnd(event)">
        <div class="grp-step-handle">⠿</div>
        <div class="grp-step-num">${i + 1}</div>
        <div class="grp-step-body">
          <div class="grp-step-name">${step.favorite}</div>
          <div class="grp-step-meta">${eventCount} 事件${fav ? '' : ' ⚠️缺失'}</div>
        </div>
        <div class="grp-step-config">
          <label class="grp-step-critical-label" title="标记为关键步骤">
            <input type="checkbox" ${criticalChecked} onchange="grpToggleCritical(${i})">⭐
          </label>
          <div class="grp-step-delay">
            <input type="number" value="${delay}" min="0" step="500"
                   onchange="grpSetDelay(${i}, this.value)" title="步骤后延迟(ms)">
            <span>ms</span>
          </div>
        </div>
        <button class="grp-step-remove" onclick="grpRemoveStep(${i})" title="移除">✕</button>
      </div>`;
  }).join('') : '<div class="grp-empty-steps">拖拽右侧收藏到此处，或点击「＋」添加</div>';

  // 收藏库列表（右侧，可点击添加）
  const favsHtml = favs.map((f, i) => `
    <div class="grp-fav-item" onclick="grpAddStep('${f.name.replace(/'/g, "\\'")}')" title="点击添加到步骤">
      <span class="grp-fav-name">${f.name}</span>
      <span class="grp-fav-count">${f.count || f.events.length}</span>
    </div>`).join('');

  // 流程预览链路
  const flowHtml = group.steps.length
    ? group.steps.map((s, i) => {
        const mark = s.is_critical ? '<span class="grp-flow-star">⭐</span>' : '';
        return `<span class="grp-flow-node">${mark}${s.favorite}</span>`;
      }).join('<span class="grp-flow-arrow">→</span>')
    : '<span style="color:#78909c">（空流程）</span>';

  modal.innerHTML = `
    <div class="modal grp-editor-modal">
      <div class="grp-editor-header">
        <h3>${ge.isNew ? '＋ 新建 Group' : '✏️ 编排 Group'}</h3>
        <div class="grp-editor-meta">
          <input type="text" id="grp-ed-name" value="${group.name}" placeholder="Group 名称"
                 class="grp-input grp-input-name">
          <input type="text" id="grp-ed-desc" value="${group.description || ''}" placeholder="描述（可选）"
                 class="grp-input grp-input-desc">
        </div>
      </div>

      <div class="grp-editor-flow">
        <label>流程预览：</label>
        <div class="grp-flow-bar">${flowHtml}</div>
      </div>

      <div class="grp-editor-body">
        <div class="grp-editor-left">
          <div class="grp-editor-section-title">步骤编排（${group.steps.length} 步，拖拽排序）</div>
          <div class="grp-steps-list" id="grp-steps-list">${stepsHtml}</div>
        </div>
        <div class="grp-editor-right">
          <div class="grp-editor-section-title">⭐ 收藏库（点击添加）</div>
          <div class="grp-favs-list">${favsHtml}</div>
        </div>
      </div>

      <div class="btn-row" style="margin-top:16px">
        <button onclick="closeGroupEditor()">取消</button>
        <button class="primary" onclick="saveGroupFromEditor()">💾 保存</button>
      </div>
    </div>
    <style>${getGroupStyles()}</style>`;

  modal.classList.add('show');
}

function closeGroupEditor() {
  const modal = document.getElementById('group-editor-modal');
  if (modal) modal.classList.remove('show');
  window._groupEditor.group = null;
}

// ─── 步骤操作 ──────────────────────────────────────

function grpAddStep(favName) {
  const ge = window._groupEditor;
  if (!ge.group) return;
  ge.group.steps.push({
    favorite: favName,
    delay_after_ms: 2000,
    is_critical: false,
  });
  renderGroupEditor();
}

function grpRemoveStep(idx) {
  const ge = window._groupEditor;
  if (!ge.group) return;
  ge.group.steps.splice(idx, 1);
  renderGroupEditor();
}

function grpToggleCritical(idx) {
  const ge = window._groupEditor;
  if (!ge.group) return;
  ge.group.steps[idx].is_critical = !ge.group.steps[idx].is_critical;
  renderGroupEditor();
}

function grpSetDelay(idx, val) {
  const ge = window._groupEditor;
  if (!ge.group) return;
  ge.group.steps[idx].delay_after_ms = parseInt(val) || 0;
  // 不重新渲染，避免输入框失焦
}

// ─── 拖拽排序 ──────────────────────────────────────

function grpDragStart(e, idx) {
  window._groupEditor.dragIdx = idx;
  e.target.classList.add('grp-step-dragging');
  e.dataTransfer.effectAllowed = 'move';
}

function grpDragOver(e, idx) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  // 高亮 drop 目标
  const list = document.getElementById('grp-steps-list');
  list.querySelectorAll('.grp-step').forEach(el => el.classList.remove('grp-step-dragover'));
  e.currentTarget.classList.add('grp-step-dragover');
}

function grpDrop(e, dropIdx) {
  e.preventDefault();
  const ge = window._groupEditor;
  const fromIdx = ge.dragIdx;
  if (fromIdx < 0 || fromIdx === dropIdx) return;

  const steps = ge.group.steps;
  const [moved] = steps.splice(fromIdx, 1);
  steps.splice(dropIdx, 0, moved);

  ge.dragIdx = -1;
  renderGroupEditor();
}

function grpDragEnd(e) {
  e.target.classList.remove('grp-step-dragging');
  const list = document.getElementById('grp-steps-list');
  if (list) list.querySelectorAll('.grp-step').forEach(el => el.classList.remove('grp-step-dragover'));
  window._groupEditor.dragIdx = -1;
}

// ─── 保存 ──────────────────────────────────────────

async function saveGroupFromEditor() {
  const ge = window._groupEditor;
  if (!ge.group) return;

  const nameEl = document.getElementById('grp-ed-name');
  const descEl = document.getElementById('grp-ed-desc');
  const name = nameEl ? nameEl.value.trim() : '';
  const desc = descEl ? descEl.value.trim() : '';

  if (!name) {
    alert('请输入 Group 名称');
    nameEl && nameEl.focus();
    return;
  }
  if (!ge.group.steps.length) {
    alert('请至少添加一个步骤');
    return;
  }

  ge.group.name = name;
  ge.group.description = desc;

  const result = await saveGroupToServer(ge.group);
  if (result.ok) {
    alert(`✅ Group「${name}」已保存（${ge.group.steps.length} 个步骤）`);
    closeGroupEditor();
  } else {
    alert('❌ 保存失败: ' + (result.error || '未知错误'));
  }
}

// ─── 样式 ──────────────────────────────────────────

function getGroupStyles() {
  return `
  .grp-list { max-height: 400px; overflow-y: auto; }
  .grp-card {
    display: flex; align-items: center; padding: 12px 16px; margin-bottom: 8px;
    background: linear-gradient(145deg, #1a1a2e, #1e2240);
    border-radius: 10px; border: 1px solid #2a4a7f; transition: border-color 0.2s;
  }
  .grp-card:hover { border-color: #4fc3f7; }
  .grp-card-info { flex: 1; min-width: 0; }
  .grp-card-title { font-size: 14px; font-weight: 600; color: #4fc3f7; margin-bottom: 4px; }
  .grp-card-steps { font-size: 12px; color: #90caf9; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .grp-card-desc { font-size: 11px; color: #78909c; margin-top: 4px; }
  .grp-card-actions { display: flex; gap: 6px; margin-left: 12px; }
  .grp-btn { padding: 6px 14px; border-radius: 6px; font-size: 12px; cursor: pointer; border: 1px solid; }
  .grp-btn-edit { border-color: #4fc3f7; background: linear-gradient(145deg,#1a2e3e,#1e3a4a); color: #4fc3f7; }
  .grp-btn-delete { border-color: #c0392b; background: linear-gradient(145deg,#3e1a1a,#4a1e1e); color: #e74c3c; padding: 6px 10px; }
  .grp-badge { font-size: 11px; padding: 1px 6px; border-radius: 4px; margin-left: 6px; }
  .grp-badge-critical { background: rgba(243,156,18,0.15); color: #f39c12; }
  .grp-empty { color: #78909c; font-size: 14px; text-align: center; padding: 32px 0; }

  /* 编排器 */
  .grp-editor-modal { max-width: 800px !important; width: 90vw; }
  .grp-editor-header { margin-bottom: 12px; }
  .grp-editor-meta { display: flex; gap: 12px; margin-top: 10px; }
  .grp-input { padding: 8px 12px; border: 1px solid #444; border-radius: 6px; background: #1a1a2e; color: #eee; font-size: 13px; }
  .grp-input-name { width: 200px; font-weight: 600; }
  .grp-input-name[readonly] { opacity: 0.6; cursor: not-allowed; }
  .grp-input-desc { flex: 1; }

  .grp-editor-flow { margin: 12px 0; padding: 10px 14px; background: #0d0d1a; border-radius: 8px; border: 1px solid #1e2240; }
  .grp-editor-flow label { font-size: 11px; color: #78909c; display: block; margin-bottom: 6px; }
  .grp-flow-bar { font-size: 13px; line-height: 1.8; display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
  .grp-flow-node { background: #1a2a4a; padding: 2px 10px; border-radius: 12px; color: #90caf9; white-space: nowrap; }
  .grp-flow-arrow { color: #4a5568; font-size: 12px; }
  .grp-flow-star { margin-right: 2px; }

  .grp-editor-body { display: flex; gap: 16px; min-height: 300px; }
  .grp-editor-left { flex: 3; display: flex; flex-direction: column; }
  .grp-editor-right { flex: 2; display: flex; flex-direction: column; }
  .grp-editor-section-title { font-size: 12px; font-weight: 600; color: #78909c; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }

  .grp-steps-list { flex: 1; overflow-y: auto; min-height: 200px; padding: 4px; border: 1px dashed #2a4a7f; border-radius: 8px; }
  .grp-empty-steps { color: #5a6a7a; font-size: 13px; text-align: center; padding: 40px 20px; }

  .grp-step {
    display: flex; align-items: center; gap: 8px; padding: 10px 12px; margin-bottom: 6px;
    background: #1a1a2e; border-radius: 8px; border: 1px solid #2a4a7f;
    cursor: grab; transition: all 0.15s;
  }
  .grp-step:hover { border-color: #4fc3f7; background: #1e2240; }
  .grp-step-critical { border-color: #f39c12 !important; background: rgba(243,156,18,0.05); }
  .grp-step-dragging { opacity: 0.4; }
  .grp-step-dragover { border-color: #27ae60 !important; background: rgba(39,174,96,0.08); }

  .grp-step-handle { color: #4a5568; font-size: 14px; cursor: grab; user-select: none; }
  .grp-step-num { font-size: 12px; font-weight: 700; color: #4fc3f7; min-width: 20px; }
  .grp-step-body { flex: 1; min-width: 0; }
  .grp-step-name { font-size: 13px; font-weight: 500; color: #e0e0e0; }
  .grp-step-meta { font-size: 11px; color: #78909c; margin-top: 2px; }

  .grp-step-config { display: flex; align-items: center; gap: 8px; }
  .grp-step-critical-label { font-size: 12px; cursor: pointer; display: flex; align-items: center; gap: 2px; }
  .grp-step-critical-label input { width: 14px; height: 14px; }
  .grp-step-delay { display: flex; align-items: center; gap: 4px; }
  .grp-step-delay input { width: 60px; padding: 3px 6px; border: 1px solid #333; border-radius: 4px; background: #0d0d1a; color: #aaa; font-size: 11px; text-align: right; }
  .grp-step-delay span { font-size: 10px; color: #5a6a7a; }
  .grp-step-remove { background: none; border: none; color: #c0392b; font-size: 14px; cursor: pointer; padding: 4px 8px; border-radius: 4px; }
  .grp-step-remove:hover { background: rgba(192,57,43,0.15); }

  .grp-favs-list { flex: 1; overflow-y: auto; min-height: 200px; }
  .grp-fav-item {
    display: flex; align-items: center; padding: 8px 12px; margin-bottom: 4px;
    background: #1a1a2e; border-radius: 6px; border: 1px solid #2a4a7f;
    cursor: pointer; transition: all 0.15s;
  }
  .grp-fav-item:hover { border-color: #27ae60; background: rgba(39,174,96,0.06); }
  .grp-fav-name { flex: 1; font-size: 13px; color: #b0bec5; }
  .grp-fav-count { font-size: 11px; color: #5a6a7a; background: #0d0d1a; padding: 2px 6px; border-radius: 10px; }
  `;
}
