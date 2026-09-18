#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A教师页面、上下文感知对话和语音识别接口。"""

import json

from flask import Response, jsonify, render_template, request, stream_with_context

from src.apps.aiteacher import aiteacher_bp
from src.apps.aiteacher.course import DEMO_COURSE, SYSTEM_PROMPT
from src.llm_client import LLMClient
from src.logger import logger


MAX_MESSAGE_CHARS = 1200
MAX_CONTEXT_CHARS = 6000
MAX_HISTORY_ITEMS = 16


def _sse(data):
    return 'data: %s\n\n' % json.dumps(data, ensure_ascii=False)


def _clean_text(value, limit):
    return str(value or '').strip()[:limit]


def _chat_messages(body):
    user_message = _clean_text(body.get('message'), MAX_MESSAGE_CHARS)
    page_context = body.get('page_context') or {}
    context = {
        '课程': _clean_text(page_context.get('course_title'), 120),
        '当前环节': _clean_text(page_context.get('lesson_title'), 120),
        '教学目标': _clean_text(page_context.get('goal'), 240),
        '屏幕教学文字': _clean_text(page_context.get('visible_text'), 2600),
        '孩子刚才的操作': _clean_text(page_context.get('last_action'), 500),
        '已拼出的表达': _clean_text(page_context.get('constructed_phrase'), 300),
        '本次已完成环节': page_context.get('completed_lessons') or [],
        '偏好设置': page_context.get('preferences') or {},
    }
    context_text = json.dumps(context, ensure_ascii=False)[:MAX_CONTEXT_CHARS]
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    history = body.get('history') or []
    for item in history[-MAX_HISTORY_ITEMS:]:
        if not isinstance(item, dict) or item.get('role') not in ('user', 'assistant'):
            continue
        content = _clean_text(item.get('content'), MAX_MESSAGE_CHARS)
        if content:
            messages.append({'role': item['role'], 'content': content})
    messages.append({
        'role': 'user',
        'content': '当前学习区状态：%s\n\n孩子/照护者刚刚说或做：%s' % (
            context_text, user_message),
    })
    return user_message, messages


@aiteacher_bp.route('/')
def index():
    return render_template('aiteacher/index.html', course=DEMO_COURSE)


@aiteacher_bp.route('/api/course')
def course():
    return jsonify({'success': True, 'course': DEMO_COURSE})


@aiteacher_bp.route('/api/chat', methods=['POST'])
def chat():
    body = request.get_json(silent=True) or {}
    user_message, messages = _chat_messages(body)
    if not user_message:
        return jsonify({'success': False, 'error': '请说点什么或输入一段话'}), 400

    def generate():
        full_reply = []
        try:
            client = LLMClient(language='zh')
            payload = {
                'model': client.model,
                'messages': messages,
                'stream': True,
                'temperature': 0.45,
            }
            yield _sse({'type': 'ready'})
            for chunk_type, text in client._call_api_stream_yield(payload):
                if chunk_type != 'content' or not text:
                    continue
                full_reply.append(text)
                yield _sse({'type': 'delta', 'text': text})
            if not full_reply:
                raise RuntimeError('AI 暂时没有返回内容')
            yield _sse({'type': 'done', 'text': ''.join(full_reply)})
        except Exception as exc:
            logger.error('aiteacher chat 失败: %s', exc)
            yield _sse({'type': 'error', 'message': 'AI老师暂时没有连上，请稍后再试。'})

    response = Response(stream_with_context(generate()), content_type='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


@aiteacher_bp.route('/api/asr', methods=['POST'])
def asr():
    audio = request.files.get('audio')
    if not audio or not audio.filename:
        return jsonify({'success': False, 'error': '没有收到录音'}), 400
    data = audio.read(12 * 1024 * 1024 + 1)
    if not data:
        return jsonify({'success': False, 'error': '录音内容为空'}), 400
    if len(data) > 12 * 1024 * 1024:
        return jsonify({'success': False, 'error': '录音不能超过 12MB'}), 413
    try:
        from src.apps.aiteacher.voice import transcribe
        text = transcribe(data, audio.filename)
        return jsonify({'success': True, 'text': text})
    except Exception as exc:
        logger.error('aiteacher asr 失败: %s', exc)
        return jsonify({'success': False, 'error': str(exc)}), 502
