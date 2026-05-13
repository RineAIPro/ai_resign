# 配置管理
# 修改时间：2026/05/08
# 功能：全局设置管理（AI配置、导出配置、字体缩放）

import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

# 修改时间：2026/05/09 - 新增 ai_timeout, ai_max_tokens 配置项
DEFAULT_CONFIG = {
    "ai_enabled": False,
    "ai_provider": "claude",
    "ai_api_key": "",
    "ai_base_url": "https://api.anthropic.com",
    "ai_model": "claude-sonnet-4-6",
    "use_custom_model": False,
    "ai_timeout": 180,
    "ai_max_tokens": 8192,
    "ai_profiles": [],
    "ai_active_profile": -1,
    "export_format": "Word (.docx)",
    "export_dir": "",
    "font_scale": 100,
    "auto_save": True,
}


def load_config():
    """加载配置"""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        # 合并默认值（防止新增字段缺失）
        cfg = dict(DEFAULT_CONFIG)
        cfg.update(saved)

        # 修改时间：2026/05/09 - 自动迁移旧的单配置到profiles
        if not cfg.get("ai_profiles") and cfg.get("ai_api_key"):
            cfg["ai_profiles"] = [{
                "name": "默认配置",
                "provider": cfg.get("ai_provider", "claude"),
                "api_key": cfg["ai_api_key"],
                "base_url": cfg.get("ai_base_url", "https://api.anthropic.com"),
                "model": cfg.get("ai_model", ""),
                "use_custom_model": cfg.get("use_custom_model", False),
            }]
            cfg["ai_active_profile"] = 0
            save_config(cfg)

        # 将active profile合并到顶层字段，其他代码无需改动
        profiles = cfg.get("ai_profiles", [])
        active_idx = cfg.get("ai_active_profile", -1)
        if profiles and 0 <= active_idx < len(profiles):
            profile = profiles[active_idx]
            for key in ["ai_provider", "ai_api_key", "ai_base_url", "ai_model", "use_custom_model"]:
                if key in profile:
                    cfg[key] = profile[key]
        return cfg
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    """保存配置"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_font_size(base_size=12, scale_percent=100):
    """根据百分比计算实际字体大小"""
    return max(8, int(base_size * scale_percent / 100))
