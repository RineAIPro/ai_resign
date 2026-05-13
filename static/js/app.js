/* 离职交接助手 - 前端逻辑 */
/* 修改时间：2026/05/08 */
/* 从prototype.html提取，改为API调用 */

// ==================== 全局状态 ====================
let currentCompanyId = null;
let currentCompanyName = '';
let currentModuleId = null; // 用于添加项目到指定模块
let currentParentModuleId = null; // 用于添加子模块
let editingModuleId = null; // 修改时间：2026/05/09 - 编辑模块时的模块ID
let modulesCache = {}; // 修改时间：2026/05/09 - 模块数据缓存，用于获取默认路径
let fontScale = 100;
// Git命令存储：{ pid: [命令字符串数组] }
// 修改时间：2026/05/08 - 支持编辑删除Git命令
let gitCommandsStore = {};
// 默认Git命令流程
const DEFAULT_GIT_COMMANDS = [
    'git status',
    'git add .',
    'git commit -m "feat: 完成交接"',
    'git push origin handover'
];

// ==================== API 封装 ====================
async function api(method, url, data) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (data) opts.body = JSON.stringify(data);
    const res = await fetch(url, opts);
    return res.json();
}

// ==================== 公司页 ====================

let longPressTimer = null;

async function loadCompanies() {
    const companies = await api('GET', '/api/companies');
    const grid = document.getElementById('companyGrid');
    grid.innerHTML = '';
    companies.forEach(c => {
        const card = document.createElement('div');
        card.className = 'company-card';
        card.dataset.cid = c.id;
        card.onclick = () => enterWorkspace(c.id, c.name);
        // 长按删除
        card.onmousedown = (e) => { longPressTimer = setTimeout(() => { if(confirm(`确定删除「${c.name}」？`)) deleteCompany(c.id); }, 600); };
        card.onmouseup = () => clearTimeout(longPressTimer);
        card.onmouseleave = () => clearTimeout(longPressTimer);
        card.innerHTML = `
            <div class="cc-icon">🏢</div>
            <div class="cc-name">${esc(c.name)}</div>
            <div class="cc-dept">${esc(c.department || '')}</div>
            <div class="cc-time">${c.start_date || ''} - ${c.leave_date || '至今'}${c.position ? ' · ' + esc(c.position) : ''}</div>
            <div class="cc-progress">
                <div class="prog-label"><span>交接进度</span><span>0%</span></div>
                <div class="progress-bar"><div class="fill" style="width:0%"></div></div>
            </div>`;
        grid.appendChild(card);
    });
    // 添加按钮
    const addCard = document.createElement('div');
    addCard.className = 'company-card add';
    addCard.onclick = () => openModal('companyModal');
    addCard.innerHTML = '<div class="add-icon">+</div><div style="font-size:13px">创建公司</div>';
    grid.appendChild(addCard);

    // 修改时间：2026/05/09 - 批量获取真实进度更新公司卡片
    if (companies.length > 0) {
        const ids = companies.map(c => c.id).join(',');
        const statsMap = await api('GET', `/api/companies/stats-batch?ids=${ids}`);
        companies.forEach(c => {
            const s = statsMap[String(c.id)];
            if (s) {
                const card = grid.querySelector(`.company-card[data-cid="${c.id}"]`);
                if (card) {
                    const label = card.querySelector('.prog-label span:last-child');
                    const fill = card.querySelector('.progress-bar .fill');
                    if (label) label.textContent = s.progress + '%';
                    if (fill) fill.style.width = s.progress + '%';
                }
            }
        });
    }
}

async function createCompany() {
    const name = document.getElementById('cName').value.trim();
    if (!name) return alert('请输入公司名称');
    await api('POST', '/api/companies', {
        name,
        department: document.getElementById('cDept').value,
        position: document.getElementById('cPos').value,
        start_date: document.getElementById('cStart').value,
        leave_date: document.getElementById('cLeave').value,
        note: document.getElementById('cNote').value
    });
    closeModal('companyModal');
    document.getElementById('cName').value = '';
    document.getElementById('cDept').value = '';
    document.getElementById('cPos').value = '';
    document.getElementById('cStart').value = '';
    document.getElementById('cLeave').value = '';
    document.getElementById('cNote').value = '';
    loadCompanies();
}

async function deleteCompany(id) {
    await api('DELETE', `/api/companies/${id}`);
    loadCompanies();
}

// ==================== 工作区 ====================

function enterWorkspace(id, name) {
    currentCompanyId = id;
    currentCompanyName = name;
    document.getElementById('companyPage').classList.add('hidden');
    document.getElementById('workspace').classList.add('active');
    document.getElementById('wsCompanyName').textContent = name;
    goPage('page-home');
    loadWorkspaceData();
}

function goBackToCompanies() {
    document.getElementById('workspace').classList.remove('active');
    document.getElementById('companyPage').classList.remove('hidden');
    currentCompanyId = null;
    loadCompanies();
}

async function loadWorkspaceData() {
    if (!currentCompanyId) return;
    // 倒计时
    const cd = await api('GET', `/api/companies/${currentCompanyId}/countdown`);
    document.getElementById('countdownDays').textContent = cd.days !== null ? cd.days : '--';
    document.getElementById('countdownDate').textContent = cd.leave_date ? `📅 离职日期：${cd.leave_date}` : '📅 离职日期：未设置';
    // 统计
    const stats = await api('GET', `/api/companies/${currentCompanyId}/stats`);
    document.getElementById('statProjects').textContent = stats.project_count;
    document.getElementById('statTodos').textContent = stats.todo_count;
    document.getElementById('statDocs').textContent = stats.doc_count;
    document.getElementById('statProgress').textContent = stats.progress + '%';
    document.getElementById('statProgressBar').style.width = stats.progress + '%';
    // 入口卡片摘要
    document.getElementById('projectSummary').textContent = `${stats.project_count}个项目`;
    document.getElementById('docSummary').textContent = `${stats.doc_count}份文档`;
    // 配置
    loadConfig();
}

// ==================== 子页面切换 ====================

function goPage(pageId) {
    document.querySelectorAll('.sub-page').forEach(p => p.classList.remove('active'));
    document.getElementById(pageId).classList.add('active');
    document.getElementById('wsContent').scrollTop = 0;
    const hint = document.getElementById('backHint');
    // 修改时间：2026/05/09 - 返回主页时刷新统计数据
    if (pageId === 'page-home') { hint.textContent = ''; loadWorkspaceData(); }
    else if (pageId === 'page-project') { hint.textContent = ' / 项目管理'; loadModules(); }
    else if (pageId === 'page-document') { hint.textContent = ' / 文档管理'; loadDocuments(); }
    else if (pageId === 'page-handover') { hint.textContent = ' / 交接信息'; loadHandoverData(); }
}

function goHome() { goPage('page-home'); }

function handleBack() {
    const currentPage = document.querySelector('.sub-page.active');
    if (currentPage && currentPage.id === 'page-home') {
        // 在主页时，返回公司列表
        goBackToCompanies();
    } else {
        // 在子页面时，返回工作区主页
        goHome();
    }
}

// ==================== 模块 & 项目 ====================

async function loadModules() {
    if (!currentCompanyId) return;
    // 修改时间：2026/05/09 - 保存当前展开状态，刷新后恢复
    const openIds = [];
    document.querySelectorAll('#moduleList .proj-card.open').forEach(c => {
        if (c.id) openIds.push(c.id);
    });

    const modules = await api('GET', `/api/modules?company_id=${currentCompanyId}`);
    // 修改时间：2026/05/09 - 缓存模块数据
    modulesCache = {};
    modules.forEach(m => { modulesCache[m.id] = m; });
    const container = document.getElementById('moduleList');
    container.innerHTML = '';
    if (modules.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-icon">📂</div><div class="empty-text">还没有模块，点击上方按钮添加</div></div>';
        return;
    }
    // 构建树形结构
    const rootModules = modules.filter(m => !m.parent_id);
    const childMap = {};
    modules.filter(m => m.parent_id).forEach(m => {
        if (!childMap[m.parent_id]) childMap[m.parent_id] = [];
        childMap[m.parent_id].push(m);
    });
    rootModules.forEach(mod => renderModule(container, mod, childMap, 'mod_' + mod.id));

    // 恢复之前展开的状态
    openIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('open');
    });
}

function renderModule(container, mod, childMap, prefix) {
    const card = document.createElement('div');
    card.className = 'proj-card';
    card.id = prefix;
    const pathHint = mod.default_project_path
        ? `<div style="font-size:10px;color:#8c93a8;margin-top:2px" title="默认项目地址">📁 ${esc(mod.default_project_path)}</div>`
        : '';
    card.innerHTML = `
        <div class="proj-header" onclick="toggleProj('${prefix}')">
            <div class="ph-left">
                <span class="ph-name">📂 ${esc(mod.name)}</span>
                <span class="tag tag-gray">${mod.project_count}个项目</span>
                ${pathHint}
            </div>
            <div style="display:flex;align-items:center;gap:6px">
                <button class="btn btn-outline btn-sm" onclick="event.stopPropagation();openModuleModal(false, null, ${mod.id})" style="font-size:10px;padding:2px 8px" title="编辑">✏</button>
                <button class="btn btn-danger btn-sm" onclick="event.stopPropagation();deleteModule(${mod.id})" style="font-size:10px;padding:2px 8px">🗑</button>
                <button class="btn btn-primary btn-sm" onclick="event.stopPropagation();currentModuleId=${mod.id};openProjectModal(${mod.id})" style="font-size:10px;padding:2px 8px">+ 项目</button>
                <button class="btn btn-outline btn-sm" onclick="event.stopPropagation();currentParentModuleId=${mod.id};openModuleModal(true)" style="font-size:10px;padding:2px 8px">+ 子模块</button>
                <span class="ph-arrow">▶</span>
            </div>
        </div>
        <div class="proj-body">
            <div id="${prefix}_projects"></div>
            <div id="${prefix}_children"></div>
        </div>`;
    container.appendChild(card);
    // 加载项目
    loadProjects(mod.id, `${prefix}_projects`);
    // 递归渲染子模块
    const children = childMap[mod.id] || [];
    const childContainer = card.querySelector(`#${prefix}_children`);
    children.forEach(child => renderModule(childContainer, child, childMap, 'submod_' + child.id));
}

async function loadProjects(moduleId, containerId) {
    const projects = await api('GET', `/api/projects?module_id=${moduleId}`);
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    projects.forEach(p => {
        const statusClass = p.status === '已完成' ? 'tag-green' : p.status === '维护中' ? 'tag-orange' : 'tag-blue';
        const card = document.createElement('div');
        card.className = 'proj-card';
        card.id = 'proj_' + p.id;
        card.innerHTML = `
            <div class="proj-header" onclick="toggleProj('proj_${p.id}')">
                <div class="ph-left"><span class="ph-name">📱 ${esc(p.name)}</span><span class="tag ${statusClass}" id="status_tag_${p.id}" onclick="event.stopPropagation();cycleProjectStatus(${p.id},'${esc(p.status)}')" title="点击切换状态" style="cursor:pointer">${p.version || 'v1.0'} ${p.status}</span></div>
                <div style="display:flex;align-items:center;gap:6px"><button class="btn btn-danger btn-sm" onclick="event.stopPropagation();deleteProject(${p.id})" style="font-size:10px;padding:2px 8px">✕</button><span class="ph-arrow">▶</span></div>
            </div>
            <div class="proj-body">
                <div class="form-group">
                    <label>项目地址</label>
                    <div style="display:flex;gap:6px">
                        <input value="${esc(p.project_path || '')}" id="path_${p.id}" style="flex:1" onchange="updateProject(${p.id})">
                        <button class="btn btn-outline btn-sm" onclick="openBrowser('path_${p.id}')">📁</button>
                    </div>
                </div>
                <div style="display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap">
                    <button class="btn btn-primary btn-sm" onclick="autoGenerate(${p.id},'tech')">🤖 生成技术栈</button>
                    <button class="btn btn-primary btn-sm" onclick="readGitUrl(${p.id})">🤖 生成Git地址</button>
                    <button class="btn btn-primary btn-sm" onclick="autoGenerate(${p.id},'desc')">🤖 生成简介</button>
                    <button class="btn btn-success btn-sm" onclick="autoGenerate(${p.id},'all')">🤖 一键全部生成</button>
                </div>
                <div class="form-row">
                    <div class="form-group"><label>技术栈</label><input id="tech_${p.id}" value="${esc(p.tech_stack || '')}" onchange="updateProject(${p.id})"></div>
                    <div class="form-group"><label>Git 地址</label><input id="git_${p.id}" value="${esc(p.git_url || '')}" onchange="updateProject(${p.id})"></div>
                </div>
                <div class="form-group"><label>简介</label><textarea id="desc_${p.id}" onchange="updateProject(${p.id})">${esc(p.description || '')}</textarea></div>
                <div style="display:flex;gap:6px;margin-bottom:14px">
                    <button class="btn btn-primary btn-sm" onclick="generateHandoverDoc(${p.id})">🤖 AI生成交接文档</button>
                    <button class="btn btn-outline btn-sm" onclick="previewHandoverDoc(${p.id})">📄 预览</button>
                    <span style="font-size:11px;color:#8c93a8;display:flex;align-items:center">→ 按 resign_doc 模板生成到 项目地址/jiaojie/</span>
                </div>
                <div id="git_area_${p.id}" style="background:#fff;border:1px solid #e4e7ed;border-radius:10px;padding:14px">
                    <div style="text-align:center;color:#8c93a8;padding:20px;font-size:12px">加载中...</div>
                </div>
            </div>`;
        container.appendChild(card);
        // 异步加载Git命令并渲染
        // 修改时间：2026/05/08 - Git操作区域动态渲染，支持编辑/删除/新增
        loadGitCommands(p.id);
    });
}

// 修改时间：2026/05/09 - 支持编辑模块（名称/备注/默认路径），通过modId从缓存取数据
function openModuleModal(isChild, modData, modId) {
    editingModuleId = null;
    // 如果传了modId，从缓存取数据（编辑模式）
    if (modId && modulesCache[modId]) {
        modData = modulesCache[modId];
    }
    if (modData) {
        // 编辑模式
        document.getElementById('moduleModalTitle').textContent = '编辑模块';
        document.getElementById('mName').value = modData.name || '';
        document.getElementById('mNote').value = modData.note || '';
        document.getElementById('mDefaultPath').value = modData.default_project_path || '';
        editingModuleId = modData.id;
        currentParentModuleId = modData.parent_id;
    } else {
        document.getElementById('moduleModalTitle').textContent = isChild ? '添加子模块' : '添加模块';
        document.getElementById('mName').value = '';
        document.getElementById('mNote').value = '';
        document.getElementById('mDefaultPath').value = '';
        if (!isChild) currentParentModuleId = null;
    }
    openModal('moduleModal');
}

async function createModule() {
    const name = document.getElementById('mName').value.trim();
    if (!name) return alert('请输入模块名称');
    const data = {
        name,
        note: document.getElementById('mNote').value,
        default_project_path: document.getElementById('mDefaultPath').value
    };
    if (editingModuleId) {
        // 修改时间：2026/05/09 - 编辑已有模块
        await api('PUT', `/api/modules/${editingModuleId}`, data);
        editingModuleId = null;
    } else {
        data.company_id = currentCompanyId;
        data.parent_id = currentParentModuleId || null;
        await api('POST', '/api/modules', data);
    }
    closeModal('moduleModal');
    loadModules();
}

async function deleteModule(id) {
    if (!confirm('确定删除此模块及其下所有项目？')) return;
    await api('DELETE', `/api/modules/${id}`);
    loadModules();
}

// 修改时间：2026/05/09 - 打开项目弹窗时自动填入模块默认路径
function openProjectModal(moduleId) {
    currentModuleId = moduleId;
    document.getElementById('pName').value = '';
    document.getElementById('pVersion').value = '';
    document.getElementById('pStatus').value = '进行中';
    // 预填模块默认项目地址
    const mod = modulesCache[moduleId];
    document.getElementById('pPath').value = (mod && mod.default_project_path) ? mod.default_project_path : '';
    openModal('projectModal');
}

async function createProject() {
    const name = document.getElementById('pName').value.trim();
    if (!name) return alert('请输入项目名称');
    await api('POST', '/api/projects', {
        module_id: currentModuleId,
        name,
        version: document.getElementById('pVersion').value,
        status: document.getElementById('pStatus').value,
        project_path: document.getElementById('pPath').value
    });
    closeModal('projectModal');
    document.getElementById('pName').value = '';
    document.getElementById('pVersion').value = '';
    document.getElementById('pPath').value = '';
    loadModules();
}

// 修改时间：2026/05/09 - 点击状态标签循环切换项目状态
const STATUS_CYCLE = ['进行中', '已完成', '维护中'];
const STATUS_CLASS = { '进行中': 'tag-blue', '已完成': 'tag-green', '维护中': 'tag-orange' };

async function cycleProjectStatus(pid, currentStatus) {
    const idx = STATUS_CYCLE.indexOf(currentStatus);
    const newStatus = STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length];
    await api('PUT', `/api/projects/${pid}`, { status: newStatus });
    // 更新UI
    const tag = document.getElementById(`status_tag_${pid}`);
    if (tag) {
        tag.className = `tag ${STATUS_CLASS[newStatus]}`;
        tag.textContent = tag.textContent.replace(currentStatus, newStatus);
        tag.setAttribute('onclick', `event.stopPropagation();cycleProjectStatus(${pid},'${newStatus}')`);
    }
}

async function updateProject(pid) {
    const data = {
        project_path: document.getElementById(`path_${pid}`).value,
        tech_stack: document.getElementById(`tech_${pid}`).value,
        git_url: document.getElementById(`git_${pid}`).value,
        description: document.getElementById(`desc_${pid}`).value
    };
    await api('PUT', `/api/projects/${pid}`, data);
}

// 修改时间：2026/05/09 - AI生成交接文档（多模板多文件）
let generatingDocPid = null;

async function generateHandoverDoc(pid) {
    if (generatingDocPid === pid) return;
    const pathEl = document.getElementById(`path_${pid}`);
    const projectPath = pathEl ? pathEl.value.trim() : '';
    if (!projectPath) return alert('请先填写项目地址');
    if (!confirm('将在项目路径/jiaojie/ 下按模板生成多个交接文档，是否继续？')) return;
    generatingDocPid = pid;
    try {
        const res = await api('POST', `/api/projects/${pid}/generate-doc`);
        if (res.error) return alert('❌ ' + res.error);
        const files = res.files || [];
        const names = files.map(f => f.name).join('、');
        alert(`✅ 生成成功！共 ${files.length} 个文件：${names}`);
    } catch (e) {
        alert('❌ 请求失败：' + e.message);
    } finally {
        generatingDocPid = null;
    }
}

// 修改时间：2026/05/09 - 预览交接文档（多文件左右切换）
let docPreviewFiles = [];
let docPreviewIdx = 0;

async function previewHandoverDoc(pid) {
    try {
        const res = await api('GET', `/api/projects/${pid}/read-doc`);
        if (res.error) return alert('⚠️ ' + res.error);
        docPreviewFiles = res.files || [];
        docPreviewIdx = 0;
        renderDocPreview();
        openModal('docPreviewModal');
    } catch (e) {
        alert('❌ 请求失败：' + e.message);
    }
}

function renderDocPreview() {
    if (!docPreviewFiles.length) return;
    const file = docPreviewFiles[docPreviewIdx];
    document.getElementById('docPreviewTitle').textContent = file.name || '交接文档';
    // 修改时间：2026/05/09 - Markdown渲染预览
    const container = document.getElementById('docPreviewContent');
    container.innerHTML = marked.parse(file.content || '');
    container.querySelectorAll('pre code').forEach(block => {
        block.style.background = '#f5f6f8';
        block.style.padding = '8px 12px';
        block.style.borderRadius = '6px';
        block.style.fontSize = '12px';
        block.style.overflowX = 'auto';
    });
    document.getElementById('docPreviewPath').textContent = '📁 ' + (file.path || '') + ` (${docPreviewIdx + 1}/${docPreviewFiles.length})`;
    const prevBtn = document.getElementById('docPrevBtn');
    const nextBtn = document.getElementById('docNextBtn');
    prevBtn.style.display = docPreviewIdx > 0 ? '' : 'none';
    nextBtn.style.display = docPreviewIdx < docPreviewFiles.length - 1 ? '' : 'none';
}

function switchDoc(delta) {
    docPreviewIdx = Math.max(0, Math.min(docPreviewFiles.length - 1, docPreviewIdx + delta));
    renderDocPreview();
}

async function deleteProject(pid) {
    if (!confirm('确定删除此项目？')) return;
    await api('DELETE', `/api/projects/${pid}`);
    loadModules();
}

async function autoGenerate(pid, type) {
    const res = await api('POST', `/api/projects/${pid}/auto-generate`);
    if (type === 'tech' && res.tech_stack !== undefined) {
        document.getElementById(`tech_${pid}`).value = res.tech_stack || '';
        updateProject(pid);
    } else if (type === 'git' && res.git_url !== undefined) {
        document.getElementById(`git_${pid}`).value = res.git_url || '';
        updateProject(pid);
    } else if (type === 'desc' && res.description !== undefined) {
        document.getElementById(`desc_${pid}`).value = res.description || '';
        updateProject(pid);
    } else if (type === 'all') {
        if (res.tech_stack !== undefined) document.getElementById(`tech_${pid}`).value = res.tech_stack || '';
        if (res.git_url !== undefined) document.getElementById(`git_${pid}`).value = res.git_url || '';
        if (res.description !== undefined) document.getElementById(`desc_${pid}`).value = res.description || '';
        updateProject(pid);
    }
}

// 修改时间：2026/05/08 - 直接读取项目路径下.git/config获取Git地址，无需复杂接口
async function readGitUrl(pid) {
    const pathEl = document.getElementById(`path_${pid}`);
    const projectPath = pathEl ? pathEl.value.trim() : '';
    if (!projectPath) return alert('请先填写项目地址');
    try {
        const res = await api('POST', '/api/git/read-url', { project_path: projectPath });
        if (!res || typeof res !== 'object') return alert('❌ 服务器返回异常');
        if (res.error) return alert('❌ ' + res.error);
        if (res.git_url) {
            document.getElementById(`git_${pid}`).value = res.git_url;
            updateProject(pid);
        } else {
            alert('⚠️ ' + (res.message || '未能读取Git远程地址，请确认项目路径下有.git目录且已配置remote origin'));
        }
    } catch (e) {
        alert('❌ 请求失败：' + e.message);
    }
}

// ==================== Git命令流程管理 ====================
// 修改时间：2026/05/08 - 支持编辑、删除、新增Git命令

async function loadGitCommands(pid) {
    /* 为指定项目加载Git命令模板并渲染 */
    if (!currentCompanyId) return;
    // 尝试从API加载模板
    const templates = await api('GET', `/api/git-templates?company_id=${currentCompanyId}`);
    if (templates.length > 0 && templates[0].commands) {
        gitCommandsStore[pid] = templates[0].commands.split('\n').filter(c => c.trim());
    } else {
        gitCommandsStore[pid] = [...DEFAULT_GIT_COMMANDS];
    }
    renderGitFlow(pid);
}

function renderGitFlow(pid) {
    /* 渲染指定项目的Git命令流程 */
    const area = document.getElementById(`git_area_${pid}`);
    if (!area) return;
    const commands = gitCommandsStore[pid] || [...DEFAULT_GIT_COMMANDS];

    let stepsHtml = '';
    commands.forEach((cmd, idx) => {
        const escapedCmd = esc(cmd);
        stepsHtml += `
            <div class="git-step" style="position:relative">
                <div class="git-num">${idx + 1}</div>
                <div class="git-cmd" id="git_cmd_text_${pid}_${idx}" style="cursor:pointer"
                     ondblclick="startEditGitCmd(${pid}, ${idx})"
                     title="双击编辑命令">${escapedCmd}</div>
                <div style="display:flex;gap:4px;margin-left:6px">
                    <button class="btn btn-sm" onclick="executeSingleCmd(${pid}, ${idx})"
                            style="font-size:12px;padding:3px 7px;line-height:1;background:#67c23a;color:#fff;border:none;border-radius:4px" title="执行此命令">▶</button>
                    <button class="btn btn-outline btn-sm" onclick="startEditGitCmd(${pid}, ${idx})"
                            style="font-size:12px;padding:3px 7px;line-height:1" title="编辑">✏</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteGitCmd(${pid}, ${idx})"
                            style="font-size:12px;padding:3px 7px;line-height:1" title="删除">✕</button>
                </div>
            </div>`;
        if (idx < commands.length - 1) {
            stepsHtml += '<div class="git-conn"></div>';
        }
    });

    area.innerHTML = `
        <div style="font-size:12px;font-weight:600;color:#2c3143;margin-bottom:8px">🔀 Git 操作</div>
        <div style="font-size:11px;color:#3c4257;font-weight:600;margin-bottom:6px">
            命令流程
            <span style="font-size:10px;color:#8c93a8;font-weight:400">（双击命令文本可编辑）</span>
        </div>
        <div class="git-flow">${stepsHtml}</div>
        <div style="display:flex;gap:6px;margin-top:10px;flex-wrap:wrap">
            <button class="btn btn-outline btn-sm" onclick="addGitCmd(${pid})">+ 添加命令</button>
            <button class="btn btn-warning btn-sm" onclick="executeGitAll(${pid})">⚡ 一键执行</button>
            <button class="btn btn-outline btn-sm" onclick="saveGitTemplate(${pid})">💾 保存模板</button>
        </div>
        <div id="git_output_${pid}" style="margin-top:8px;max-height:200px;overflow-y:auto;display:none;
             background:#1e1e1e;color:#d4d4d4;border-radius:6px;padding:8px;font-family:monospace;font-size:11px;white-space:pre-wrap"></div>
    `;
}

function startEditGitCmd(pid, idx) {
    /* 行内编辑Git命令 */
    const textEl = document.getElementById(`git_cmd_text_${pid}_${idx}`);
    if (!textEl) return;
    const currentCmd = gitCommandsStore[pid][idx];
    textEl.innerHTML = `<input id="git_cmd_input_${pid}_${idx}"
        value="${esc(currentCmd)}"
        style="flex:1;padding:2px 6px;border:1px solid #4f6ef4;border-radius:4px;font-size:11px;font-family:monospace"
        onblur="finishEditGitCmd(${pid}, ${idx})"
        onkeydown="if(event.key==='Enter')finishEditGitCmd(${pid}, ${idx})">`;
    const input = document.getElementById(`git_cmd_input_${pid}_${idx}`);
    if (input) { input.focus(); input.select(); }
}

function finishEditGitCmd(pid, idx) {
    /* 完成编辑Git命令 */
    const input = document.getElementById(`git_cmd_input_${pid}_${idx}`);
    if (!input) return;
    const newCmd = input.value.trim();
    if (newCmd) {
        gitCommandsStore[pid][idx] = newCmd;
    }
    renderGitFlow(pid);
}

function deleteGitCmd(pid, idx) {
    /* 删除Git命令 */
    if (!confirm('确定删除此命令？')) return;
    gitCommandsStore[pid].splice(idx, 1);
    renderGitFlow(pid);
}

function addGitCmd(pid) {
    /* 添加新Git命令 */
    if (!gitCommandsStore[pid]) gitCommandsStore[pid] = [];
    gitCommandsStore[pid].push('git ');
    renderGitFlow(pid);
    // 自动进入编辑新添加的最后一条命令
    const lastIdx = gitCommandsStore[pid].length - 1;
    setTimeout(() => startEditGitCmd(pid, lastIdx), 100);
}

async function saveGitTemplate(pid) {
    /* 保存当前命令流程为模板 */
    const name = prompt('请输入模板名称：', '默认提交流程');
    if (!name) return;
    const commands = gitCommandsStore[pid] || [];
    if (commands.length === 0) return alert('请先添加命令');
    const cmdText = commands.join('\n');
    // 尝试查找已有模板更新，否则新建
    const templates = await api('GET', `/api/git-templates?company_id=${currentCompanyId}`);
    if (templates.length > 0) {
        await api('PUT', `/api/git-templates/${templates[0].id}`, { name, commands: cmdText });
    } else {
        await api('POST', '/api/git-templates', { company_id: currentCompanyId, name, commands: cmdText });
    }
    alert('模板已保存');
}

// Git命令执行 - 流式实时输出
// 修改时间：2026/05/08 - 改为fetch流式读取，实时显示命令输出；去掉逐步执行，每条命令独立执行

// 修改时间：2026/05/08 - 单独执行某一条命令
async function executeSingleCmd(pid, idx) {
    const commands = gitCommandsStore[pid] || [];
    const cmd = commands[idx];
    if (!cmd) return;
    const pathEl = document.getElementById(`path_${pid}`);
    const projectPath = pathEl ? pathEl.value : '';
    if (!projectPath) return alert('请先填写项目地址');

    const outputDiv = document.getElementById(`git_output_${pid}`);
    if (outputDiv) {
        outputDiv.style.display = 'block';
        outputDiv.textContent = `▶ 执行(${idx + 1}): ${cmd}\n`;
        outputDiv.scrollTop = outputDiv.scrollHeight;
    }

    let lastExitCode = 0;
    try {
        await fetchStream('/api/git/execute-stream',
            { project_path: projectPath, command: cmd },
            (text) => {
                if (text.startsWith('__EXIT__:')) {
                    lastExitCode = parseInt(text.split(':')[1]) || 0;
                } else if (text.startsWith('__ERROR__:')) {
                    if (outputDiv) {
                        outputDiv.textContent += `\n❌ ${text.substring(9)}\n`;
                        outputDiv.scrollTop = outputDiv.scrollHeight;
                    }
                } else {
                    if (outputDiv) {
                        outputDiv.textContent += text + '\n';
                        outputDiv.scrollTop = outputDiv.scrollHeight;
                    }
                }
            }
        );
        if (outputDiv) {
            outputDiv.textContent += lastExitCode === 0 ? '✅ 成功\n' : `❌ 执行出错 (退出码: ${lastExitCode})\n`;
            outputDiv.scrollTop = outputDiv.scrollHeight;
        }
    } catch (e) {
        if (outputDiv) {
            outputDiv.textContent += `\n请求失败: ${e.message}\n`;
            outputDiv.scrollTop = outputDiv.scrollHeight;
        }
    }
}

// 通用流式读取函数
async function fetchStream(url, body, onLine) {
    const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ error: 'HTTP ' + resp.status }));
        throw new Error(err.error || '请求失败');
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // 保留未完成的行
        for (const line of lines) {
            if (!line.trim()) continue;
            try {
                const obj = JSON.parse(line);
                if (obj.t) onLine(obj.t);
            } catch (e) { /* skip malformed lines */ }
        }
    }
    // 处理剩余buffer
    if (buffer.trim()) {
        try {
            const obj = JSON.parse(buffer);
            if (obj.t) onLine(obj.t);
        } catch (e) { /* skip */ }
    }
}

async function executeGitAll(pid) {
    /* 一键执行所有Git命令 - 流式输出 */
    const commands = gitCommandsStore[pid] || [];
    const pathEl = document.getElementById(`path_${pid}`);
    const projectPath = pathEl ? pathEl.value : '';
    if (!projectPath) return alert('请先填写项目地址');
    if (commands.length === 0) return alert('请先添加命令');

    const outputDiv = document.getElementById(`git_output_${pid}`);
    if (outputDiv) {
        outputDiv.style.display = 'block';
        outputDiv.textContent = '⚡ 开始一键执行...\n';
        outputDiv.scrollTop = outputDiv.scrollHeight;
    }

    try {
        await fetchStream('/api/git/execute-all-stream',
            { project_path: projectPath, commands },
            (text) => {
                if (outputDiv) {
                    if (text.startsWith('__CMD__:')) {
                        outputDiv.textContent += `\n${text.substring(8)}\n`;
                    } else if (text.startsWith('__EXIT__:')) {
                        const code = parseInt(text.split(':')[1]) || 0;
                        outputDiv.textContent += code === 0 ? '✅\n' : `❌ (退出码: ${code})\n`;
                    } else if (text.startsWith('__BREAK__:')) {
                        outputDiv.textContent += `\n⚠️ ${text.substring(9)}\n`;
                    } else if (text.startsWith('__ERROR__:')) {
                        outputDiv.textContent += `\n❌ ${text.substring(9)}\n`;
                    } else {
                        outputDiv.textContent += text + '\n';
                    }
                    outputDiv.scrollTop = outputDiv.scrollHeight;
                }
            }
        );
    } catch (e) {
        if (outputDiv) {
            outputDiv.textContent += `\n请求失败: ${e.message}\n`;
            outputDiv.scrollTop = outputDiv.scrollHeight;
        }
    }
}

// ==================== 文档管理 ====================

async function loadDocuments() {
    if (!currentCompanyId) return;
    const docs = await api('GET', `/api/documents?company_id=${currentCompanyId}`);
    const container = document.getElementById('documentList');
    container.innerHTML = '';
    if (docs.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-icon">📄</div><div class="empty-text">还没有文档，点击上方按钮导入</div></div>';
        return;
    }
    docs.forEach(d => {
        const analyzed = d.ai_analyzed;
        const icon = d.file_type === 'Word' ? '📝' : d.file_type === 'PDF' ? '📕' : '📄';
        const tagClass = analyzed ? 'tag-green' : 'tag-orange';
        const tagText = analyzed ? 'AI已分析' : '未分析';
        const card = document.createElement('div');
        card.className = 'doc-card';
        card.innerHTML = `
            <div class="doc-left"><div class="doc-icon">${icon}</div><div class="doc-info"><div class="doc-name">${esc(d.name)}</div><div class="doc-meta">${esc(d.file_type || '')} · <span class="tag ${tagClass}" style="font-size:9px">${tagText}</span></div></div></div>
            <div style="display:flex;gap:6px">
                ${!analyzed ? `<button class="btn btn-sm" style="background:#f5f7ff;color:#4f6ef4;border:none" onclick="analyzeDoc(${d.id})">🤖 AI分析</button>` : ''}
                <button class="btn btn-danger btn-sm" onclick="deleteDoc(${d.id})">删除</button>
            </div>`;
        container.appendChild(card);
    });
}

function openDocModal() {
    document.getElementById('dName').value = '';
    document.getElementById('dPath').value = '';
    openModal('docModal');
}

async function createDocument() {
    const name = document.getElementById('dName').value.trim();
    if (!name) return alert('请输入文档名称');
    await api('POST', '/api/documents', {
        company_id: currentCompanyId,
        name,
        file_path: document.getElementById('dPath').value,
        file_type: document.getElementById('dType').value
    });
    closeModal('docModal');
    loadDocuments();
}

async function analyzeDoc(id) {
    await api('POST', `/api/documents/${id}/analyze`);
    loadDocuments();
}

async function deleteDoc(id) {
    if (!confirm('确定删除此文档？')) return;
    await api('DELETE', `/api/documents/${id}`);
    loadDocuments();
}

// ==================== 交接信息 ====================

async function loadHandoverData() {
    loadAccounts();
    loadTodos();
    loadContacts();
    loadSchedules();
}

// --- 账号 ---
async function loadAccounts() {
    const accounts = await api('GET', `/api/accounts?company_id=${currentCompanyId}`);
    const tbody = document.getElementById('accountTableBody');
    tbody.innerHTML = '';
    const typeTagMap = { '代码仓库': 'tag-blue', '云服务': 'tag-orange', '数据库': 'tag-red', 'CI/CD': 'tag-blue', '办公系统': 'tag-gray' };
    const statusTagMap = { '已交接': 'tag-green', '待交接': 'tag-orange', '不需要交接': 'tag-gray' };
    accounts.forEach(a => {
        tbody.innerHTML += `<tr>
            <td><b>${esc(a.platform)}</b></td>
            <td><span class="tag ${typeTagMap[a.account_type] || 'tag-gray'}">${esc(a.account_type)}</span></td>
            <td>${esc(a.usage_desc)}</td>
            <td><span class="tag ${statusTagMap[a.status] || 'tag-orange'}" id="acc_status_${a.id}" onclick="cycleAccountStatus(${a.id},'${esc(a.status)}')" title="点击切换状态" style="cursor:pointer">${esc(a.status)}</span></td>
            <td><button class="btn btn-danger btn-sm" onclick="deleteAccount(${a.id})">删除</button></td>
        </tr>`;
    });
}

function openAccountModal() {
    document.getElementById('aPlatform').value = '';
    document.getElementById('aUsage').value = '';
    openModal('accountModal');
}

async function createAccount() {
    const platform = document.getElementById('aPlatform').value.trim();
    if (!platform) return alert('请输入平台名称');
    await api('POST', '/api/accounts', {
        company_id: currentCompanyId,
        platform,
        account_type: document.getElementById('aType').value,
        usage_desc: document.getElementById('aUsage').value,
        status: document.getElementById('aStatus').value
    });
    closeModal('accountModal');
    loadAccounts();
}

// 修改时间：2026/05/09 - 账号状态循环切换
const ACC_STATUS_CYCLE = ['待交接', '已交接', '不需要交接'];
const ACC_STATUS_CLASS = { '待交接': 'tag-orange', '已交接': 'tag-green', '不需要交接': 'tag-gray' };

async function cycleAccountStatus(id, currentStatus) {
    const idx = ACC_STATUS_CYCLE.indexOf(currentStatus);
    const newStatus = ACC_STATUS_CYCLE[(idx + 1) % ACC_STATUS_CYCLE.length];
    await api('PUT', `/api/accounts/${id}`, { status: newStatus });
    const tag = document.getElementById(`acc_status_${id}`);
    if (tag) {
        tag.className = `tag ${ACC_STATUS_CLASS[newStatus]}`;
        tag.textContent = newStatus;
        tag.setAttribute('onclick', `cycleAccountStatus(${id},'${newStatus}')`);
    }
}

async function deleteAccount(id) {
    if (!confirm('确定删除此账号？')) return;
    await api('DELETE', `/api/accounts/${id}`);
    loadAccounts();
}

// --- 待办 ---
async function loadTodos() {
    const todos = await api('GET', `/api/todos?company_id=${currentCompanyId}`);
    const container = document.getElementById('todoList');
    const active = todos.filter(t => t.status === '进行中');
    const done = todos.filter(t => t.status === '已完成');
    const prioMap = { '紧急': 'tag-red', '重要': 'tag-orange', '普通': 'tag-gray' };
    let html = '';
    if (active.length) {
        html += '<div style="margin-bottom:12px"><div style="font-size:12px;font-weight:600;color:#2c3143;margin-bottom:8px">🔴 进行中</div><ul class="checklist">';
        active.forEach(t => {
            html += `<li><input type="checkbox" onchange="toggleTodo(${t.id})"> <b>${esc(t.title)}</b> — ${esc(t.description || '')} <span class="tag ${prioMap[t.priority] || 'tag-gray'}" style="margin-left:6px">${t.priority}</span> <button onclick="deleteTodo(${t.id})" style="font-size:10px;padding:0 5px;border:none;background:none;cursor:pointer;color:#e8374c" title="删除">✕</button></li>`;
        });
        html += '</ul></div>';
    }
    if (done.length) {
        html += '<div><div style="font-size:12px;font-weight:600;color:#2c3143;margin-bottom:8px">🟢 已完成</div><ul class="checklist">';
        done.forEach(t => {
            html += `<li><input type="checkbox" checked disabled> ${esc(t.title)} <button onclick="deleteTodo(${t.id})" style="font-size:10px;padding:0 5px;border:none;background:none;cursor:pointer;color:#e8374c" title="删除">✕</button></li>`;
        });
        html += '</ul></div>';
    }
    if (!active.length && !done.length) html = '<div class="empty-state"><div class="empty-text">还没有待办事项</div></div>';
    container.innerHTML = html;
}

function openTodoModal() {
    document.getElementById('tTitle').value = '';
    document.getElementById('tDesc').value = '';
    openModal('todoModal');
}

async function createTodo() {
    const title = document.getElementById('tTitle').value.trim();
    if (!title) return alert('请输入标题');
    await api('POST', '/api/todos', {
        company_id: currentCompanyId,
        title,
        description: document.getElementById('tDesc').value,
        priority: document.getElementById('tPriority').value,
        status: document.getElementById('tStatus').value
    });
    closeModal('todoModal');
    loadTodos();
}

async function toggleTodo(id) {
    await api('PUT', `/api/todos/${id}`, { status: '已完成' });
    loadTodos();
}

// 修改时间：2026/05/09 - 删除待办
async function deleteTodo(id) {
    if (!confirm('确定删除此待办？')) return;
    await api('DELETE', `/api/todos/${id}`);
    loadTodos();
}

// --- 联系人 ---
async function loadContacts() {
    const contacts = await api('GET', `/api/contacts?company_id=${currentCompanyId}`);
    const tbody = document.getElementById('contactTableBody');
    tbody.innerHTML = '';
    contacts.forEach(c => {
        tbody.innerHTML += `<tr>
            <td><b>${esc(c.name)}</b></td>
            <td>${esc(c.role)}</td>
            <td>${esc(c.handover_scope)}</td>
            <td>${esc(c.contact_info)}</td>
            <td>${esc(c.note || '')}</td>
            <td><button class="btn btn-danger btn-sm" onclick="deleteContact(${c.id})">删除</button></td>
        </tr>`;
    });
}

function openContactModal() {
    document.getElementById('ctName').value = '';
    document.getElementById('ctRole').value = '';
    document.getElementById('ctScope').value = '';
    document.getElementById('ctInfo').value = '';
    document.getElementById('ctNote').value = '';
    openModal('contactModal');
}

async function createContact() {
    const name = document.getElementById('ctName').value.trim();
    if (!name) return alert('请输入姓名');
    await api('POST', '/api/contacts', {
        company_id: currentCompanyId,
        name,
        role: document.getElementById('ctRole').value,
        handover_scope: document.getElementById('ctScope').value,
        contact_info: document.getElementById('ctInfo').value,
        note: document.getElementById('ctNote').value
    });
    closeModal('contactModal');
    loadContacts();
}

async function deleteContact(id) {
    if (!confirm('确定删除此联系人？')) return;
    await api('DELETE', `/api/contacts/${id}`);
    loadContacts();
}

// --- 日程 ---
async function loadSchedules() {
    const schedules = await api('GET', `/api/schedules?company_id=${currentCompanyId}`);
    const container = document.getElementById('scheduleTimeline');
    container.innerHTML = '';
    const statusMap = { '已完成': 'done', '待进行': '', '即将到来': '' };
    const statusTagMap = { '已完成': 'tag-green', '待进行': 'tag-gray', '即将到来': 'tag-blue' };
    schedules.forEach(s => {
        container.innerHTML += `<div class="tl-item ${statusMap[s.status] || ''}">
            <div class="tl-date">${esc(s.event_date)}</div>
            <div class="tl-content" style="display:flex;align-items:center;gap:6px">
                <span style="flex:1">${esc(s.content)}</span>
                <span class="tag ${statusTagMap[s.status] || 'tag-gray'}" id="sch_status_${s.id}" onclick="cycleScheduleStatus(${s.id},'${esc(s.status)}')" title="点击切换状态" style="cursor:pointer">${esc(s.status)}</span>
                <button onclick="deleteSchedule(${s.id})" style="font-size:10px;padding:0 5px;border:none;background:none;cursor:pointer;color:#e8374c" title="删除">✕</button>
            </div>
        </div>`;
    });
    if (!schedules.length) container.innerHTML = '<div class="empty-state"><div class="empty-text">还没有日程</div></div>';
}

function openScheduleModal() {
    document.getElementById('sDate').value = '';
    document.getElementById('sContent').value = '';
    openModal('scheduleModal');
}

async function createSchedule() {
    const content = document.getElementById('sContent').value.trim();
    if (!content) return alert('请输入内容');
    await api('POST', '/api/schedules', {
        company_id: currentCompanyId,
        event_date: document.getElementById('sDate').value,
        content,
        status: document.getElementById('sStatus').value
    });
    closeModal('scheduleModal');
    loadSchedules();
}

// 修改时间：2026/05/09 - 日程状态切换 + 删除
const SCH_STATUS_CYCLE = ['待进行', '已完成'];
const SCH_STATUS_CLASS = { '待进行': 'tag-gray', '已完成': 'tag-green' };

async function cycleScheduleStatus(id, currentStatus) {
    const idx = SCH_STATUS_CYCLE.indexOf(currentStatus);
    const newStatus = SCH_STATUS_CYCLE[(idx + 1) % SCH_STATUS_CYCLE.length];
    await api('PUT', `/api/schedules/${id}`, { status: newStatus });
    loadSchedules();
}

async function deleteSchedule(id) {
    if (!confirm('确定删除此日程？')) return;
    await api('DELETE', `/api/schedules/${id}`);
    loadSchedules();
}

// ==================== 项目展开 ====================

function toggleProj(id) {
    document.getElementById(id).classList.toggle('open');
}

// ==================== Tab ====================

function switchTab(tabId, el) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-item').forEach(t => t.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    el.classList.add('active');
}

// ==================== 弹窗 ====================

function openModal(id) { document.getElementById(id).classList.add('active'); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); }
document.querySelectorAll('.modal-overlay').forEach(o => {
    o.addEventListener('click', e => { if (e.target === o) o.classList.remove('active'); });
});

// ==================== 返回顶部 ====================

document.getElementById('wsContent').addEventListener('scroll', function () {
    document.getElementById('backTop').classList.toggle('show', this.scrollTop > 300);
});

// ==================== 设置 ====================

// 修改时间：2026/05/09 - AI多配置管理
let aiProfiles = [];
let aiActiveIdx = -1;
let aiEditingIdx = -1;

async function loadConfig() {
    const config = await api('GET', '/api/config');
    // AI状态
    if (config.ai_enabled && config.ai_api_key) {
        document.getElementById('aiDot').className = 'ai-dot on';
        document.getElementById('aiLabel').textContent = 'AI 已连接';
    } else {
        document.getElementById('aiDot').className = 'ai-dot off';
        document.getElementById('aiLabel').textContent = 'AI 未配置';
    }
    // 设置弹窗填充
    const toggle = document.getElementById('aiToggle');
    if (config.ai_enabled) toggle.classList.add('on'); else toggle.classList.remove('on');
    document.getElementById('aiConfigArea').style.display = config.ai_enabled ? 'block' : 'none';
    // 加载多配置
    await loadAIProfiles();
    // 修改时间：2026/05/09 - 加载超时和tokens配置
    document.getElementById('aiTimeout').value = config.ai_timeout || 180;
    document.getElementById('aiMaxTokens').value = config.ai_max_tokens || 8192;
    document.getElementById('exportDir').value = config.export_dir || '';
    fontScale = config.font_scale || 100;
    document.getElementById('fontSizeLabel').textContent = fontScale + '%';
}

async function loadAIProfiles() {
    const res = await api('GET', '/api/ai/profiles');
    aiProfiles = res.profiles || [];
    aiActiveIdx = res.active ?? -1;
    renderProfileCards();
    // 自动选中活跃的配置
    if (aiProfiles.length > 0 && aiActiveIdx >= 0 && aiActiveIdx < aiProfiles.length) {
        selectAIProfile(aiActiveIdx);
    } else if (aiProfiles.length > 0) {
        selectAIProfile(0);
    } else {
        aiEditingIdx = -1;
        document.getElementById('aiProfileEditor').style.display = 'none';
    }
}

function renderProfileCards() {
    const container = document.getElementById('aiProfileList');
    container.innerHTML = '';
    aiProfiles.forEach((p, i) => {
        const card = document.createElement('div');
        card.className = 'ai-profile-card' + (i === aiActiveIdx ? ' active' : '');
        card.innerHTML = `<span class="ap-name">${p.name || '未命名'}</span>`;
        card.onclick = () => selectAIProfile(i);
        container.appendChild(card);
    });
}

function selectAIProfile(idx) {
    // 先保存当前编辑的
    if (aiEditingIdx >= 0 && aiEditingIdx < aiProfiles.length) {
        saveCurrentProfileToMemory();
    }
    aiActiveIdx = idx;
    aiEditingIdx = idx;
    renderProfileCards();
    // 填充编辑器
    const p = aiProfiles[idx];
    document.getElementById('profileName').value = p.name || '';
    document.getElementById('aiProvider').value = p.provider || 'claude';
    document.getElementById('aiKey').value = p.api_key || '';
    document.getElementById('baseUrl').value = p.base_url || 'https://api.anthropic.com';
    changeProvider();
    const useCustom = p.use_custom_model || false;
    document.getElementById('useCustomModel').checked = useCustom;
    if (useCustom) {
        document.getElementById('customModel').value = p.model || '';
    } else {
        document.getElementById('modelSelect').value = p.model || 'claude-sonnet-4-6';
    }
    toggleCustomModel();
    document.getElementById('aiProfileEditor').style.display = 'block';
}

function saveCurrentProfileToMemory() {
    if (aiEditingIdx < 0 || aiEditingIdx >= aiProfiles.length) return;
    const modelSelect = document.getElementById('modelSelect');
    const useCustom = document.getElementById('useCustomModel').checked;
    const model = useCustom ? document.getElementById('customModel').value : modelSelect.value;
    aiProfiles[aiEditingIdx] = {
        name: document.getElementById('profileName').value || '未命名',
        provider: document.getElementById('aiProvider').value,
        api_key: document.getElementById('aiKey').value,
        base_url: document.getElementById('baseUrl').value,
        model: model,
        use_custom_model: useCustom
    };
}

function addAIProfile() {
    aiProfiles.push({
        name: '新配置',
        provider: 'claude',
        api_key: '',
        base_url: 'https://api.anthropic.com',
        model: 'claude-sonnet-4-6',
        use_custom_model: false
    });
    aiActiveIdx = aiProfiles.length - 1;
    selectAIProfile(aiActiveIdx);
}

function deleteAIProfile() {
    if (aiProfiles.length <= 0) return;
    if (!confirm('确认删除此配置？')) return;
    aiProfiles.splice(aiEditingIdx, 1);
    aiEditingIdx = -1;
    if (aiActiveIdx >= aiProfiles.length) aiActiveIdx = aiProfiles.length - 1;
    renderProfileCards();
    if (aiProfiles.length > 0) {
        selectAIProfile(Math.min(aiActiveIdx, aiProfiles.length - 1));
    } else {
        document.getElementById('aiProfileEditor').style.display = 'none';
    }
}

function toggleAI() {
    const t = document.getElementById('aiToggle');
    t.classList.toggle('on');
    document.getElementById('aiConfigArea').style.display = t.classList.contains('on') ? 'block' : 'none';
}

function changeProvider() {
    const p = document.getElementById('aiProvider').value, url = document.getElementById('baseUrl'), ms = document.getElementById('modelSelect');
    if (p === 'claude') { url.value = 'https://api.anthropic.com'; ms.innerHTML = '<option value="claude-sonnet-4-6">Claude Sonnet 4.6（推荐）</option><option value="claude-opus-4-6">Claude Opus 4.6（最强）</option><option value="claude-haiku-4-5">Claude Haiku 4.5（最快）</option>'; }
    else if (p === 'openai') { url.value = 'https://api.openai.com/v1'; ms.innerHTML = '<option value="gpt-4o">GPT-4o</option><option value="gpt-4o-mini">GPT-4o Mini</option><option value="o1">o1</option>'; }
    else { url.value = ''; ms.innerHTML = '<option>请输入自定义模型</option>'; }
}

function toggleCustomModel() {
    const c = document.getElementById('useCustomModel').checked;
    document.getElementById('customModel').style.display = c ? 'block' : 'none';
    document.getElementById('modelSelect').style.display = c ? 'none' : 'block';
}

async function testAI() {
    const modelSelect = document.getElementById('modelSelect');
    const useCustom = document.getElementById('useCustomModel').checked;
    const model = useCustom ? document.getElementById('customModel').value : modelSelect.value;
    const res = await api('POST', '/api/ai/test', {
        ai_enabled: document.getElementById('aiToggle').classList.contains('on'),
        ai_provider: document.getElementById('aiProvider').value,
        ai_api_key: document.getElementById('aiKey').value,
        ai_base_url: document.getElementById('baseUrl').value,
        ai_model: model
    });
    if (res.ok) {
        document.getElementById('aiDot').className = 'ai-dot on';
        document.getElementById('aiLabel').textContent = 'AI 已连接';
        alert('✅ 连接成功！');
    } else {
        alert('❌ 连接失败：' + (res.message || '未知错误'));
    }
}

async function saveSettings() {
    // 修改时间：2026/05/09 - 保存当前编辑的profile到内存
    if (aiEditingIdx >= 0 && aiEditingIdx < aiProfiles.length) {
        saveCurrentProfileToMemory();
    }
    // 保存profiles
    await api('PUT', '/api/ai/profiles', {
        profiles: aiProfiles,
        active: aiActiveIdx
    });
    // 保存其他设置
    await api('PUT', '/api/config', {
        ai_enabled: document.getElementById('aiToggle').classList.contains('on'),
        ai_timeout: parseInt(document.getElementById('aiTimeout').value) || 180,
        ai_max_tokens: parseInt(document.getElementById('aiMaxTokens').value) || 8192,
        font_scale: fontScale,
        export_format: document.getElementById('exportFormat').value,
        export_dir: document.getElementById('exportDir').value
    });
    closeModal('settingsModal');
    loadConfig();
}

// ==================== 字体 ====================

function changeFont(delta) {
    fontScale = Math.max(80, Math.min(150, fontScale + delta));
    document.body.style.fontSize = (12 * fontScale / 100) + 'px';
    document.getElementById('fontSizeLabel').textContent = fontScale + '%';
}
function resetFont() { fontScale = 100; changeFont(0); }

// ==================== 报告导出 ====================

// 修改时间：2026/05/12 - 项目管理HTML导出
function exportProjectsHtml() {
    window.open('/api/export/projects-html?company_id=' + currentCompanyId, '_blank');
}

// 修改时间：2026/05/12 - 导出功能完善：后端直接保存到指定目录，前端提示路径
async function exportReport() {
    const checks = document.querySelectorAll('#reportChecks input[type="checkbox"]');
    const sections = {};
    checks.forEach(c => { sections[c.value] = c.checked; });
    const format = document.getElementById('reportFormat').value;
    const filename = document.getElementById('reportFileName').value.trim();
    const exportDir = document.getElementById('reportExportDir').value.trim();

    try {
        const res = await api('POST', '/api/export', {
            company_id: currentCompanyId,
            sections,
            format,
            filename,
            export_dir: exportDir
        });

        if (res.ok) {
            alert('报告已保存到：' + res.path);
        } else {
            alert(res.message || '导出失败');
        }
    } catch (e) {
        alert('导出失败：' + e.message);
    }
    closeModal('reportModal');
}

// ==================== 浏览目录 ====================

let browseTargetId = null;

async function openBrowser(targetId) {
    browseTargetId = targetId;
    // 初始路径用当前值或桌面
    const current = document.getElementById(targetId).value || '';
    openModal('browseModal');
    await browseTo(current);
}

async function browseTo(path) {
    const res = await api('GET', `/api/browse?path=${encodeURIComponent(path || '')}`);
    document.getElementById('browsePath').value = res.current;
    const list = document.getElementById('browseList');
    list.innerHTML = '';
    // 返回上级
    if (res.parent && res.parent !== res.current) {
        list.innerHTML += `<div style="padding:8px 12px;cursor:pointer;display:flex;align-items:center;gap:8px;border-bottom:1px solid #f5f7fa;font-size:12px;color:#8c93a8" onmouseover="this.style.background='#f5f7ff'" onmouseout="this.style.background=''" onclick="browseTo('${res.parent.replace(/\\/g,'\\\\')}')">📁 ..</div>`;
    }
    res.dirs.forEach(d => {
        const escPath = d.path.replace(/\\/g, '\\\\');
        list.innerHTML += `<div style="padding:8px 12px;cursor:pointer;display:flex;align-items:center;gap:8px;border-bottom:1px solid #f5f7fa;font-size:12px;color:#3c4257" onmouseover="this.style.background='#f5f7ff'" onmouseout="this.style.background=''" onclick="browseTo('${escPath}')">📁 ${esc(d.name)}</div>`;
    });
    if (res.dirs.length === 0) {
        list.innerHTML += '<div style="padding:20px;text-align:center;color:#b0b5c8;font-size:12px">此目录下没有子文件夹</div>';
    }
}

function confirmBrowse() {
    const path = document.getElementById('browsePath').value;
    if (browseTargetId && path) {
        document.getElementById(browseTargetId).value = path;
        // 如果是项目详情里的input，触发保存
        document.getElementById(browseTargetId).dispatchEvent(new Event('change'));
    }
    closeModal('browseModal');
}

// ==================== 工具函数 ====================

function esc(str) {
    if (!str) return '';
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

// ==================== 初始化 ====================

document.addEventListener('DOMContentLoaded', () => {
    loadCompanies();
});
