# 数据模型
# 修改时间：2026/05/08
# 功能：定义数据类

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Company:
    id: int = 0
    name: str = ""
    department: str = ""
    position: str = ""
    superior: str = ""
    start_date: str = ""
    leave_date: str = ""
    note: str = ""
    created_at: str = ""


@dataclass
class Module:
    id: int = 0
    company_id: int = 0
    parent_id: Optional[int] = None
    name: str = ""
    note: str = ""
    sort_order: int = 0
    created_at: str = ""
    # 运行时属性，不存数据库
    sub_modules: list = field(default_factory=list)
    projects: list = field(default_factory=list)


@dataclass
class Project:
    id: int = 0
    module_id: int = 0
    name: str = ""
    version: str = ""
    status: str = "进行中"
    project_path: str = ""
    tech_stack: str = ""
    git_url: str = ""
    description: str = ""
    created_at: str = ""


@dataclass
class Document:
    id: int = 0
    company_id: int = 0
    project_id: Optional[int] = None
    name: str = ""
    file_path: str = ""
    file_type: str = ""
    ai_summary: str = ""
    ai_analyzed: bool = False
    created_at: str = ""


@dataclass
class Account:
    id: int = 0
    company_id: int = 0
    platform: str = ""
    account_type: str = ""
    usage_desc: str = ""
    status: str = "待交接"
    note: str = ""
    created_at: str = ""


@dataclass
class Todo:
    id: int = 0
    company_id: int = 0
    title: str = ""
    description: str = ""
    priority: str = "普通"
    status: str = "进行中"
    project_id: Optional[int] = None
    created_at: str = ""


@dataclass
class Contact:
    id: int = 0
    company_id: int = 0
    name: str = ""
    role: str = ""
    handover_scope: str = ""
    contact_info: str = ""
    note: str = ""
    created_at: str = ""


@dataclass
class Schedule:
    id: int = 0
    company_id: int = 0
    event_date: str = ""
    content: str = ""
    status: str = "待进行"
    created_at: str = ""


@dataclass
class GitTemplate:
    id: int = 0
    company_id: int = 0
    name: str = ""
    commands: str = ""  # JSON字符串，命令列表
    created_at: str = ""
