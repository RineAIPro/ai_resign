# 离职交接助手 - Flask Web入口
# 修改时间：2026/05/08
# 功能：Flask后端API + 页面渲染

import os
import json
import asyncio
import webbrowser
import threading
from datetime import datetime, date

from flask import Flask, jsonify, request, render_template, send_file, Response, stream_with_context
from app.database import init_db, get_conn
from app.config import load_config, save_config
from app.git_service import GitService
from app.ai_service import AIService

app = Flask(__name__)
init_db()


# ==================== 页面 ====================

@app.route('/')
def index():
    return render_template('index.html')


# ==================== 公司 ====================

@app.route('/api/companies', methods=['GET'])
def get_companies():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM companies ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/companies', methods=['POST'])
def create_company():
    d = request.json
    if not d or not d.get('name'):
        return jsonify({"error": "公司名称不能为空"}), 400
    conn = get_conn()
    conn.execute(
        "INSERT INTO companies (name,department,position,superior,start_date,leave_date,note) VALUES (?,?,?,?,?,?,?)",
        (d['name'], d.get('department', ''), d.get('position', ''), '',
         d.get('start_date', ''), d.get('leave_date', ''), d.get('note', ''))
    )
    conn.commit()
    cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return jsonify({"id": cid}), 201


@app.route('/api/companies/<int:cid>', methods=['GET'])
def get_company(cid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "公司不存在"}), 404
    return jsonify(dict(row))


@app.route('/api/companies/<int:cid>', methods=['DELETE'])
def delete_company(cid):
    conn = get_conn()
    conn.execute("DELETE FROM companies WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route('/api/companies/<int:cid>/stats', methods=['GET'])
def get_company_stats(cid):
    """交接统计：有数据的类别才参与平均，无固定权重"""
    # 修改时间：2026/05/09 - 动态权重+新增日程完成率
    conn = get_conn()
    # 项目
    proj_total = conn.execute(
        "SELECT COUNT(*) c FROM projects p JOIN modules m ON p.module_id=m.id WHERE m.company_id=?", (cid,)
    ).fetchone()["c"]
    proj_done = conn.execute(
        "SELECT COUNT(*) c FROM projects p JOIN modules m ON p.module_id=m.id WHERE m.company_id=? AND p.status='已完成'", (cid,)
    ).fetchone()["c"]

    # 待办
    todo_total = conn.execute("SELECT COUNT(*) c FROM todos WHERE company_id=?", (cid,)).fetchone()["c"]
    todo_done = conn.execute("SELECT COUNT(*) c FROM todos WHERE company_id=? AND status='已完成'", (cid,)).fetchone()["c"]
    todo_active = todo_total - todo_done

    # 账号
    acc_total = conn.execute("SELECT COUNT(*) c FROM accounts WHERE company_id=?", (cid,)).fetchone()["c"]
    acc_done = conn.execute("SELECT COUNT(*) c FROM accounts WHERE company_id=? AND status='已交接'", (cid,)).fetchone()["c"]

    # 日程
    sch_total = conn.execute("SELECT COUNT(*) c FROM schedules WHERE company_id=?", (cid,)).fetchone()["c"]
    sch_done = conn.execute("SELECT COUNT(*) c FROM schedules WHERE company_id=? AND status='已完成'", (cid,)).fetchone()["c"]

    doc_count = conn.execute("SELECT COUNT(*) c FROM documents WHERE company_id=?", (cid,)).fetchone()["c"]
    conn.close()

    # 所有项目/待办/账号/日程按完成总数/总数量统一计算
    total_items = proj_total + todo_total + acc_total + sch_total
    done_items = proj_done + todo_done + acc_done + sch_done
    progress = round(done_items / total_items * 100) if total_items > 0 else 0

    return jsonify({
        "project_count": proj_total,
        "todo_count": todo_active,
        "doc_count": doc_count,
        "progress": progress
    })


# 修改时间：2026/05/09 - 公司列表页批量获取进度
@app.route('/api/companies/stats-batch', methods=['GET'])
def get_companies_stats_batch():
    """批量获取公司进度统计，用于公司列表页显示真实进度"""
    ids_str = request.args.get('ids', '')
    if not ids_str:
        return jsonify({})
    ids = [int(x) for x in ids_str.split(',') if x.strip().isdigit()]
    if not ids:
        return jsonify({})

    conn = get_conn()

    # 一次性查出所有相关数据
    proj_rows = conn.execute(
        "SELECT m.company_id, COUNT(*) c FROM projects p JOIN modules m ON p.module_id=m.id WHERE m.company_id IN ({}) GROUP BY m.company_id"
        .format(','.join('?' * len(ids))), ids
    ).fetchall()
    proj_done_rows = conn.execute(
        "SELECT m.company_id, COUNT(*) c FROM projects p JOIN modules m ON p.module_id=m.id WHERE m.company_id IN ({}) AND p.status='已完成' GROUP BY m.company_id"
        .format(','.join('?' * len(ids))), ids
    ).fetchall()
    todo_rows = conn.execute(
        "SELECT company_id, COUNT(*) c FROM todos WHERE company_id IN ({}) GROUP BY company_id"
        .format(','.join('?' * len(ids))), ids
    ).fetchall()
    todo_done_rows = conn.execute(
        "SELECT company_id, COUNT(*) c FROM todos WHERE company_id IN ({}) AND status='已完成' GROUP BY company_id"
        .format(','.join('?' * len(ids))), ids
    ).fetchall()
    acc_rows = conn.execute(
        "SELECT company_id, COUNT(*) c FROM accounts WHERE company_id IN ({}) GROUP BY company_id"
        .format(','.join('?' * len(ids))), ids
    ).fetchall()
    acc_done_rows = conn.execute(
        "SELECT company_id, COUNT(*) c FROM accounts WHERE company_id IN ({}) AND status='已交接' GROUP BY company_id"
        .format(','.join('?' * len(ids))), ids
    ).fetchall()
    sch_rows = conn.execute(
        "SELECT company_id, COUNT(*) c FROM schedules WHERE company_id IN ({}) GROUP BY company_id"
        .format(','.join('?' * len(ids))), ids
    ).fetchall()
    sch_done_rows = conn.execute(
        "SELECT company_id, COUNT(*) c FROM schedules WHERE company_id IN ({}) AND status='已完成' GROUP BY company_id"
        .format(','.join('?' * len(ids))), ids
    ).fetchall()
    doc_rows = conn.execute(
        "SELECT company_id, COUNT(*) c FROM documents WHERE company_id IN ({}) GROUP BY company_id"
        .format(','.join('?' * len(ids))), ids
    ).fetchall()
    conn.close()

    # 转为 dict
    def to_dict(rows):
        return {r['company_id']: r['c'] for r in rows}

    proj_map = to_dict(proj_rows)
    proj_done_map = to_dict(proj_done_rows)
    todo_map = to_dict(todo_rows)
    todo_done_map = to_dict(todo_done_rows)
    acc_map = to_dict(acc_rows)
    acc_done_map = to_dict(acc_done_rows)
    sch_map = to_dict(sch_rows)
    sch_done_map = to_dict(sch_done_rows)
    doc_map = to_dict(doc_rows)

    result = {}
    for cid in ids:
        proj_total = proj_map.get(cid, 0)
        proj_done = proj_done_map.get(cid, 0)
        todo_total = todo_map.get(cid, 0)
        todo_done = todo_done_map.get(cid, 0)
        acc_total = acc_map.get(cid, 0)
        acc_done = acc_done_map.get(cid, 0)
        sch_total = sch_map.get(cid, 0)
        sch_done = sch_done_map.get(cid, 0)

        total_items = proj_total + todo_total + acc_total + sch_total
        done_items = proj_done + todo_done + acc_done + sch_done
        progress = round(done_items / total_items * 100) if total_items > 0 else 0

        result[str(cid)] = {
            "project_count": proj_total,
            "todo_count": todo_total - todo_done,
            "doc_count": doc_map.get(cid, 0),
            "progress": progress
        }

    return jsonify(result)


@app.route('/api/companies/<int:cid>/countdown', methods=['GET'])
def get_countdown(cid):
    conn = get_conn()
    row = conn.execute("SELECT leave_date FROM companies WHERE id=?", (cid,)).fetchone()
    conn.close()
    if not row or not row["leave_date"]:
        return jsonify({"days": None, "leave_date": ""})
    try:
        d = datetime.strptime(row["leave_date"], "%Y-%m-%d").date()
        days = max(0, (d - date.today()).days)
        return jsonify({"days": days, "leave_date": row["leave_date"]})
    except ValueError:
        return jsonify({"days": 0, "leave_date": row["leave_date"]})


# ==================== 模块 ====================

@app.route('/api/modules', methods=['GET'])
def get_modules():
    """获取模块列表，项目数递归统计所有子孙模块的项目"""
    # 修改时间：2026/05/08 - 修复主模块项目数统计，递归累加子模块项目
    company_id = request.args.get('company_id', type=int)
    if not company_id:
        return jsonify([])
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM modules WHERE company_id=? ORDER BY sort_order, id", (company_id,)
    ).fetchall()
    modules = [dict(r) for r in rows]

    # 构建父子关系树
    children_map = {}  # parent_id -> [子模块列表]
    for m in modules:
        pid = m['parent_id']
        if pid not in children_map:
            children_map[pid] = []
        children_map[pid].append(m)

    # 查询该公司所有项目按 module_id 分组计数
    proj_rows = conn.execute(
        """SELECT m.id AS module_id, COUNT(p.id) AS cnt
           FROM modules m LEFT JOIN projects p ON p.module_id = m.id
           WHERE m.company_id = ?
           GROUP BY m.id""", (company_id,)
    ).fetchall()
    direct_count = {row['module_id']: row['cnt'] for row in proj_rows}
    conn.close()

    # 递归计算每个模块的总项目数（自身 + 所有子孙模块）
    def calc_total(mod_id):
        total = direct_count.get(mod_id, 0)
        for child in children_map.get(mod_id, []):
            total += calc_total(child['id'])
        return total

    result = []
    for m in modules:
        m['project_count'] = calc_total(m['id'])
        result.append(m)

    return jsonify(result)


@app.route('/api/modules', methods=['POST'])
def create_module():
    """创建模块，支持默认项目地址"""
    # 修改时间：2026/05/09 - 新增default_project_path字段
    d = request.json
    if not d or not d.get('name'):
        return jsonify({"error": "模块名称不能为空"}), 400
    conn = get_conn()
    conn.execute(
        "INSERT INTO modules (company_id,parent_id,name,note,default_project_path) VALUES (?,?,?,?,?)",
        (d.get('company_id'), d.get('parent_id'), d['name'], d.get('note', ''), d.get('default_project_path', ''))
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 201


# 修改时间：2026/05/09 - 新增模块编辑接口
@app.route('/api/modules/<int:mid>', methods=['PUT'])
def update_module(mid):
    """编辑模块（名称、备注、默认项目地址）"""
    d = request.json
    conn = get_conn()
    fields = []
    values = []
    for key in ['name', 'note', 'default_project_path']:
        if key in d:
            fields.append(f"{key}=?")
            values.append(d[key])
    if fields:
        values.append(mid)
        conn.execute(f"UPDATE modules SET {','.join(fields)} WHERE id=?", values)
        conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route('/api/modules/<int:mid>', methods=['DELETE'])
def delete_module(mid):
    conn = get_conn()
    conn.execute("DELETE FROM modules WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ==================== 项目 ====================

@app.route('/api/projects', methods=['GET'])
def get_projects():
    module_id = request.args.get('module_id', type=int)
    if not module_id:
        return jsonify([])
    conn = get_conn()
    rows = conn.execute("SELECT * FROM projects WHERE module_id=? ORDER BY id", (module_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/projects', methods=['POST'])
def create_project():
    d = request.json
    if not d or not d.get('name'):
        return jsonify({"error": "项目名称不能为空"}), 400
    conn = get_conn()
    conn.execute(
        "INSERT INTO projects (module_id,name,version,status,project_path) VALUES (?,?,?,?,?)",
        (d.get('module_id'), d['name'], d.get('version', ''), d.get('status', '进行中'), d.get('project_path', ''))
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 201


@app.route('/api/projects/<int:pid>', methods=['PUT'])
def update_project(pid):
    d = request.json
    conn = get_conn()
    fields = []
    values = []
    for key in ['name', 'version', 'status', 'project_path', 'tech_stack', 'git_url', 'description']:
        if key in d:
            fields.append(f"{key}=?")
            values.append(d[key])
    if fields:
        values.append(pid)
        conn.execute(f"UPDATE projects SET {','.join(fields)} WHERE id=?", values)
        conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route('/api/projects/<int:pid>', methods=['DELETE'])
def delete_project(pid):
    conn = get_conn()
    conn.execute("DELETE FROM projects WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route('/api/projects/<int:pid>/auto-generate', methods=['POST'])
def auto_generate(pid):
    """自动生成技术栈、Git地址、简介"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "项目不存在"}), 404

    proj_path = row["project_path"]
    result = {}
    if proj_path and os.path.isdir(proj_path):
        # 扫描技术栈
        result["tech_stack"] = _scan_tech_stack(proj_path)
        # 读取Git地址
        result["git_url"] = _read_git_url(proj_path)
        # 读取README
        result["description"] = _read_readme(proj_path)

    # 更新数据库
    if result:
        conn = get_conn()
        sets = []
        vals = []
        for k, v in result.items():
            sets.append(f"{k}=?")
            vals.append(v)
        vals.append(pid)
        conn.execute(f"UPDATE projects SET {','.join(sets)} WHERE id=?", vals)
        conn.commit()
        conn.close()

    return jsonify(result)


# 修改时间：2026/05/09 - AI生成交接文档
@app.route('/api/projects/<int:pid>/generate-doc', methods=['POST'])
def generate_handover_doc(pid):
    """AI生成交接文档，保存到项目路径/jiaojie/交接文档.md"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "项目不存在"}), 404

    proj_path = row["project_path"]
    if not proj_path or not os.path.isdir(proj_path):
        conn.close()
        return jsonify({"error": "项目路径无效，请先填写项目地址"}), 400

    # 获取公司信息作为上下文
    company_row = conn.execute(
        "SELECT c.name FROM companies c JOIN modules m ON m.company_id=c.id WHERE m.id=?",
        (row["module_id"],)
    ).fetchone()
    conn.close()
    company_name = company_row["name"] if company_row else ""

    # 构建文档内容
    # 修改时间：2026/05/09 - 按resign_doc下每个模板生成独立的md文件
    config = load_config()
    ai_enabled = config.get("ai_enabled") and config.get("ai_api_key")

    # 扫描所有模板文件
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resign_doc")
    template_files = sorted([f for f in os.listdir(template_dir) if f.endswith('.md')]) if os.path.isdir(template_dir) else []

    # 保存到项目路径/jiaojie/
    jiaojie_dir = os.path.join(proj_path, "jiaojie")
    os.makedirs(jiaojie_dir, exist_ok=True)

    generated_files = []
    if ai_enabled and template_files:
        ai = AIService(config)
        for tpl_file in template_files:
            tpl_path = os.path.join(template_dir, tpl_file)
            with open(tpl_path, "r", encoding="utf-8") as f:
                tpl_content = f.read()
            prompt = _build_doc_prompt_from_template(row, company_name, tpl_content)
            print(f"[INFO] 按模板 {tpl_file} 生成中...")
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                doc_content = loop.run_until_complete(ai.generate_text(prompt, "你是一个专业的技术文档撰写助手，请用中文输出。"))
                loop.close()
            except Exception as e:
                import traceback
                print(f"[ERROR] 模板 {tpl_file} 生成失败：{type(e).__name__}: {repr(e)}")
                traceback.print_exc()
                return jsonify({"error": f"模板 {tpl_file} AI生成失败：{type(e).__name__}: {e}"}), 500
            # 输出文件名：去掉"模板"二字，如 交接模板1.md -> 交接1.md
            out_name = tpl_file.replace("模板", "")
            out_path = os.path.join(jiaojie_dir, out_name)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(doc_content)
            generated_files.append({"name": out_name, "path": out_path})
    else:
        # AI未配置或无模板，生成一个默认文档
        doc_content = _build_template_doc(row, company_name)
        out_path = os.path.join(jiaojie_dir, "交接文档.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(doc_content)
        generated_files.append({"name": "交接文档.md", "path": out_path})

    return jsonify({"ok": True, "files": generated_files})


@app.route('/api/projects/<int:pid>/read-doc', methods=['GET'])
def read_handover_doc(pid):
    """读取交接文档列表，支持多文件"""
    # 修改时间：2026/05/09 - 返回jiaojie目录下所有md文件
    conn = get_conn()
    row = conn.execute("SELECT project_path FROM projects WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not row or not row["project_path"]:
        return jsonify({"error": "项目路径无效"}), 400
    jiaojie_dir = os.path.join(row["project_path"], "jiaojie")
    if not os.path.isdir(jiaojie_dir):
        return jsonify({"error": "交接文档尚未生成"}), 404
    files = []
    for fname in sorted(os.listdir(jiaojie_dir)):
        if fname.endswith('.md'):
            fpath = os.path.join(jiaojie_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            files.append({"name": fname, "content": content, "path": fpath})
    if not files:
        return jsonify({"error": "交接文档尚未生成"}), 404
    return jsonify({"ok": True, "files": files})


def _scan_project_structure(path, max_depth=5):
    """扫描项目目录结构，返回详细树形文本"""
    # 修改时间：2026/05/09 - 增加扫描深度和文件数量，生成详细结构
    ignore_dirs = {'.git', '.idea', '.gradle', 'build', 'node_modules', '__pycache__',
                   '.vscode', 'dist', 'target', '.mvn', 'vendor', 'Pods', '.next', 'jiaojie'}
    ignore_exts = {'.class', '.jar', '.apk', '.aab', '.png', '.jpg', '.jpeg', '.gif',
                   '.ico', '.so', '.dll', '.exe', '.obj', '.o', '.pyc'}
    lines = []

    def _scan(dir_path, depth, prefix=""):
        if depth > max_depth:
            return
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return
        dirs = []
        files = []
        for e in entries:
            full = os.path.join(dir_path, e)
            if os.path.isdir(full):
                if e not in ignore_dirs and not e.startswith('.'):
                    dirs.append(e)
            else:
                _, ext = os.path.splitext(e)
                if ext.lower() not in ignore_exts:
                    files.append(e)
        # 显示文件，源代码类文件最多50个，其他最多10个
        src_exts = {'.java', '.kt', '.xml', '.py', '.js', '.ts', '.go', '.rs', '.swift', '.dart', '.c', '.cpp', '.h', '.gradle', '.properties', '.yaml', '.yml', '.json', '.toml'}
        src_files = [f for f in files if os.path.splitext(f)[1].lower() in src_exts]
        other_files = [f for f in files if os.path.splitext(f)[1].lower() not in src_exts]
        for f in src_files[:50]:
            lines.append(f"{prefix}{f}")
        if len(src_files) > 50:
            lines.append(f"{prefix}... 共{len(src_files)}个源码文件")
        for f in other_files[:10]:
            lines.append(f"{prefix}{f}")
        for d in dirs:
            lines.append(f"{prefix}{d}/")
            _scan(os.path.join(dir_path, d), depth + 1, prefix + "  ")

    _scan(path, 0)
    return "\n".join(lines[:500]) if lines else "（无法扫描目录结构）"


def _build_doc_prompt_from_template(row, company_name, template_content):
    """根据单个模板内容构建AI prompt"""
    # 修改时间：2026/05/09 - 支持多模板，提供详细项目结构供AI分析
    proj_path = row['project_path'] or ''
    project_structure = ""
    if proj_path and os.path.isdir(proj_path):
        project_structure = _scan_project_structure(proj_path)

    prompt = f"""请严格按照以下模板的要求生成文档内容（Markdown格式）。

【模板内容】
```
{template_content}
```

模板说明：
- `*` 表示需要用项目实际信息替换
- 模板中的说明性文字（如括号内的要求、AI写xxx等）是需要你根据项目信息生成实际内容的地方
- 生成的文档应详细、专业，参考专业技术文档的写法
- 如果模板要求写项目结构，请包含：项目概述、目录树（用代码块）、各模块/包的详细说明（用表格）、核心类说明、技术栈列表、通信架构（如适用）、权限列表（如适用）等
- 只输出模板要求的内容，不要添加模板中没有的章节

【项目信息】
- 项目名称：{row['name']}
- 所属公司：{company_name}
- 当前版本：{row['version'] or '未指定'}
- 项目状态：{row['status']}
- 技术栈：{row['tech_stack'] or '未填写'}
- Git 地址：{row['git_url'] or '未填写'}
- 项目简介：{row['description'] or '未填写'}
- 项目路径：{proj_path or '未填写'}

【项目完整目录结构（供分析）】
{project_structure}

用中文输出，只输出文档正文，不要用代码块包裹整个输出。"""

    return prompt


def _build_template_doc(row, company_name):
    """AI未配置时的模板文档，结构与 resign_doc/交接模板.md 一致"""
    # 修改时间：2026/05/09 - 改为与模板文件一致的3章节结构
    return f"""# 项目交接文档

## 1. 项目概述
- 项目名称：{row['name']}
- 所属公司：{company_name}
- 当前版本：{row['version'] or '未指定'}
- 项目状态：{row['status']}
- 技术栈：{row['tech_stack'] or '未填写'}
- Git 地址：{row['git_url'] or '未填写'}
- 简介：{row['description'] or '未填写'}

## 2. 项目架构说明
> 待补充（配置AI后可自动生成）

## 3. 相关文档和资源
> 项目路径：{row['project_path'] or '未填写'}

---
*由离职交接助手生成*
"""



def _scan_tech_stack(path):
    """扫描项目技术栈"""
    stacks = []
    checks = {
        'build.gradle': 'Gradle/Android',
        'build.gradle.kts': 'Gradle Kotlin DSL',
        'pom.xml': 'Maven/Java',
        'package.json': 'Node.js',
        'requirements.txt': 'Python',
        'go.mod': 'Go',
        'Cargo.toml': 'Rust',
        'pubspec.yaml': 'Flutter/Dart',
        'Podfile': 'iOS/CocoaPods',
    }
    for fname, tech in checks.items():
        if os.path.isfile(os.path.join(path, fname)):
            stacks.append(tech)
    return ', '.join(stacks) if stacks else ''


def _read_git_url(path):
    """读取.git/config中的远程地址"""
    # 修改时间：2026/05/08 - 修复in_remote未重置bug，支持多个remote区块
    git_config = os.path.join(path, '.git', 'config')
    if not os.path.isfile(git_config):
        return ''
    try:
        with open(git_config, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        in_origin = False
        for line in lines:
            # 检测到新的section头部时重置标志
            if line.strip().startswith('['):
                in_origin = '[remote "origin"]' in line
            elif in_origin and line.strip().startswith('url'):
                return line.split('=', 1)[1].strip()
    except Exception:
        pass
    return ''


def _read_readme(path):
    """读取README.md前200字"""
    for name in ['README.md', 'readme.md', 'README.MD']:
        readme = os.path.join(path, name)
        if os.path.isfile(readme):
            try:
                with open(readme, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read(500).strip()
            except Exception:
                pass
    return ''


# ==================== Git命令模板 ====================
# 新增时间：2026/05/08 - Git命令流程模板的CRUD接口

@app.route('/api/git-templates', methods=['GET'])
def get_git_templates():
    """获取Git命令模板列表"""
    company_id = request.args.get('company_id', type=int)
    if not company_id:
        return jsonify([])
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM git_templates WHERE company_id=? ORDER BY id DESC", (company_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/git-templates', methods=['POST'])
def create_git_template():
    """创建Git命令模板"""
    d = request.json
    if not d or not d.get('name'):
        return jsonify({"error": "模板名称不能为空"}), 400
    if not d.get('commands'):
        return jsonify({"error": "命令不能为空"}), 400
    conn = get_conn()
    conn.execute(
        "INSERT INTO git_templates (company_id, name, commands) VALUES (?,?,?)",
        (d.get('company_id'), d['name'], d['commands'])
    )
    conn.commit()
    tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return jsonify({"id": tid}), 201


@app.route('/api/git-templates/<int:tid>', methods=['PUT'])
def update_git_template(tid):
    """编辑Git命令模板"""
    d = request.json
    conn = get_conn()
    fields = []
    values = []
    for key in ['name', 'commands']:
        if key in d:
            fields.append(f"{key}=?")
            values.append(d[key])
    if fields:
        values.append(tid)
        conn.execute(f"UPDATE git_templates SET {','.join(fields)} WHERE id=?", values)
        conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route('/api/git-templates/<int:tid>', methods=['DELETE'])
def delete_git_template(tid):
    """删除Git命令模板"""
    conn = get_conn()
    conn.execute("DELETE FROM git_templates WHERE id=?", (tid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ==================== Git命令执行 ====================
# 修改时间：2026/05/08 - Git命令逐步执行和一键执行接口

@app.route('/api/git/execute', methods=['POST'])
def git_execute():
    """执行单条Git命令"""
    d = request.json
    if not d or not d.get('command'):
        return jsonify({"error": "命令不能为空"}), 400
    project_path = d.get('project_path', '')
    if not project_path or not os.path.isdir(project_path):
        return jsonify({"error": "项目路径无效"}), 400
    success, output = GitService.execute_command(project_path, d['command'])
    return jsonify({"success": success, "output": output})


@app.route('/api/git/execute-all', methods=['POST'])
def git_execute_all():
    """一键执行所有Git命令"""
    d = request.json
    if not d or not d.get('commands'):
        return jsonify({"error": "命令不能为空"}), 400
    project_path = d.get('project_path', '')
    if not project_path or not os.path.isdir(project_path):
        return jsonify({"error": "项目路径无效"}), 400
    results = GitService.execute_commands(project_path, d['commands'])
    return jsonify({
        "results": [{"success": ok, "output": out} for ok, out in results]
    })


# 修改时间：2026/05/08 - Git命令流式执行端点，实时返回输出
@app.route('/api/git/execute-stream', methods=['POST'])
def git_execute_stream():
    """流式执行Git命令，逐行返回实时输出（NDJSON格式）"""
    import json as _json
    d = request.json
    if not d or not d.get('command'):
        return jsonify({"error": "命令不能为空"}), 400
    project_path = d.get('project_path', '')
    if not project_path or not os.path.isdir(project_path):
        return jsonify({"error": "项目路径无效"}), 400

    command = d['command']

    def generate():
        for line in GitService.execute_command_stream(project_path, command):
            yield _json.dumps({"t": line}, ensure_ascii=False) + "\n"

    return Response(
        stream_with_context(generate()),
        mimetype='application/x-ndjson',
        headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'}
    )


@app.route('/api/git/execute-all-stream', methods=['POST'])
def git_execute_all_stream():
    """流式一键执行所有Git命令"""
    import json as _json
    d = request.json
    if not d or not d.get('commands'):
        return jsonify({"error": "命令不能为空"}), 400
    project_path = d.get('project_path', '')
    if not project_path or not os.path.isdir(project_path):
        return jsonify({"error": "项目路径无效"}), 400

    commands = d['commands']

    def generate():
        for line in GitService.execute_commands_stream(project_path, commands):
            yield _json.dumps({"t": line}, ensure_ascii=False) + "\n"

    return Response(
        stream_with_context(generate()),
        mimetype='application/x-ndjson',
        headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'}
    )


@app.route('/api/git/read-url', methods=['POST'])
def git_read_url():
    """直接读取项目路径下.git/config的远程URL，无需请求复杂接口"""
    # 修改时间：2026/05/08 - 简化Git地址读取，直接读.git/config，增加诊断信息
    d = request.json
    project_path = (d or {}).get('project_path', '')
    if not project_path or not os.path.isdir(project_path):
        return jsonify({"error": "项目路径无效", "git_url": ""}), 400
    git_dir = os.path.join(project_path, '.git')
    if not os.path.isdir(git_dir):
        return jsonify({"git_url": "", "message": f"未找到.git目录（已检查：{git_dir}）"})
    git_config = os.path.join(git_dir, 'config')
    if not os.path.isfile(git_config):
        return jsonify({"git_url": "", "message": f"未找到.git/config文件（已检查：{git_config}）"})
    url = _read_git_url(project_path)
    if not url:
        return jsonify({"git_url": "", "message": "在.git/config中未找到[remote \"origin\"]的url"})
    return jsonify({"git_url": url})


# ==================== 文档 ====================

@app.route('/api/documents', methods=['GET'])
def get_documents():
    company_id = request.args.get('company_id', type=int)
    if not company_id:
        return jsonify([])
    conn = get_conn()
    rows = conn.execute("SELECT * FROM documents WHERE company_id=? ORDER BY id DESC", (company_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/documents', methods=['POST'])
def create_document():
    d = request.json
    if not d or not d.get('name'):
        return jsonify({"error": "文档名称不能为空"}), 400
    conn = get_conn()
    conn.execute(
        "INSERT INTO documents (company_id,project_id,name,file_path,file_type) VALUES (?,?,?,?,?)",
        (d.get('company_id'), d.get('project_id'), d['name'], d.get('file_path', ''), d.get('file_type', ''))
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 201


@app.route('/api/documents/<int:did>', methods=['DELETE'])
def delete_document(did):
    conn = get_conn()
    conn.execute("DELETE FROM documents WHERE id=?", (did,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route('/api/documents/<int:did>/analyze', methods=['POST'])
def analyze_document(did):
    """AI分析文档（占位）"""
    conn = get_conn()
    conn.execute("UPDATE documents SET ai_analyzed=1, ai_summary='AI分析结果（待实现）' WHERE id=?", (did,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ==================== 账号 ====================

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    company_id = request.args.get('company_id', type=int)
    if not company_id:
        return jsonify([])
    conn = get_conn()
    rows = conn.execute("SELECT * FROM accounts WHERE company_id=? ORDER BY id DESC", (company_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/accounts', methods=['POST'])
def create_account():
    d = request.json
    if not d or not d.get('platform'):
        return jsonify({"error": "平台名称不能为空"}), 400
    conn = get_conn()
    conn.execute(
        "INSERT INTO accounts (company_id,platform,account_type,usage_desc,status,note) VALUES (?,?,?,?,?,?)",
        (d.get('company_id'), d['platform'], d.get('account_type', ''), d.get('usage_desc', ''), d.get('status', '待交接'), d.get('note', ''))
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 201


@app.route('/api/accounts/<int:aid>', methods=['PUT'])
def update_account(aid):
    d = request.json
    conn = get_conn()
    fields = []
    values = []
    for key in ['platform', 'account_type', 'usage_desc', 'status', 'note']:
        if key in d:
            fields.append(f"{key}=?")
            values.append(d[key])
    if fields:
        values.append(aid)
        conn.execute(f"UPDATE accounts SET {','.join(fields)} WHERE id=?", values)
        conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route('/api/accounts/<int:aid>', methods=['DELETE'])
def delete_account(aid):
    conn = get_conn()
    conn.execute("DELETE FROM accounts WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ==================== 待办 ====================

@app.route('/api/todos', methods=['GET'])
def get_todos():
    company_id = request.args.get('company_id', type=int)
    if not company_id:
        return jsonify([])
    conn = get_conn()
    rows = conn.execute("SELECT * FROM todos WHERE company_id=? ORDER BY id DESC", (company_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/todos', methods=['POST'])
def create_todo():
    d = request.json
    if not d or not d.get('title'):
        return jsonify({"error": "标题不能为空"}), 400
    conn = get_conn()
    conn.execute(
        "INSERT INTO todos (company_id,title,description,priority,status,project_id) VALUES (?,?,?,?,?,?)",
        (d.get('company_id'), d['title'], d.get('description', ''), d.get('priority', '普通'), d.get('status', '进行中'), d.get('project_id'))
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 201


@app.route('/api/todos/<int:tid>', methods=['PUT'])
def update_todo(tid):
    d = request.json
    conn = get_conn()
    fields = []
    values = []
    for key in ['title', 'description', 'priority', 'status']:
        if key in d:
            fields.append(f"{key}=?")
            values.append(d[key])
    if fields:
        values.append(tid)
        conn.execute(f"UPDATE todos SET {','.join(fields)} WHERE id=?", values)
        conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route('/api/todos/<int:tid>', methods=['DELETE'])
def delete_todo(tid):
    conn = get_conn()
    conn.execute("DELETE FROM todos WHERE id=?", (tid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ==================== 联系人 ====================

@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    company_id = request.args.get('company_id', type=int)
    if not company_id:
        return jsonify([])
    conn = get_conn()
    rows = conn.execute("SELECT * FROM contacts WHERE company_id=? ORDER BY id DESC", (company_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/contacts', methods=['POST'])
def create_contact():
    d = request.json
    if not d or not d.get('name'):
        return jsonify({"error": "姓名不能为空"}), 400
    conn = get_conn()
    conn.execute(
        "INSERT INTO contacts (company_id,name,role,handover_scope,contact_info,note) VALUES (?,?,?,?,?,?)",
        (d.get('company_id'), d['name'], d.get('role', ''), d.get('handover_scope', ''), d.get('contact_info', ''), d.get('note', ''))
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 201


@app.route('/api/contacts/<int:cid_>', methods=['PUT'])
def update_contact(cid_):
    d = request.json
    conn = get_conn()
    fields = []
    values = []
    for key in ['name', 'role', 'handover_scope', 'contact_info', 'note']:
        if key in d:
            fields.append(f"{key}=?")
            values.append(d[key])
    if fields:
        values.append(cid_)
        conn.execute(f"UPDATE contacts SET {','.join(fields)} WHERE id=?", values)
        conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route('/api/contacts/<int:cid_>', methods=['DELETE'])
def delete_contact(cid_):
    conn = get_conn()
    conn.execute("DELETE FROM contacts WHERE id=?", (cid_,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ==================== 日程 ====================

@app.route('/api/schedules', methods=['GET'])
def get_schedules():
    company_id = request.args.get('company_id', type=int)
    if not company_id:
        return jsonify([])
    conn = get_conn()
    rows = conn.execute("SELECT * FROM schedules WHERE company_id=? ORDER BY event_date, id", (company_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/schedules', methods=['POST'])
def create_schedule():
    d = request.json
    if not d or not d.get('content'):
        return jsonify({"error": "内容不能为空"}), 400
    conn = get_conn()
    conn.execute(
        "INSERT INTO schedules (company_id,event_date,content,status) VALUES (?,?,?,?)",
        (d.get('company_id'), d.get('event_date', ''), d['content'], d.get('status', '待进行'))
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True}), 201


@app.route('/api/schedules/<int:sid>', methods=['PUT'])
def update_schedule(sid):
    d = request.json
    conn = get_conn()
    fields = []
    values = []
    for key in ['event_date', 'content', 'status']:
        if key in d:
            fields.append(f"{key}=?")
            values.append(d[key])
    if fields:
        values.append(sid)
        conn.execute(f"UPDATE schedules SET {','.join(fields)} WHERE id=?", values)
        conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route('/api/schedules/<int:sid>', methods=['DELETE'])
def delete_schedule(sid):
    conn = get_conn()
    conn.execute("DELETE FROM schedules WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ==================== 配置 ====================

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(load_config())


@app.route('/api/config', methods=['PUT'])
def update_config():
    d = request.json
    if not d:
        return jsonify({"error": "无效数据"}), 400
    config = load_config()
    config.update(d)
    save_config(config)
    return jsonify({"ok": True})


@app.route('/api/ai/test', methods=['POST'])
def test_ai():
    """测试AI连接 - 实际调用AI接口验证API Key和Base URL"""
    # 修改时间：2026/05/08 - 修复占位桩，改为实际调用AI接口验证
    config = load_config()
    # 使用请求中传来的最新配置（如果有）
    d = request.json or {}
    if d:
        config.update(d)
    ai = AIService(config)
    if not config.get('ai_enabled'):
        return jsonify({"ok": False, "message": "AI功能未启用"})
    if not ai.api_key:
        return jsonify({"ok": False, "message": "API Key 未填写"})
    # 在同步Flask中运行异步测试
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success, msg = loop.run_until_complete(ai.test_connection())
        loop.close()
        return jsonify({"ok": success, "message": msg})
    except Exception as e:
        return jsonify({"ok": False, "message": f"连接异常: {str(e)}"})


# 修改时间：2026/05/09 - AI多配置管理
@app.route('/api/ai/profiles', methods=['GET'])
def get_ai_profiles():
    """获取所有AI配置"""
    config = load_config()
    return jsonify({
        "profiles": config.get("ai_profiles", []),
        "active": config.get("ai_active_profile", -1)
    })


@app.route('/api/ai/profiles', methods=['PUT'])
def save_ai_profiles():
    """保存所有AI配置"""
    # 修改时间：2026/05/09 - 保存profiles和active索引
    d = request.json
    if not d:
        return jsonify({"error": "无效数据"}), 400
    config = load_config()
    config["ai_profiles"] = d.get("profiles", [])
    config["ai_active_profile"] = d.get("active", -1)
    save_config(config)
    return jsonify({"ok": True})


# ==================== 导出 ====================

@app.route('/api/browse', methods=['GET'])
def browse_dir():
    """浏览本地目录，返回子目录列表"""
    path = request.args.get('path', '')
    # 默认路径
    if not path or not os.path.isdir(path):
        # Windows默认桌面，其他系统HOME
        path = os.path.join(os.path.expanduser('~'), 'Desktop')
        if not os.path.isdir(path):
            path = os.path.expanduser('~')
    try:
        entries = []
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            if os.path.isdir(full):
                entries.append({'name': name, 'path': full})
        return jsonify({'current': path, 'parent': os.path.dirname(path), 'dirs': entries})
    except PermissionError:
        return jsonify({'current': path, 'parent': os.path.dirname(path), 'dirs': []})


@app.route('/api/export', methods=['POST'])
def export_report():
    """生成报告并返回文件下载"""
    # 修改时间：2026/05/12 - 导出功能完善
    d = request.json or {}
    company_id = d.get('company_id')
    sections = d.get('sections', {})
    fmt = d.get('format', 'Word (.docx)')
    filename = (d.get('filename') or '').strip()
    export_dir = (d.get('export_dir') or '').strip()

    if not company_id:
        return jsonify({"ok": False, "message": "缺少公司ID"}), 400

    # 查询公司名称
    conn = get_conn()
    company = conn.execute("SELECT name FROM companies WHERE id=?", (company_id,)).fetchone()
    conn.close()
    company_name = company['name'] if company else '未知'

    # 确定导出目录
    if not export_dir:
        cfg = load_config()
        export_dir = cfg.get('export_dir', '')
    if not export_dir or not os.path.isdir(export_dir):
        export_dir = os.path.join(os.path.expanduser('~'), 'Desktop')

    # 确定文件名
    if not filename:
        today = datetime.now().strftime('%Y%m%d')
        filename = f"离职交接报告_{company_name}_{today}"
    # 过滤非法字符
    for ch in '/\\:*?"<>|':
        filename = filename.replace(ch, '_')

    # 确定扩展名
    ext = '.md' if 'Markdown' in fmt else '.docx'
    output_path = os.path.join(export_dir, filename + ext)

    try:
        import shutil
        from app.export_service import ExportService
        cfg = load_config()
        svc = ExportService(company_id, cfg)
        svc.generate_report(sections, output_path)

        # 修改时间：2026/05/12 - 导出AI交接文档，按模块层级递归建目录
        if sections.get("projects"):
            docs_dir = os.path.join(export_dir, filename + "_项目交接文档")
            conn2 = get_conn()
            # 递归复制模块下的项目交接文档
            def copy_module_docs(module_id, parent_dir):
                # 当前模块信息
                mod = conn2.execute("SELECT name FROM modules WHERE id=?", (module_id,)).fetchone()
                if not mod:
                    return
                safe_name = mod['name']
                for ch in '/\\:*?"<>|':
                    safe_name = safe_name.replace(ch, '_')
                mod_dir = os.path.join(parent_dir, safe_name)
                # 复制当前模块下的项目交接文档
                projects = conn2.execute(
                    "SELECT name, project_path FROM projects WHERE module_id=?", (module_id,)
                ).fetchall()
                for p in projects:
                    proj_path = p['project_path']
                    if not proj_path:
                        continue
                    jiaojie_dir = os.path.join(proj_path, 'jiaojie')
                    if not os.path.isdir(jiaojie_dir):
                        continue
                    md_files = [f for f in os.listdir(jiaojie_dir) if f.endswith('.md')]
                    if not md_files:
                        continue
                    safe_pname = p['name']
                    for ch in '/\\:*?"<>|':
                        safe_pname = safe_pname.replace(ch, '_')
                    proj_dest = os.path.join(mod_dir, safe_pname)
                    os.makedirs(proj_dest, exist_ok=True)
                    for md_file in md_files:
                        shutil.copy2(
                            os.path.join(jiaojie_dir, md_file),
                            os.path.join(proj_dest, md_file)
                        )
                # 递归子模块
                subs = conn2.execute("SELECT id FROM modules WHERE parent_id=?", (module_id,)).fetchall()
                for sub in subs:
                    copy_module_docs(sub['id'], mod_dir)

            # 从顶层模块开始
            top_modules = conn2.execute(
                "SELECT id FROM modules WHERE company_id=? AND parent_id IS NULL", (company_id,)
            ).fetchall()
            for mod in top_modules:
                copy_module_docs(mod['id'], docs_dir)
            conn2.close()

        # 修改时间：2026/05/12 - 改为返回保存路径，不再触发浏览器下载
        return jsonify({"ok": True, "path": output_path})
    except Exception as e:
        return jsonify({"ok": False, "message": f"导出失败：{str(e)}"}), 500


# 修改时间：2026/05/12 - 项目管理HTML导出
@app.route('/api/export/projects-html')
def export_projects_html():
    """导出项目清单为独立静态HTML"""
    from app.export_service import ExportService
    company_id = request.args.get('company_id', type=int)
    if not company_id:
        return jsonify({"error": "缺少公司ID"}), 400
    cfg = load_config()
    svc = ExportService(company_id, cfg)
    html_content = svc.generate_projects_html()
    return Response(html_content, mimetype='text/html; charset=utf-8')


# ==================== 启动 ====================

if __name__ == '__main__':
    # 自动打开浏览器
    threading.Timer(1.5, lambda: webbrowser.open('http://localhost:5000')).start()
    print("离职交接助手已启动：http://localhost:5000")
    app.run(debug=True, port=5000)
