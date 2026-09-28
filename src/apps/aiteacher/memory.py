#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""三层记忆的存储层（MySQL）。

- 用户 memory：某位学员的长期画像（owner=用户名或 guest-xxx）。
- 教材 memory：按材料 id 共享、服务所有学员的教学经验。
- 产品 memory：跨材料的全局教学沉淀。

所有对外函数都做“优雅降级”：数据库不可用时读取返回空、写入静默失败，
绝不因为记忆功能异常而打断主对话链路。
"""

import json
import os
from datetime import datetime

import pymysql

from config.config import DB_CONFIG
from src.logger import logger
from src.prompts.memory_extractor import parse_deltas, EXTRACTOR_SYSTEM_PROMPT


SHARED_OWNER = '__shared__'
TABLE = 'at_memory'
MAX_ITEMS_PER_CATEGORY = 20
MEMORY_CONTEXT_BUDGET = int(os.environ.get('AITEACHER_MEMORY_BUDGET', '2000'))

# 注入/展示时把内部分类名翻成可读中文标签。
CATEGORY_LABELS = {
    'learner_name': '称呼', 'interests': '兴趣', 'comm_mode': '常用表达',
    'difficulty_pref': '难度偏好', 'feedback_style': '反馈偏好',
    'weak_points': '薄弱点', 'progress': '学习进度', 'avoid_topics': '回避话题',
    'common_confusions': '常见困惑', 'effective_explanations': '有效讲法',
    'frequent_questions': '高频问题', 'key_points': '关键要点',
    'pedagogy_notes': '教学心得',
}

_table_ready = False


def is_memory_enabled():
    """记忆功能总开关（默认开启，可用环境变量关闭）。"""
    return os.environ.get('AITEACHER_MEMORY', '1').strip().lower() not in (
        '0', 'false', 'off', 'no')


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def get_connection():
    return pymysql.connect(
        host=DB_CONFIG['host'], port=DB_CONFIG['port'],
        user=DB_CONFIG['user'], password=DB_CONFIG['password'],
        database=DB_CONFIG['database'], charset=DB_CONFIG['charset'],
    )


def ensure_memory_table(force=False):
    """惰性建表。成功返回 True，任何异常返回 False（调用方据此跳过记忆）。"""
    global _table_ready
    if _table_ready and not force:
        return True
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS %s (
                        id BIGINT NOT NULL AUTO_INCREMENT,
                        owner VARCHAR(80) NOT NULL,
                        scope VARCHAR(16) NOT NULL,
                        material_id VARCHAR(80) NOT NULL DEFAULT '',
                        category VARCHAR(40) NOT NULL,
                        mem_value TEXT NOT NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        PRIMARY KEY (id),
                        UNIQUE KEY uk_mem (owner, scope, material_id, category)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                ''' % TABLE)
            conn.commit()
        finally:
            conn.close()
        _table_ready = True
        return True
    except Exception as exc:
        logger.warning('记忆表不可用，已跳过记忆功能：%s', exc)
        return False


def _read_row(cursor, owner, scope, material_id, category):
    cursor.execute(
        'SELECT id, mem_value FROM %s '
        'WHERE owner=%%s AND scope=%%s AND material_id=%%s AND category=%%s' % TABLE,
        (owner, scope, material_id, category))
    return cursor.fetchone()


def _merge_item(items, new_item):
    """把 new_item 合并进条目列表：同 item 累加 count，否则新增；随后按上限淘汰。"""
    now = _now()
    for entry in items:
        if entry.get('item') == new_item:
            entry['count'] = int(entry.get('count', 1)) + 1
            entry['updated_at'] = now
            return items
    items.append({'item': new_item, 'count': 1, 'updated_at': now})
    if len(items) > MAX_ITEMS_PER_CATEGORY:
        # 优先保留出现次数多、更新近的条目。
        items.sort(
            key=lambda e: (int(e.get('count', 1)), e.get('updated_at') or ''),
            reverse=True)
        del items[MAX_ITEMS_PER_CATEGORY:]
    return items


def merge_deltas(scope, owner, material_id, category, item):
    """把单条 (scope, owner, material_id, category, item) upsert 进记忆表。"""
    if not ensure_memory_table():
        return False
    material_id = material_id or ''
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            row = _read_row(cursor, owner, scope, material_id, category)
            if row:
                _, raw = row
                try:
                    items = json.loads(raw or '[]')
                    if not isinstance(items, list):
                        items = []
                except Exception:
                    items = []
                items = _merge_item(items, item)
                cursor.execute(
                    'UPDATE %s SET mem_value=%%s, updated_at=%%s WHERE id=%%s' % TABLE,
                    (json.dumps(items, ensure_ascii=False), _now(), row[0]))
            else:
                cursor.execute(
                    'INSERT INTO %s '
                    '(owner, scope, material_id, category, mem_value, created_at, updated_at) '
                    'VALUES (%%s,%%s,%%s,%%s,%%s,%%s,%%s)' % TABLE,
                    (owner, scope, material_id, category,
                     json.dumps([{'item': item, 'count': 1, 'updated_at': _now()}],
                                ensure_ascii=False),
                     _now(), _now()))
        conn.commit()
        return True
    except Exception as exc:
        if conn:
            conn.rollback()
        logger.warning('写入记忆失败（已忽略）：%s', exc)
        return False
    finally:
        if conn:
            conn.close()


def _fetch_group(conn, owner, scope, material_id=''):
    with conn.cursor() as cursor:
        cursor.execute(
            'SELECT category, mem_value FROM %s '
            'WHERE owner=%%s AND scope=%%s AND material_id=%%s' % TABLE,
            (owner, scope, material_id))
        rows = cursor.fetchall()
    grouped = {}
    for category, raw in rows:
        try:
            items = json.loads(raw or '[]')
        except Exception:
            items = []
        if isinstance(items, list) and items:
            grouped[category] = items
    return grouped


def load_memory_context(owner, material_id=''):
    """读取三层记忆并格式化为可注入提示词的文本块（按 user>material>product 截断）。"""
    if not is_memory_enabled() or not ensure_memory_table():
        return ''
    conn = None
    try:
        conn = get_connection()
        user_group = _fetch_group(conn, owner, 'user')
        mat_group = (_fetch_group(conn, SHARED_OWNER, 'material', material_id)
                     if material_id else {})
        product_group = _fetch_group(conn, SHARED_OWNER, 'product')
    except Exception as exc:
        logger.warning('读取记忆失败（返回空）：%s', exc)
        return ''
    finally:
        if conn:
            conn.close()

    def _section(title, grouped, order):
        lines = []
        for category in order:
            items = grouped.get(category)
            if not items:
                continue
            label = CATEGORY_LABELS.get(category, category)
            top = sorted(items, key=lambda e: int(e.get('count', 1)), reverse=True)[:5]
            joined = '；'.join(str(e.get('item', '')).strip() for e in top if e.get('item'))
            if joined:
                lines.append('%s：%s' % (label, joined))
        if not lines:
            return ''
        return '【%s】\n%s' % (title, '\n'.join(lines))

    from src.prompts.memory_extractor import USER_CATEGORIES, MATERIAL_CATEGORIES
    user_order = [c for c in (
        'learner_name', 'comm_mode', 'interests', 'difficulty_pref',
        'feedback_style', 'weak_points', 'progress', 'avoid_topics')
        if c in USER_CATEGORIES]
    material_order = [c for c in (
        'common_confusions', 'effective_explanations', 'frequent_questions',
        'key_points') if c in MATERIAL_CATEGORIES]

    sections = [
        _section('已知学员画像', user_group, user_order),
        _section('这份材料的教学经验', mat_group, material_order),
        _section('教学沉淀', product_group, ['pedagogy_notes']),
    ]
    text = '\n'.join(s for s in sections if s).strip()

    # 预算截断：按 user>material>product 优先级，从最次要的段落开始整段丢弃。
    while len(text) > MEMORY_CONTEXT_BUDGET:
        idx = next((i for i in range(len(sections) - 1, -1, -1) if sections[i]), None)
        if idx is None:
            break
        sections[idx] = ''
        text = '\n'.join(s for s in sections if s).strip()
    return text


def _build_turn_material(user_msg, assistant_msg, page_context, material_id, material_title):
    page_context = page_context or {}
    prefs = page_context.get('preferences') or {}
    bits = [
        '材料标题：%s' % (material_title or page_context.get('course_title') or ''),
        '当前环节：%s' % (page_context.get('lesson_title') or ''),
        '已填偏好：称呼=%s 兴趣=%s 表达方式=%s' % (
            prefs.get('name', ''), prefs.get('interests', ''),
            ','.join(prefs.get('modes') or [])),
        '学员本轮说：%s' % (user_msg or '')[:800],
        'AI老师本轮回复：%s' % (assistant_msg or '')[:800],
    ]
    if material_id:
        bits.append('（若提炼 material 层记忆，material_id 请使用：%s）' % material_id)
    return '\n'.join(bits)


def extract_and_store(client, owner, material_id, material_title,
                      user_msg, assistant_msg, page_context):
    """用给定的 LLM 客户端提炼本轮记忆并落库。任何异常都被吞掉，不影响主流程。"""
    if not is_memory_enabled():
        return
    if not ensure_memory_table():
        return
    try:
        user_content = _build_turn_material(
            user_msg, assistant_msg, page_context, material_id, material_title)
        options = {}
        if str(getattr(client, 'model_name', '')).lower() == 'deepseek':
            options['thinking'] = 'disabled'
        raw = client.generate(
            EXTRACTOR_SYSTEM_PROMPT, user_content,
            max_tokens=600, temperature=0.2, stream=False, **options)
        deltas = parse_deltas(raw if isinstance(raw, str) else str(raw or ''))
        stored = 0
        for delta in deltas:
            scope = delta['scope']
            if scope == 'user':
                row_owner, row_material = owner, ''
            elif scope == 'material':
                if not material_id:
                    continue
                row_owner, row_material = SHARED_OWNER, material_id
            else:  # product
                row_owner, row_material = SHARED_OWNER, ''
            if merge_deltas(scope, row_owner, row_material, delta['category'], delta['item']):
                stored += 1
        if stored:
            logger.info('本轮提炼并写入 %d 条记忆（owner=%s）', stored, owner)
    except Exception as exc:
        logger.warning('记忆提炼失败（已忽略）：%s', exc)


def get_user_profile(owner):
    """返回当前用户的画像条目，供前端展示。DB 不可用时返回空 dict。"""
    if not is_memory_enabled() or not ensure_memory_table():
        return {}
    conn = None
    try:
        conn = get_connection()
        grouped = _fetch_group(conn, owner, 'user')
    except Exception as exc:
        logger.warning('读取用户画像失败：%s', exc)
        return {}
    finally:
        if conn:
            conn.close()
    profile = {}
    for category, items in grouped.items():
        top = sorted(items, key=lambda e: int(e.get('count', 1)), reverse=True)
        profile[category] = [
            {'label': CATEGORY_LABELS.get(category, category),
             'item': str(e.get('item', '')).strip(),
             'count': int(e.get('count', 1))}
            for e in top if e.get('item')
        ]
    return profile


def clear_memory(owner):
    """清除当前用户的 user 层记忆（教材/产品共享层不动）。"""
    if not ensure_memory_table():
        return False
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                'DELETE FROM %s WHERE owner=%%s AND scope=%%s' % TABLE,
                (owner, 'user'))
        conn.commit()
        return True
    except Exception as exc:
        if conn:
            conn.rollback()
        logger.warning('清除记忆失败：%s', exc)
        return False
    finally:
        if conn:
            conn.close()
