#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A教师页面、上下文感知对话和语音识别接口。"""

import json
import secrets

import requests
from flask import (
    Response, jsonify, render_template, request, send_file, session,
    stream_with_context, url_for,
)

from src.apps.aiteacher import aiteacher_bp
from src.apps.aiteacher.course import DEMO_COURSE, SYSTEM_PROMPT
from src.apps.aiteacher.materials import (
    MaterialError, create_generated_material, create_uploaded_material,
    create_url_material, list_materials, load_material, safe_owner_name,
)
from src.llm_client import LLMClient
from src.logger import logger


MAX_MESSAGE_CHARS = 1200
MAX_CONTEXT_CHARS = 16000
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
        '材料类型': _clean_text(page_context.get('material_type'), 80),
        '材料来源': _clean_text(page_context.get('material_source'), 500),
        '屏幕教学文字': _clean_text(page_context.get('visible_text'), 12000),
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


def _current_material_owner():
    """登录用户按用户名存储；访客使用当前会话的隔离目录。"""
    if session.get('is_logged_in') and session.get('username'):
        return safe_owner_name(session['username'])
    guest_id = session.get('aiteacher_guest_id')
    if not guest_id:
        guest_id = secrets.token_hex(8)
        session['aiteacher_guest_id'] = guest_id
    return 'guest-' + safe_owner_name(guest_id)


def _current_material_owners():
    """当前账号目录优先，同时保留本次会话登录前的访客材料。"""
    owners = [_current_material_owner()]
    guest_id = session.get('aiteacher_guest_id')
    if guest_id:
        guest_owner = 'guest-' + safe_owner_name(guest_id)
        if guest_owner not in owners:
            owners.append(guest_owner)
    return owners


def _load_current_material(material_id):
    for owner in _current_material_owners():
        try:
            return load_material(owner, material_id)
        except FileNotFoundError:
            continue
    raise FileNotFoundError('学习材料不存在')


def _material_payload(material):
    return {
        'id': material['id'],
        'title': material['title'],
        'source_type': material['source_type'],
        'source_label': material.get('source_label', ''),
        'original_name': material.get('original_name', ''),
        'text': material.get('text', ''),
        'created_at': material.get('created_at', ''),
        'viewer_url': url_for(
            'aiteacher.view_material', material_id=material['id']),
    }


def _material_summary_payload(material):
    return {
        'id': material['id'],
        'title': material['title'],
        'source_type': material['source_type'],
        'source_label': material.get('source_label', ''),
        'original_name': material.get('original_name', ''),
        'created_at': material.get('created_at', ''),
    }


def _hydrate_material_context(body):
    """用服务端已保存的正文覆盖前端材料上下文，避免丢失或篡改。"""
    page_context = body.get('page_context') or {}
    material_id = page_context.get('material_id')
    if not material_id:
        return body
    metadata, _ = _load_current_material(material_id)
    hydrated = dict(body)
    hydrated_context = dict(page_context)
    hydrated_context.update({
        'course_title': metadata['title'],
        'lesson_title': '自选学习材料',
        'goal': '理解材料、回答问题并通过对话巩固学习',
        'material_type': metadata['source_type'],
        'material_source': metadata.get('source_label', ''),
        'visible_text': metadata.get('text', ''),
    })
    hydrated['page_context'] = hydrated_context
    return hydrated


@aiteacher_bp.route('/')
def index():
    return render_template('aiteacher/index.html', course=DEMO_COURSE)


@aiteacher_bp.route('/api/course')
def course():
    return jsonify({'success': True, 'course': DEMO_COURSE})


@aiteacher_bp.route('/api/material/generate', methods=['POST'])
def generate_material():
    body = request.get_json(silent=True) or {}
    try:
        client = LLMClient(language='zh')
        material = create_generated_material(
            _current_material_owner(), body.get('requirement'), client)
        return jsonify({'success': True, 'material': _material_payload(material)})
    except MaterialError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except Exception as exc:
        logger.error('生成学习材料失败: %s', exc)
        return jsonify({'success': False, 'error': 'AI 暂时无法生成课件，请稍后再试'}), 502


@aiteacher_bp.route('/api/materials')
def saved_materials():
    owner = _current_material_owner()
    try:
        owner_materials = [(owner, item) for owner in _current_material_owners()
                           for item in list_materials(owner)]
        owner_materials.sort(
            key=lambda pair: pair[1].get('created_at', ''), reverse=True)
        return jsonify({
            'success': True,
            'materials': [_material_summary_payload(item) for _, item in owner_materials[:50]],
            'storage_path': 'data/users/%s' % owner,
            'storage_paths': ['data/users/%s' % value for value in _current_material_owners()],
        })
    except Exception as exc:
        logger.error('读取已保存学习材料失败: %s', exc)
        return jsonify({'success': False, 'error': '读取已保存材料时发生错误'}), 500


@aiteacher_bp.route('/api/materials/<material_id>')
def saved_material(material_id):
    try:
        material, _ = _load_current_material(material_id)
        return jsonify({'success': True, 'material': _material_payload(material)})
    except (MaterialError, FileNotFoundError):
        return jsonify({'success': False, 'error': '学习材料不存在'}), 404


@aiteacher_bp.route('/api/material/url', methods=['POST'])
def material_from_url():
    body = request.get_json(silent=True) or {}
    try:
        material = create_url_material(
            _current_material_owner(), body.get('url'))
        return jsonify({'success': True, 'material': _material_payload(material)})
    except MaterialError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except requests.RequestException as exc:
        logger.warning('读取学习网址失败: %s', exc)
        return jsonify({'success': False, 'error': '无法连接到这个网址'}), 502
    except Exception as exc:
        logger.error('导入学习网址失败: %s', exc)
        return jsonify({'success': False, 'error': '读取网页时发生错误'}), 502


@aiteacher_bp.route('/api/material/upload', methods=['POST'])
def upload_material():
    uploaded = request.files.get('file')
    if not uploaded:
        return jsonify({'success': False, 'error': '请选择要上传的文件'}), 400
    try:
        material = create_uploaded_material(_current_material_owner(), uploaded)
        return jsonify({'success': True, 'material': _material_payload(material)})
    except MaterialError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except Exception as exc:
        logger.error('上传学习材料失败: %s', exc)
        return jsonify({'success': False, 'error': '保存文件时发生错误'}), 500


@aiteacher_bp.route('/materials/<material_id>')
def view_material(material_id):
    try:
        _, viewer_path = _load_current_material(material_id)
    except (MaterialError, FileNotFoundError):
        return jsonify({'success': False, 'error': '学习材料不存在'}), 404
    response = send_file(viewer_path, mimetype='text/html')
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['Content-Security-Policy'] = (
        "sandbox allow-scripts allow-forms; default-src 'none'; "
        "style-src 'unsafe-inline' https: http:; "
        "script-src 'unsafe-inline'; img-src data: blob: https: http:; "
        "font-src data: https: http:; media-src data: blob: https: http:; "
        "connect-src 'none'; frame-src 'none'; form-action 'none';"
    )
    return response


@aiteacher_bp.route('/api/chat', methods=['POST'])
def chat():
    body = request.get_json(silent=True) or {}
    try:
        body = _hydrate_material_context(body)
    except (MaterialError, FileNotFoundError):
        return jsonify({'success': False, 'error': '当前学习材料已经不可用，请重新打开'}), 400
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
