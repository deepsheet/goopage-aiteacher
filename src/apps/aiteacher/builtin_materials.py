#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""系统内置的可选 HTML 教程目录。"""

from functools import lru_cache
from pathlib import Path

from src.apps.aiteacher.materials import extract_html_text


BUILTIN_ROOT = Path(__file__).resolve().parent / 'builtin_materials'
BUILTIN_CATALOG = {
    'functional-communication-starter': {
        'id': 'functional-communication-starter',
        'title': '把想法说出来',
        'subtitle': '功能性沟通体验课',
        'description': '从选择喜欢的东西开始，练习请求、拒绝、求助和轮流。',
        'duration': '约 8 分钟',
        'source_type': 'builtin',
        'source_label': '系统内置教程 · 功能性沟通',
        'filename': 'functional-communication-starter.html',
    },
}


@lru_cache(maxsize=16)
def load_builtin_material(material_id):
    item = BUILTIN_CATALOG.get(str(material_id or ''))
    if not item:
        raise FileNotFoundError('内置教程不存在')
    path = (BUILTIN_ROOT / item['filename']).resolve()
    if path.parent != BUILTIN_ROOT.resolve() or not path.is_file():
        raise FileNotFoundError('内置教程文件不存在')
    source = path.read_text(encoding='utf-8')
    material = dict(item)
    material['text'] = extract_html_text(source)
    return material, path


def list_builtin_materials():
    return [load_builtin_material(material_id)[0] for material_id in BUILTIN_CATALOG]
