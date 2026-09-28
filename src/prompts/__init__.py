#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""提示词层：把 AI 教师的系统提示词拆成可组合、可注入记忆的结构。

本层不内置任何单个课件的教学法；课件的个性内容由它自己的 manifest 提供
（见 docs/material-protocol.md 第 3 节）。
"""

from src.prompts.teacher import (
    CORE_ROLE, MATERIAL_COMMANDS, MEMORY_USAGE_RULES,
    build_material_command_rules, build_system_prompt,
)

__all__ = [
    'CORE_ROLE',
    'MATERIAL_COMMANDS',
    'MEMORY_USAGE_RULES',
    'build_material_command_rules',
    'build_system_prompt',
]
