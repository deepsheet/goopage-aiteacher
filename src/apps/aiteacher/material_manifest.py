#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""解析课件自带的 manifest，实现 docs/material-protocol.md 第 3 节。

课件用一段 JSON 脚本块声明自己的能力与教学须知，公共层因此不需要认识任何具体课件：

    <script type="application/aiteacher+json" id="aiteacher-manifest">
    {"schema": 1, "commands": ["hint"], "teacher_notes": "……"}
    </script>

两条边界：
- 解析永不抛异常。课件是外部内容，写得不对就当没有清单，课件本身照常可用。
- 自由文本（teacher_notes / command_guide）会进 system prompt，属于指令，只采纳可信来源；
  commands 只是能力开关，任何来源都采纳。指令名的白名单由调用方用提示词层的注册表收敛
  （见 routes._material_bits），本模块只做结构与长度校验。
"""

import json
import re


MANIFEST_SCHEMA = 1
MAX_COMMANDS = 8
MAX_NOTE_CHARS = 2000
MAX_GUIDE_CHARS = 200

# 第三方网页/上传文件里的清单不得影响教师行为。
TRUSTED_NOTE_SOURCES = frozenset({'builtin', 'generated'})

_MANIFEST_RE = re.compile(
    r'<script[^>]*type\s*=\s*["\']application/aiteacher\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL)


def _empty():
    return {'schema': 0, 'commands': [], 'teacher_notes': '', 'command_guide': {}}


def _clean_strings(values, limit):
    """把列表规整成去重保序的短字符串列表；非法输入返回空。"""
    if not isinstance(values, (list, tuple)):
        return []
    cleaned = []
    for value in values:
        if not isinstance(value, str):
            continue
        token = value.strip().lower()[:limit]
        if token and token not in cleaned:
            cleaned.append(token)
    return cleaned


def parse_manifest(html_source):
    """从课件 HTML 中读出 manifest。

    @param {str} html_source - 课件源码，可为空
    @return {dict} - {'schema', 'commands', 'teacher_notes', 'command_guide'}；
        没有清单或清单不可识别时返回全空结构（schema=0）。
    """
    for match in _MANIFEST_RE.finditer(str(html_source or '')):
        try:
            raw = json.loads(match.group(1))
        except (ValueError, TypeError):
            continue          # 多份清单时跳过坏的那份，继续找下一份
        if not isinstance(raw, dict):
            continue
        manifest = _empty()
        try:
            manifest['schema'] = int(raw.get('schema'))
        except (TypeError, ValueError):
            continue
        if manifest['schema'] != MANIFEST_SCHEMA:
            continue          # 版本不认识就整份作废，避免按旧语义解释新字段
        manifest['commands'] = _clean_strings(raw.get('commands'), 20)[:MAX_COMMANDS]
        notes = raw.get('teacher_notes')
        if isinstance(notes, str):
            manifest['teacher_notes'] = notes.strip()[:MAX_NOTE_CHARS]
        guide = raw.get('command_guide')
        if isinstance(guide, dict):
            for key, value in list(guide.items())[:MAX_COMMANDS]:
                name = str(key or '').strip().lower()[:20]
                if name in manifest['commands'] and isinstance(value, str) and value.strip():
                    manifest['command_guide'][name] = value.strip()[:MAX_GUIDE_CHARS]
        return manifest
    return _empty()


def manifest_bits(metadata, html_source):
    """把 manifest 折成服务端可直接使用的片段，并按来源做信任分级。

    @param {dict} metadata - 材料元数据，需含 source_type
    @param {str} html_source - 课件源码
    @return {dict} - {'commands', 'teacher_notes', 'command_guide'}；
        不可信来源只保留 commands，自由文本一律丢弃。
    """
    manifest = parse_manifest(html_source)
    source_type = str((metadata or {}).get('source_type') or '')
    bits = {'commands': manifest['commands'], 'teacher_notes': '', 'command_guide': {}}
    if source_type in TRUSTED_NOTE_SOURCES:
        bits['teacher_notes'] = manifest['teacher_notes']
        bits['command_guide'] = manifest['command_guide']
    return bits
