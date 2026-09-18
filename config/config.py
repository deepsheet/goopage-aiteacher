#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置文件：存储API密钥和数据库连接信息
"""

# DeepSeek API 配置
DEEPSEEK_API_KEY = ""
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# QWEN API 配置
QWEN_API_KEY = ""
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
QWEN_MODEL = "qwen-plus"

# 当前使用的模型选择（deepseek、qwen）
CURRENT_MODEL = "deepseek"

# 数据库配置-MySQL
DB_CONFIG = {
    'port': 3306,
    'charset': 'utf8mb4',
    'database': 'uni',

    # 本地开发环境
    'host': 'localhost',
    'user': 'root',
    'password': '',


}


# Redis 配置
REDIS_CONFIG = {
    'expire': 3600 * 24 * 30,  # 过期时间 30 天
    'prefix': '',  # 缓存前缀

     # 本地开发环境（优先使用）
    'host': 'localhost',
    'port': 6379,
    'password': '',  # 本地 Redis 通常无密码


}


# 日志配置
LOG_DIR = "logs"


# 多语言配置
DEFAULT_LANGUAGE = 'zh'  # 默认语言:zh(中文), en(英文)
SUPPORTED_LANGUAGES = ['zh', 'en']

# 🔴 主域名配置（用于非请求上下文中的URL生成）
MAIN_DOMAIN = "http://127.0.0.1:5058"

# ============================================================
# 文件存储配置
# ============================================================

STORAGE_CONFIG = {
    # 后端选择: 'disk' 或 'oss'
    'backend': 'disk',

    # 本地磁盘配置
    'disk': {
        'base_dir': 'userdata',  # 存储根目录（相对于项目根目录）
    },

    # 阿里云OSS配置（后续启用时修改 backend 为 'oss'）
    'oss': {
        'endpoint': 'oss-cn-beijing.aliyuncs.com',
        'access_key_id': '',
        'access_key_secret': '',
        'bucket_name': 'aiteacher-userdata',
        'public_read': False,       # Bucket 是否为公共读
        'cdn_domain': None,          # CDN 域名（如 cdn.example.com）
    },
}

# ============================================================
# 本机配置覆盖
# ============================================================
#
# config.py 只保存可以提交到版本库的默认值。开发者可以复制
# config_local.example.py 为 config_local.py，并在其中填写密钥、数据库等
# 私有配置。同名变量会在模块导入时覆盖上面的默认值。
try:
    from config.config_local import *  # noqa: F401,F403
except ImportError as exc:
    # 只忽略“本地配置文件不存在”；文件内部导入失败仍应明确报错。
    if exc.name != 'config.config_local':
        raise
