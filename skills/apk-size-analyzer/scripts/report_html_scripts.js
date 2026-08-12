// Tab 切换
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const name = btn.dataset.tab;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.querySelector(`.panel[data-panel="${name}"]`).classList.add('active');
    });
});

// 表格排序：点击表头切换升/降序
(function() {
    function parseNumeric(text) {
        if (!text) return 0;
        text = text.trim();
        // 匹配 "xxx KB/MB/GB/B/%"
        const m = text.match(/^(-?[\d.,]+)\s*(B|KB|MB|GB|%)?/i);
        if (!m) return NaN;
        let n = parseFloat(m[1].replace(/,/g, ''));
        if (isNaN(n)) return NaN;
        const unit = (m[2] || '').toUpperCase();
        if (unit === 'KB') n *= 1024;
        else if (unit === 'MB') n *= 1024 * 1024;
        else if (unit === 'GB') n *= 1024 * 1024 * 1024;
        return n;
    }

    function sortTable(table, colIdx, type, asc) {
        const tbody = table.tBodies[0];
        if (!tbody) return;
        const rows = Array.from(tbody.rows);
        rows.sort((r1, r2) => {
            const c1 = r1.cells[colIdx] ? r1.cells[colIdx].innerText : '';
            const c2 = r2.cells[colIdx] ? r2.cells[colIdx].innerText : '';
            let res;
            if (type === 'num') {
                const n1 = parseNumeric(c1), n2 = parseNumeric(c2);
                res = (isNaN(n1) ? -Infinity : n1) - (isNaN(n2) ? -Infinity : n2);
            } else {
                res = c1.localeCompare(c2, 'zh-CN');
            }
            return asc ? res : -res;
        });
        rows.forEach(r => tbody.appendChild(r));
    }

    document.querySelectorAll('table.sortable').forEach(table => {
        const headers = table.tHead ? table.tHead.rows[0].cells : [];
        Array.from(headers).forEach((th, idx) => {
            if (th.classList.contains('no-sort')) return;
            th.addEventListener('click', () => {
                const type = th.dataset.type || 'str';
                const wasAsc = th.classList.contains('sort-asc');
                // 清除其他列的标记
                Array.from(headers).forEach(h => {
                    h.classList.remove('sort-asc', 'sort-desc');
                });
                const asc = !wasAsc;
                th.classList.add(asc ? 'sort-asc' : 'sort-desc');
                sortTable(table, idx, type, asc);
            });
        });
    });
})();

// 重放命令复制按钮
// 适配多个容器：`.replay-cmd`（页眉重放命令）与 `.ue-cmd`（未使用资源 Tab
// 的 lint 引导命令）。如果 DOM 结构变化找不到预期容器，则回退为查找同级的
// <code> 元素，尽量保证按钮可用。
function copyReplayCmd(btn) {
    const row = btn.closest('.replay-cmd, .ue-cmd');
    let codeEl = row ? row.querySelector('code') : null;
    if (!codeEl && btn.parentElement) {
        codeEl = btn.parentElement.querySelector('code');
    }
    if (!codeEl) return;
    const text = codeEl.innerText;
    const done = () => {
        const orig = btn.innerText;
        btn.innerText = '✓ 已复制';
        btn.classList.add('copied');
        setTimeout(() => {
            btn.innerText = orig;
            btn.classList.remove('copied');
        }, 1500);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(() => {
            const ta = document.createElement('textarea');
            ta.value = text; document.body.appendChild(ta);
            ta.select(); document.execCommand('copy'); ta.remove(); done();
        });
    } else {
        const ta = document.createElement('textarea');
        ta.value = text; document.body.appendChild(ta);
        ta.select(); document.execCommand('copy'); ta.remove(); done();
    }
}

// 图片加载失败：隐藏 <img>，显示紧跟其后的占位块；首次失败时显露顶部横幅
function handleImgError(imgEl) {
    imgEl.style.display = 'none';
    const fb = imgEl.parentElement
        ? imgEl.parentElement.querySelector('[data-role="fallback"]')
        : null;
    if (fb) fb.hidden = false;
    const banner = document.getElementById('assetsWarning');
    if (banner) banner.hidden = false;
}

// 视图切换（缩略图 / 表格）
document.querySelectorAll('.view-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const groupName = btn.dataset.target;
        const view = btn.dataset.view;
        // 切换按钮激活态（仅限同组）
        document.querySelectorAll(
            `.view-btn[data-target="${groupName}"]`
        ).forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        // 切换面板
        const group = document.querySelector(`[data-view-group="${groupName}"]`);
        if (!group) return;
        group.querySelectorAll('.view-pane').forEach(p => p.classList.remove('active'));
        const target = group.querySelector(`.view-pane[data-view-pane="${view}"]`);
        if (target) target.classList.add('active');
    });
});

// 图片灯箱
function openLightbox(imgEl, path, size, refsJson) {
    const box = document.getElementById('lightbox');
    const img = document.getElementById('lightbox-img');
    const pathEl = document.getElementById('lightbox-path');
    const sizeEl = document.getElementById('lightbox-size');
    const dimEl = document.getElementById('lightbox-dim');
    const refsEl = document.getElementById('lightbox-refs');
    if (!box || !img) return;
    // 先清空上一次的分辨率，避免切图瞬间残留旧值
    if (dimEl) dimEl.textContent = '';
    img.onload = function () {
        if (!dimEl) return;
        const w = img.naturalWidth | 0;
        const h = img.naturalHeight | 0;
        dimEl.textContent = (w && h) ? (w + '×' + h) : '';
    };
    img.src = imgEl.src;
    img.alt = imgEl.alt || '';
    // 图片已在缓存时 onload 可能不会再触发：主动兜底一次
    if (img.complete && img.naturalWidth && dimEl) {
        dimEl.textContent = img.naturalWidth + '×' + img.naturalHeight;
    }
    if (pathEl) pathEl.textContent = path || imgEl.alt || '';
    if (sizeEl) sizeEl.textContent = size || '';
    if (refsEl) {
        refsEl.innerHTML = renderLightboxRefs(refsJson);
    }
    box.classList.add('open');
    document.body.style.overflow = 'hidden';
}

function renderLightboxRefs(refsJson) {
    if (!refsJson) return '';
    let refs;
    try { refs = JSON.parse(refsJson); } catch (e) { return ''; }
    const projectRoot = document.body
        ? (document.body.getAttribute('data-project-root') || '')
        : '';
    const rootHint = projectRoot
        ? '<span class="lbr-root" title="' + escapeHtml(projectRoot)
          + '">路径相对：' + escapeHtml(shortenRoot(projectRoot)) + '</span>'
        : '';
    // 未用资源专用分支：首项带 __unused 标记 → 渲染「定义位置」块
    // （卡片上已不再展示路径+按钮，全都移到这里）
    if (Array.isArray(refs) && refs.length === 1 && refs[0] && refs[0].__unused) {
        const u = refs[0];
        const fileRel = escapeHtml(u.defined_at || '');
        const lineHtml = u.line
            ? ':<b>' + u.line + '</b>'
            : '';
        let actions = '';
        if (u.abs) {
            const fileUrl = 'file://' + encodePath(u.abs);
            const absEsc = escapeHtml(u.abs);
            const dirEsc = escapeHtml(u.dir || '');
            actions = ''
                + '<div class="lbr-actions lbr-actions-unused">'
                + '  <button class="lbr-act lbr-copy" type="button"'
                + ' data-abs="' + dirEsc + '" onclick="copyAbsPath(this)"'
                + ' title="复制目录路径到剪贴板，粘贴到 Finder（Cmd+Shift+G）/'
                + '&#10;Explorer 地址栏打开：&#10;' + dirEsc
                + '">📋 复制目录</button>'
                + '  <a class="lbr-act" href="' + fileUrl
                + '" title="用默认程序打开文件：&#10;' + absEsc
                + '" target="_blank" rel="noopener">📄 打开文件</a>'
                + '  <button class="lbr-act lbr-copy" type="button"'
                + ' data-abs="' + absEsc + '" onclick="copyAbsPath(this)"'
                + ' title="复制文件绝对路径">⧉ 复制路径</button>'
                + '</div>';
        }
        const metaBits = [];
        if (u.res_type) metaBits.push('<span class="lbr-unused-tag">' + escapeHtml(u.res_type) + '</span>');
        if (u.module) metaBits.push('<span class="lbr-unused-tag lbr-unused-mod">📦 ' + escapeHtml(u.module) + '</span>');
        const metaHtml = metaBits.length
            ? '<div class="lbr-unused-meta">' + metaBits.join('') + '</div>'
            : '';
        return '<div class="lbr-title">'
             + '<span>定义位置</span>'
             + rootHint
             + '</div>'
             + metaHtml
             + '<div class="lbr-unused-path">'
             + '<code>' + fileRel + lineHtml + '</code>'
             + '</div>'
             + actions
             + '<div class="lbr-hint lbr-hint-unused">'
             + '⚠️ Lint 未找到引用，删除前建议人工核对反射 / 动态拼接 / DataBinding 表达式等场景'
             + '</div>';
    }
    if (!Array.isArray(refs) || refs.length === 0) {
        return '<div class="lbr-title"><span>源码引用</span>' + rootHint + '</div>'
             + '<div class="lbr-empty">🚫 源码中未找到该图片的引用</div>';
    }
    let hintHtml = '';
    let list = refs;
    if (refs[0] && refs[0].__hint) {
        hintHtml = '<div class="lbr-hint">📍 ' + escapeHtml(refs[0].__hint) + '</div>';
        list = refs.slice(1);
    }
    if (list.length === 0) {
        return '<div class="lbr-title"><span>源码引用</span>' + rootHint + '</div>'
             + hintHtml;
    }
    const items = list.map(function(r) {
        const kind = r.kind === 'static' ? 'static' : 'dynamic';
        const kindLabel = kind === 'static' ? '静态' : '动态';
        const snippet = r.snippet
            ? '<div class="lbr-snippet">' + escapeHtml(r.snippet) + '</div>'
            : '';
        // 路径部分：若有 abs/dir，渲染成"复制目录/打开文件/复制路径"三按钮
        // （点"📋 复制目录"只复制路径到剪贴板，不会真去打开目录——浏览器
        //  对 file://{dir}/ 的处理是渲染目录列表页，没法唤起文件管理器；
        //  用户需要自己粘贴到 Finder（Cmd+Shift+G）/ Explorer 地址栏）
        const fileRel = escapeHtml(r.file);
        let pathHtml;
        if (r.dir && r.abs) {
            const fileUrl = 'file://' + encodePath(r.abs);
            const absEsc = escapeHtml(r.abs);
            const dirEsc = escapeHtml(r.dir);
            pathHtml = ''
                + '<span class="lbr-path">'
                + fileRel + ':<b>' + r.line + '</b>'
                + '</span>'
                + '<span class="lbr-actions">'
                + '  <button class="lbr-act lbr-copy" type="button"'
                + ' data-abs="' + dirEsc + '" onclick="copyAbsPath(this)"'
                + ' title="复制目录路径到剪贴板，粘贴到 Finder（Cmd+Shift+G）/'
                + '&#10;Explorer 地址栏打开：&#10;' + dirEsc
                + '">📋 复制目录</button>'
                + '  <a class="lbr-act" href="' + fileUrl
                + '" title="用默认程序打开文件：&#10;' + absEsc
                + '" target="_blank" rel="noopener">📄 打开文件</a>'
                + '  <button class="lbr-act lbr-copy" type="button"'
                + ' data-abs="' + absEsc + '" onclick="copyAbsPath(this)"'
                + ' title="复制文件绝对路径">⧉ 复制路径</button>'
                + '</span>';
        } else {
            pathHtml = '<span class="lbr-path">'
                     + fileRel + ':<b>' + r.line + '</b></span>';
        }
        return '<li>'
             + '<span class="lbr-kind ' + kind + '">' + kindLabel + '</span>'
             + pathHtml
             + snippet
             + '</li>';
    }).join('');
    return '<div class="lbr-title">'
         + '<span>源码引用 · 共 ' + list.length + ' 处</span>'
         + rootHint
         + '</div>'
         + hintHtml
         + '<ul>' + items + '</ul>';
}

// 把绝对路径转成 file:// 安全片段：对每段路径做 encodeURIComponent（保留 '/'）
function encodePath(p) {
    if (!p) return '';
    // Windows 盘符情况：C:\ 形式先统一为 /C:/
    let norm = String(p).replace(/\\/g, '/');
    if (/^[a-zA-Z]:\//.test(norm)) norm = '/' + norm;
    return norm.split('/').map(function(seg) {
        return encodeURIComponent(seg);
    }).join('/');
}

// 截短展示工程根：超过 48 字符时只保留末 2 段
function shortenRoot(p) {
    if (!p || p.length <= 48) return p;
    const parts = p.split(/[\/\\]/).filter(Boolean);
    if (parts.length <= 2) return p;
    return '…/' + parts.slice(-2).join('/');
}

function copyAbsPath(btn) {
    const text = btn.getAttribute('data-abs') || '';
    if (!text) return;
    const done = function() {
        const orig = btn.innerText;
        btn.innerText = '✓ 已复制';
        btn.classList.add('copied');
        setTimeout(function() {
            btn.innerText = orig;
            btn.classList.remove('copied');
        }, 1200);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(function() {
            const ta = document.createElement('textarea');
            ta.value = text; document.body.appendChild(ta);
            ta.select(); document.execCommand('copy'); ta.remove(); done();
        });
    } else {
        const ta = document.createElement('textarea');
        ta.value = text; document.body.appendChild(ta);
        ta.select(); document.execCommand('copy'); ta.remove(); done();
    }
}

// 未用资源 Tab：按 module 筛选表格行
function filterUnusedByModule(btn) {
    const mod = btn.getAttribute('data-mod') || '__all__';
    const chips = document.querySelectorAll('.mod-chip');
    chips.forEach(function(c) { c.classList.remove('active'); });
    btn.classList.add('active');

    // 同时过滤「汇总表格视图」的行与「分类视图」里各分组的 img-card / tr
    const table = document.getElementById('unused-table');
    if (table) {
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(function(r) {
            const match = (mod === '__all__' ||
                           r.getAttribute('data-mod') === mod);
            r.style.display = match ? '' : 'none';
        });
    }

    // 分类视图：过滤每个 section 的 img-card（drawable/mipmap 网格）和 tr
    const sections = document.querySelectorAll('.ut-section');
    sections.forEach(function(sec) {
        let visible = 0;
        const items = sec.querySelectorAll('[data-mod]');
        items.forEach(function(el) {
            const match = (mod === '__all__' ||
                           el.getAttribute('data-mod') === mod);
            el.style.display = match ? '' : 'none';
            if (match) visible++;
        });
        // 整个类型在当前筛选下无数据 → 隐藏 section，避免空分组
        sec.style.display = visible === 0 ? 'none' : '';
    });

    // 同步 <details> 折叠态下 summary 里的「当前筛选：XXX」标签，
    // 让用户收起 chips 后仍能看到选中值（否则折起来就一问三不知）
    const curLabel = document.querySelector('[data-current-label]');
    if (curLabel) {
        const name = (mod === '__all__') ? '全部' : mod;
        curLabel.innerHTML = '当前：<b>' + name + '</b>';
    }
}

// 未用资源视图切换（分类视图 / 汇总表格）
function switchUnusedView(btn) {
    const view = btn.getAttribute('data-view');
    document.querySelectorAll('.uv-tab').forEach(function(b) {
        b.classList.toggle('active', b === btn);
    });
    document.querySelectorAll('.unused-view').forEach(function(v) {
        v.style.display = (v.getAttribute('data-view') === view) ? '' : 'none';
    });
}

// 分类视图：一键展开/收起所有分组
function toggleAllUnusedGroups(btn) {
    const expanded = btn.getAttribute('data-expanded') === '1';
    const target = !expanded;  // 点击后要切换到的状态
    document.querySelectorAll('.ut-section').forEach(function(sec) {
        if (target) sec.setAttribute('open', '');
        else sec.removeAttribute('open');
    });
    btn.setAttribute('data-expanded', target ? '1' : '0');
    btn.textContent = target ? '收起全部' : '展开全部';
}

function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function closeLightbox(ev) {
    if (ev) ev.stopPropagation();
    const box = document.getElementById('lightbox');
    if (box) box.classList.remove('open');
    document.body.style.overflow = '';
}

// ESC 关闭灯箱
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLightbox();
});

// ============================================================================
// 批量压缩面板：按原图大小过滤 —— 更新 dry-run/apply 命令里的 --min-size
// ============================================================================

// 把命中数从档位按钮读出来，更新所有 ci-cmd 的文本和 data-active 状态
function _applyCompressMinSize(panel, cliValue, countValue) {
    if (!panel) return;
    const codes = panel.querySelectorAll('.ci-cmd');
    codes.forEach((codeEl) => {
        const base = codeEl.getAttribute('data-base') || codeEl.innerText;
        // base 可能是 "bash xxx --list yyy" 或 "bash xxx --list yyy --apply"
        // 需要把 --min-size 插在 --apply 之前（如果有），否则追加到尾部
        let next = base;
        if (cliValue) {
            const applyIdx = base.indexOf(' --apply');
            if (applyIdx >= 0) {
                next = base.slice(0, applyIdx)
                    + ' --min-size ' + cliValue
                    + base.slice(applyIdx);
            } else {
                next = base + ' --min-size ' + cliValue;
            }
        }
        codeEl.innerText = next;
    });
    // 显示命中数（在自定义输入框旁）
    const cntEl = panel.querySelector('.ci-custom-cnt');
    if (cntEl && typeof countValue === 'number') {
        cntEl.innerText = '命中 ' + countValue + ' 条';
    }
}

// 点击预设档位按钮
function updateCompressMinSize(btn) {
    const panel = btn.closest('[data-compress-filter]').parentElement;
    // 切换 active 状态（仅预设按钮组内互斥）
    const group = btn.parentElement;
    group.querySelectorAll('.ci-chip').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    // 清空自定义输入
    const customInput = group.querySelector('.ci-custom-input');
    if (customInput) customInput.value = '';

    const cli = btn.getAttribute('data-cli') || '';
    const count = parseInt(btn.getAttribute('data-count') || '0', 10);
    _applyCompressMinSize(panel, cli, count);
}

// 自定义输入（单位 KB）
function updateCompressMinSizeCustom(input) {
    const filterBar = input.closest('[data-compress-filter]');
    if (!filterBar) return;
    const panel = filterBar.parentElement;
    const kb = parseInt(input.value, 10);

    if (!(kb > 0)) {
        // 空或非正数 → 回落到 "全部"
        const allBtn = filterBar.querySelector('.ci-chip[data-kb="0"]');
        filterBar.querySelectorAll('.ci-chip').forEach((b) => b.classList.remove('active'));
        if (allBtn) allBtn.classList.add('active');
        const total = allBtn ? parseInt(allBtn.getAttribute('data-count') || '0', 10) : 0;
        _applyCompressMinSize(panel, '', total);
        return;
    }

    // 取消所有预设 active
    filterBar.querySelectorAll('.ci-chip').forEach((b) => b.classList.remove('active'));

    // 根据所有预设按钮统计的 sizes 分布近似不易（数据未传到前端），
    // 这里直接用最接近且不大于 kb 的预设档位的命中数作下界参考；
    // 命中数仅作提示，不影响实际过滤（真正过滤由 shell 端完成）。
    let approxCount = 0;
    const chips = Array.from(filterBar.querySelectorAll('.ci-chip[data-kb]'));
    // chips 按 kb 升序：0,200,500,1024,2048
    for (let i = chips.length - 1; i >= 0; i--) {
        const ckb = parseInt(chips[i].getAttribute('data-kb') || '0', 10);
        if (ckb <= kb) {
            approxCount = parseInt(chips[i].getAttribute('data-count') || '0', 10);
            break;
        }
    }

    // 生成 cli 字符串（整 MB 用 M，否则用 K）
    let cli;
    if (kb >= 1024 && kb % 1024 === 0) {
        cli = (kb / 1024) + 'M';
    } else {
        cli = kb + 'K';
    }
    _applyCompressMinSize(panel, cli, approxCount);
    // 自定义命中数是近似，加个 ~ 标记
    const cntEl = panel.querySelector('.ci-custom-cnt');
    if (cntEl) cntEl.innerText = '命中 ≤ ' + approxCount + ' 条';
}
