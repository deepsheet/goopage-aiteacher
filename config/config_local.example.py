#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""本机私有配置示例。

复制为 ``config_local.py`` 后按需填写。该文件中的同名变量会覆盖
``config.py``，而 ``config_local.py`` 已被 Git 忽略。
"""

# 选择 deepseek 或 qwen
CURRENT_MODEL = 'deepseek'

DEEPSEEK_API_KEY = ''
# QWEN_API_KEY = ''
# DASHSCOPE_API_KEY = ''

# 可选：覆盖本地数据库和 Redis
# DB_CONFIG = {
#     'host': 'localhost',
#     'port': 3306,
#     'user': 'root',
#     'password': '',
#     'database': 'uni',
#     'charset': 'utf8mb4',
# }
# REDIS_CONFIG = {
#     'host': 'localhost',
#     'port': 6379,
#     'password': '',
#     'expire': 3600 * 24 * 30,
#     'prefix': '',
# }
