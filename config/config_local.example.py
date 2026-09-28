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
# 阿里云百炼公共端密钥（语音识别 ASR / 语音合成 TTS / 图片理解 等非文本能力必需）
# DASHSCOPE_API_KEY = ''
# DASHSCOPE_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'

# AI 老师真人发音（文字转语音）配置；api_key 留空会自动回退 DASHSCOPE_API_KEY。
# 这里的 voice 只在 VoxCPM2 不可用时生效（回退音色），默认上口的音色由
# src/apps/aiteacher/voice.py 的 DEFAULT_VOICE 决定。
# TTS_CONFIG = {
#     'model': 'qwen3-tts-flash',
#     'voice': 'Cherry',
#     'language_type': 'Chinese',
#     'api_key': '',
#     'endpoint': 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
#     'max_chars': 500,
#     'timeout': 60,
# }

# 可选：ModelBest（OpenBMB）VoxCPM2 真人感音色。不配置时会自动回落到上面的 Qwen3-TTS。
# 密钥在 https://platform.modelbest.cn/console/keys 申请。
# VOXCPM_CONFIG = {
#     'api_key': '',            # 也可单独设 MODELBEST_API_KEY
#     'model': 'VoxCPM2',
#     'endpoint': 'https://api.modelbest.cn/v1/audio/speech',
#     'max_chars': 400,         # 单次分块上限；超出会被服务端静默截断，不要调大太多
#     'timeout': 60,
# }

# 可选：主动等待判定（孩子沉默时由模型判断该不该主动引导）的保守参数。
# 该功能默认在学习偏好里关闭；以下仅是后端调参。
# PROACTIVE_CONFIG = {
#     'base_delay_ms': 10000,   # 首次去看之前的安静时间
#     'max_nudges': 3,          # 同一个提问最多温和提示几次，到顶交还照护者
#     'min_check_ms': 4000,     # 复检间隔下限
#     'max_check_ms': 30000,    # 复检间隔上限
#     'timeout': 20,            # 单次判定的模型调用超时（秒）
# }

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
