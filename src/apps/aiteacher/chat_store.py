#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""聊天历史持久化：把左侧 AI 对话按「用户 + 教程」存进已有的
ai_chat_sessions / ai_chat_messages 两张表，下次打开同一教程可恢复。

约定：
- 一个会话 = 一个 (user_id, 教程id)。会话 id 用二者的 md5（32 位 hex）生成，
  保证同一教程复用同一会话，且与库中既有的短随机 id 不冲突。
- 消息 id 用「时间(可排序 hex) + 随机」生成，ORDER BY id 即为时间正序。

所有函数都做优雅降级：数据库异常时读取返回空、写入静默失败，绝不影响主对话。
"""

import hashlib
import json
import os
import time
import uuid

import pymysql

from config.config import DB_CONFIG
from src.logger import logger


SESSIONS_TABLE = 'ai_chat_sessions'
MESSAGES_TABLE = 'ai_chat_messages'
MAX_USER_ID_CHARS = 50
MAX_DOC_ID_CHARS = 32
DEFAULT_HISTORY_LIMIT = 60


def is_enabled():
    return os.environ.get('AITEACHER_CHAT_HISTORY', '1').strip().lower() not in (
        '0', 'false', 'off', 'no')


def get_connection():
    return pymysql.connect(
        host=DB_CONFIG['host'], port=DB_CONFIG['port'],
        user=DB_CONFIG['user'], password=DB_CONFIG['password'],
        database=DB_CONFIG['database'], charset=DB_CONFIG['charset'],
    )


def _normalize_user_id(owner):
    return str(owner or 'anonymous')[:MAX_USER_ID_CHARS]


def _normalize_doc_id(doc_id):
    return str(doc_id or 'default')[:MAX_DOC_ID_CHARS]


def session_id(user_id, doc_id):
    """由 (用户, 教程) 生成稳定的 32 位 hex 会话号。"""
    raw = '%s::%s' % (_normalize_user_id(user_id), _normalize_doc_id(doc_id))
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def _new_message_id():
    # 16 位时间（纳秒，可排序）+ 16 位随机，共 32 位 hex。
    return '%016x%s' % (time.time_ns(), uuid.uuid4().hex[:16])


def _ensure_session(conn, sid, user_id, doc_id, title):
    with conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO %s (id, user_id, title, current_document_id, message_count, created_at, updated_at) '
            'VALUES (%%s,%%s,%%s,%%s,0,NOW(),NOW()) '
            'ON DUPLICATE KEY UPDATE updated_at=NOW(), title=IFNULL(title,%%s)' % SESSIONS_TABLE,
            (sid, user_id, title or None, doc_id, title or None))


def save_turn(user_id, doc_id, user_text, assistant_text, title=None, metadata=None):
    """把一轮（用户 + 老师）消息写入会话。返回写入的消息数，失败返回 0。"""
    if not is_enabled() or not (user_text or assistant_text):
        return 0
    user_id = _normalize_user_id(user_id)
    doc_id = _normalize_doc_id(doc_id)
    sid = session_id(user_id, doc_id)
    meta = json.dumps(metadata or {}, ensure_ascii=False) if metadata else None
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            _ensure_session(conn, sid, user_id, doc_id, title)
            written = 0
            for role, text in (('user', user_text), ('assistant', assistant_text)):
                text = str(text or '').strip()
                if not text:
                    continue
                cursor.execute(
                    'INSERT INTO %s (id, session_id, role, content, metadata, created_at) '
                    'VALUES (%%s,%%s,%%s,%%s,%%s,NOW())' % MESSAGES_TABLE,
                    (_new_message_id(), sid, role, text[:20000], meta))
                written += 1
            if written:
                cursor.execute(
                    'UPDATE %s SET message_count = message_count + %%s, last_message_at=NOW(), updated_at=NOW() '
                    'WHERE id=%%s' % SESSIONS_TABLE,
                    (written, sid))
        conn.commit()
        return written
    except Exception as exc:
        if conn:
            conn.rollback()
        logger.warning('保存聊天历史失败（已忽略）：%s', exc)
        return 0
    finally:
        if conn:
            conn.close()


def load_history(user_id, doc_id, limit=DEFAULT_HISTORY_LIMIT):
    """读取某用户在某教程下的历史消息，按时间正序返回 [{role, content}]。"""
    if not is_enabled():
        return []
    user_id = _normalize_user_id(user_id)
    doc_id = _normalize_doc_id(doc_id)
    sid = session_id(user_id, doc_id)
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                'SELECT role, content FROM %s WHERE session_id=%%s ORDER BY id DESC LIMIT %%s' % MESSAGES_TABLE,
                (sid, int(limit)))
            rows = cursor.fetchall()
    except Exception as exc:
        logger.warning('读取聊天历史失败（返回空）：%s', exc)
        return []
    finally:
        if conn:
            conn.close()
    rows = list(rows)[::-1]  # 取回后翻正为时间正序
    history = []
    for role, content in rows:
        role = str(role or '').strip()
        if role in ('user', 'assistant') and str(content or '').strip():
            history.append({'role': role, 'content': str(content)})
    return history
