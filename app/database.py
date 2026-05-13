# 数据库管理模块
# 修改时间：2026/05/08
# 功能：SQLite数据库建表和CRUD操作

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data.db")


def get_conn():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """初始化数据库，创建所有表"""
    conn = get_conn()
    c = conn.cursor()

    # 公司表
    c.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        department TEXT DEFAULT '',
        position TEXT DEFAULT '',
        superior TEXT DEFAULT '',
        start_date TEXT DEFAULT '',
        leave_date TEXT DEFAULT '',
        note TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # 模块表（支持无限嵌套，parent_id自引用）
    # 修改时间：2026/05/09 - 新增default_project_path字段
    c.execute("""
    CREATE TABLE IF NOT EXISTS modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        parent_id INTEGER DEFAULT NULL,
        name TEXT NOT NULL,
        note TEXT DEFAULT '',
        default_project_path TEXT DEFAULT '',
        sort_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
        FOREIGN KEY (parent_id) REFERENCES modules(id) ON DELETE CASCADE
    )""")
    # 兼容旧数据库：尝试添加default_project_path列
    try:
        c.execute("ALTER TABLE modules ADD COLUMN default_project_path TEXT DEFAULT ''")
    except Exception:
        pass

    # 项目表
    c.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        version TEXT DEFAULT '',
        status TEXT DEFAULT '进行中',
        project_path TEXT DEFAULT '',
        tech_stack TEXT DEFAULT '',
        git_url TEXT DEFAULT '',
        description TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
    )""")

    # 文档表
    c.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        project_id INTEGER DEFAULT NULL,
        name TEXT NOT NULL,
        file_path TEXT DEFAULT '',
        file_type TEXT DEFAULT '',
        ai_summary TEXT DEFAULT '',
        ai_analyzed INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
    )""")

    # 账号交接表
    c.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        platform TEXT NOT NULL,
        account_type TEXT DEFAULT '',
        usage_desc TEXT DEFAULT '',
        status TEXT DEFAULT '待交接',
        note TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
    )""")

    # 待办事项表
    c.execute("""
    CREATE TABLE IF NOT EXISTS todos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        priority TEXT DEFAULT '普通',
        status TEXT DEFAULT '进行中',
        project_id INTEGER DEFAULT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
    )""")

    # 联系人表
    c.execute("""
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        role TEXT DEFAULT '',
        handover_scope TEXT DEFAULT '',
        contact_info TEXT DEFAULT '',
        note TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
    )""")

    # 交接日程表
    c.execute("""
    CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        event_date TEXT NOT NULL,
        content TEXT NOT NULL,
        status TEXT DEFAULT '待进行',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
    )""")

    # Git命令模板表
    c.execute("""
    CREATE TABLE IF NOT EXISTS git_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        commands TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
    )""")

    conn.commit()
    conn.close()
