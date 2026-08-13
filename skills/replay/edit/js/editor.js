/**
 * replay-core Flow 编辑器
 *
 * 功能：Flow 列表管理、步骤编排（拖拽排序/增删/关键标记）、截图预览、JSON 导入导出、快捷键
 * 独立实现，不引用 adb-replay 任何前端代码。
 */

// ─── 状态 ──────────────────────────────────────────

let currentFlow = null;        // 当前编辑的 Flow 对象
let flows = [];                // 全部 Flow 列表
let currentStepIdx = -1;       // 当前选中的步骤索引
const API_BASE = "/api";       // 后端 API 根路径

// ─── 数据加载 ──────────────────────────────────────

async function loadFlows() {
    try {
        const res = await fetch(`${API_BASE}/flows`);
        flows = await res.json();
        renderFlowList();
    } catch (e) {
        console.error("加载 Flow 列表失败:", e);
    }
}

async function loadFlow(flowId) {
    try {
        const res = await fetch(`${API_BASE}/flows/${flowId}`);
        if (!res.ok) throw new Error("Flow not found");
        currentFlow = await res.json();
        renderStepList();
        highlightActiveFlow();
    } catch (e) {
        console.error("加载 Flow 失败:", e);
    }
}

// ─── 渲染 ──────────────────────────────────────────

function renderFlowList() {
    const el = document.getElementById("flowList");
    if (!flows.length) {
        el.innerHTML = '<p style="color:#888;font-size:12px;padding:8px">暂无 Flow</p>';
        return;
    }
    el.innerHTML = flows.map(f => {
        const stepCount = (f.steps || []).length;
        const active = currentFlow && currentFlow.id === f.id ? ' active' : '';
        return `<div class="flow-item${active}" onclick="loadFlow('${f.id}')">
            <div class="name">${escHtml(f.name || '未命名')}</div>
            <div class="count">${stepCount} 步骤</div>
        </div>`;
    }).join("");
}

function renderStepList() {
    const el = document.getElementById("stepList");
    if (!currentFlow || !currentFlow.steps || !currentFlow.steps.length) {
        el.innerHTML = '<p style="color:#888;font-size:13px;text-align:center;padding:40px">暂无步骤，点击工具栏添加</p>';
        return;
    }
    const steps = currentFlow.steps;
    el.innerHTML = steps.map((s, i) => {
        const typeLabel = getTypeLabel(s.type);
        const name = s.name || typeLabel;
        const isRef = s.type === "flow";
        const refName = isRef ? (s.flow_name || s.flow_id || "?") : "";
        const meta = isRef ? `引用: ${refName}` : (s.value || "");
        const critical = s.is_critical ? " critical" : "";
        const critClass = s.is_critical ? " active" : "";
        return `<div class="step-item${critical}" draggable="true" data-index="${i}"
            ondragstart="dragStart(event, ${i})" ondragover="dragOver(event)" ondrop="drop(event, ${i})"
            ondblclick="editStep(${i})" onclick="selectStep(${i})">
            <span class="idx">#${i + 1}</span>
            <div class="info">
                <div class="name">${escHtml(name)}</div>
                <div class="meta">${escHtml(meta)}</div>
            </div>
            <div class="actions">
                <button class="critical-btn${critClass}" onclick="event.stopPropagation();toggleCritical(${i})" title="关键事件">★</button>
                <button onclick="event.stopPropagation();deleteStep(${i})" title="删除">🗑</button>
            </div>
        </div>`;
    }).join("");
}

function highlightActiveFlow() {
    document.querySelectorAll(".flow-item").forEach(el => {
        el.classList.remove("active");
        const name = el.querySelector(".name")?.textContent;
        if (currentFlow && name === currentFlow.name) {
            el.classList.add("active");
        }
    });
}

// ─── 步骤操作 ──────────────────────────────────────

function getTypeLabel(type) {
    const map = { "event": "事件", "flow": "引用", "pause": "断点", "wait": "等待" };
    return map[type] || type || "事件";
}

function addStep(type) {
    if (!currentFlow) { alert("请先选择或创建一个 Flow"); return; }
    if (!currentFlow.steps) currentFlow.steps = [];
    const step = { type: type, name: getTypeLabel(type), is_critical: false };
    if (type === "wait") { step.value = "1"; step.name = "等待 1s"; }
    if (type === "pause") { step.name = "断点"; }
    currentFlow.steps.push(step);
    renderStepList();
}

function deleteStep(index) {
    if (!currentFlow) return;
    currentFlow.steps.splice(index, 1);
    renderStepList();
}

function toggleCritical(index) {
    if (!currentFlow) return;
    const s = currentFlow.steps[index];
    s.is_critical = !s.is_critical;
    if (s.is_critical && !s.name) s.name = "关键步骤";
    renderStepList();
}

function selectStep(index) {
    currentStepIdx = index;
}

function editStep(index) {
    if (!currentFlow) return;
    const s = currentFlow.steps[index];
    const isFlow = s.type === "flow";
    let bodyHtml = `
        <label>类型</label>
        <select id="editType" style="width:100%;background:#0f3460;color:#e0e0e0;border:1px solid #333;padding:8px;border-radius:6px">
            <option value="event" ${s.type === "event" ? "selected" : ""}>事件</option>
            <option value="flow" ${s.type === "flow" ? "selected" : ""}>引用 Flow</option>
            <option value="pause" ${s.type === "pause" ? "selected" : ""}>断点</option>
            <option value="wait" ${s.type === "wait" ? "selected" : ""}>等待</option>
        </select>
        <label>步骤名称</label>
        <input id="editName" value="${escHtml(s.name || '')}">
        ${isFlow ? `<label>引用 Flow ID</label><input id="editFlowId" value="${escHtml(s.flow_id || '')}">` : `<label>值</label><input id="editValue" value="${escHtml(s.value || '')}">`}
    `;
    showModal("编辑步骤", bodyHtml, () => {
        s.type = document.getElementById("editType").value;
        s.name = document.getElementById("editName").value || getTypeLabel(s.type);
        if (isFlow) s.flow_id = document.getElementById("editFlowId")?.value || "";
        else s.value = document.getElementById("editValue")?.value || "";
        renderStepList();
    });
}

// ─── 拖拽排序 ──────────────────────────────────────

let dragIdx = -1;

function dragStart(e, index) {
    dragIdx = index;
    e.target.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
}

function dragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
}

function drop(e, targetIdx) {
    e.preventDefault();
    if (!currentFlow || dragIdx < 0 || dragIdx === targetIdx) return;
    const steps = currentFlow.steps;
    const item = steps.splice(dragIdx, 1)[0];
    steps.splice(targetIdx, 0, item);
    dragIdx = -1;
    renderStepList();
}

// ─── Flow 操作 ─────────────────────────────────────

function createFlow() {
    const bodyHtml = `
        <label>Flow 名称</label>
        <input id="newFlowName" placeholder="输入名称...">
        <label>描述（可选）</label>
        <textarea id="newFlowDesc" placeholder="输入描述..."></textarea>
    `;
    showModal("新建 Flow", bodyHtml, async () => {
        const name = document.getElementById("newFlowName").value.trim();
        if (!name) { alert("请输入名称"); return; }
        try {
            const res = await fetch(`${API_BASE}/flows`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, description: document.getElementById("newFlowDesc").value, steps: [] })
            });
            if (res.ok) {
                const flow = await res.json();
                currentFlow = flow;
                await loadFlows();
                renderStepList();
            }
        } catch (e) { console.error("创建 Flow 失败:", e); }
    });
}

async function saveCurrentFlow() {
    if (!currentFlow) { alert("没有正在编辑的 Flow"); return; }
    // 从录制编辑器注入的平台信息补足 platform 字段
    if (window.__FLOW_PLATFORM && !currentFlow.platform) {
        currentFlow.platform = window.__FLOW_PLATFORM;
    }
    try {
        const res = await fetch(`${API_BASE}/flow/save`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(currentFlow)
        });
        if (res.ok) {
            showToast("已保存");
        }
    } catch (e) { console.error("保存失败:", e); }
}

function exportFlow() {
    if (!currentFlow) { alert("没有正在编辑的 Flow"); return; }
    const json = JSON.stringify(currentFlow, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${currentFlow.name || "flow"}.json`; a.click();
    URL.revokeObjectURL(url);
}

function importFlow() {
    const input = document.createElement("input");
    input.type = "file"; input.accept = ".json";
    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const text = await file.text();
        try {
            const flow = JSON.parse(text);
            if (!flow.name) { alert("JSON 缺少 name 字段"); return; }
            const res = await fetch(`${API_BASE}/flows`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(flow)
            });
            if (res.ok) {
                currentFlow = await res.json();
                await loadFlows();
                renderStepList();
                showToast("导入成功");
            }
        } catch (e) { alert("JSON 格式错误: " + e.message); }
    };
    input.click();
}

// ─── 弹窗/Toast ────────────────────────────────────

function showModal(title, bodyHtml, onOk) {
    document.getElementById("modalTitle").textContent = title;
    document.getElementById("modalBody").innerHTML = bodyHtml;
    document.getElementById("modal").classList.add("active");
    document.getElementById("modalOk").onclick = () => { closeModal(); onOk(); };
}

function closeModal() {
    document.getElementById("modal").classList.remove("active");
}

function showToast(msg) {
    const t = document.createElement("div");
    t.textContent = msg;
    t.style.cssText = "position:fixed;bottom:20px;right:20px;background:#66bb6a;color:#000;padding:8px 16px;border-radius:6px;font-size:12px;z-index:9999;";
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2000);
}

// ─── 工具函数 ──────────────────────────────────────

function escHtml(s) {
    if (!s) return "";
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ─── 键盘快捷键 ─────────────────────────────────────

document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        saveCurrentFlow();
    }
});

// ─── 初始化 ────────────────────────────────────────

loadFlows();
