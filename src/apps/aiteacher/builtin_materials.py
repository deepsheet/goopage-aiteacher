#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""系统内置的可选 HTML 教程目录。

目录只登记展示用元数据。课件支持哪些操作指令、老师该怎么带本课，全部由课件 HTML
里的 manifest 声明（docs/material-protocol.md 第 3 节），读取时即时派生，不在这里重复登记。
"""

from functools import lru_cache
from pathlib import Path

from src.apps.aiteacher.material_manifest import manifest_bits
from src.apps.aiteacher.materials import extract_html_text


BUILTIN_ROOT = Path(__file__).resolve().parent / 'builtin_materials'
BUILTIN_CATALOG = {
    'functional-communication-starter': {
        'id': 'functional-communication-starter',
        'title': '把想法说出来（语言障碍恢复）',
        'subtitle': '功能性沟通与语言训练课',
        'description': '从选择喜欢的东西开始，练请求、拒绝、求助、轮流，最后练开口说；点选、手势、发声和口语都算有效表达。',
        'duration': '约 12 分钟',
        'source_type': 'builtin',
        'source_label': '系统内置教程 · 功能性沟通与语言训练',
        'filename': 'functional-communication-starter.html',
    },
    # 必须追加在后面：内置教程列表按下标取值，已有断言依赖第一项是沟通体验课。
    'nce1-lesson1-handbag': {
        'id': 'nce1-lesson1-handbag',
        'title': '新概念英语 Lesson 1',
        'subtitle': 'Excuse me! 逐词拼句',
        'description': '看中文说英文，一格一词：练 Excuse me、Is this your handbag、Pardon、Yes，错了有反馈，最后由老师解释。',
        'duration': '约 6 分钟',
        'source_type': 'builtin',
        'source_label': '系统内置教程 · 英语学科范例',
        'filename': 'nce1-lesson1-handbag.html',
    },
    'emotion-radar-basics': {
        'id': 'emotion-radar-basics',
        'title': '我的情绪小雷达',
        'subtitle': '情绪识别与自我调节体验课',
        'description': '认识开心、难过、生气、害怕四种情绪，判断他人感受、对应身体信号，并自选一个调节办法，共 4 关。',
        'duration': '约 12 分钟',
        'source_type': 'builtin',
        'source_label': '系统内置教程 · 情绪与自我调节',
        'filename': 'emotion-radar-basics.html',
    },
    'phonics-short-a': {
        'id': 'phonics-short-a',
        'title': '自然拼读 · 短元音 a',
        'subtitle': '听音拼词 /æ/',
        'description': '练短元音 a（/æ/）的听音拼词，共 4 关：认识 /æ/ → 首音是谁 → 拼出来 → 读一读。',
        'duration': '约 8 分钟',
        'source_type': 'builtin',
        'source_label': '系统内置教程 · 英语学科范例',
        'filename': 'phonics-short-a.html',
    },
    'daily-routine-out-the-door': {
        'id': 'daily-routine-out-the-door',
        'title': '出门前的准备',
        'subtitle': '日常生活流程与自理课',
        'description': '起床顺序、洗手六步、出门清单、过马路安全，四关练生活自理与流程，低压力、可等待、不批评。',
        'duration': '约 12 分钟',
        'source_type': 'builtin',
        'source_label': '系统内置教程 · 日常生活与自理',
        'filename': 'daily-routine-out-the-door.html',
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
    # 能力清单以课件文件为唯一事实源；内置教程属于可信来源，教师须知会被采纳。
    material['manifest'] = manifest_bits(material, source)
    return material, path


def list_builtin_materials():
    return [load_builtin_material(material_id)[0] for material_id in BUILTIN_CATALOG]
