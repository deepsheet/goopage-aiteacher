#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A教师页面、上下文感知对话和语音识别接口。"""

import json
import re
import secrets
import threading

import requests
from flask import (
    Response, jsonify, render_template, request, session,
    stream_with_context, url_for,
)

import config.config as config
from src.apps.aiteacher import aiteacher_bp
from src.apps.aiteacher import memory
from src.apps.aiteacher import chat_store
from src.apps.aiteacher.course import DEMO_COURSE
from src.prompts.teacher import (
    MATERIAL_COMMANDS, build_proactive_system_prompt, build_system_prompt,
)
from src.apps.aiteacher.builtin_materials import (
    list_builtin_materials, load_builtin_material,
)
from src.apps.aiteacher.material_bridge import inject_bridge
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


def _viewer_response(viewer_path):
    """读出课件 HTML 并注入桥接脚本，让聊天页能控制课件内高亮定位。"""
    with open(viewer_path, 'r', encoding='utf-8', errors='replace') as handle:
        html = handle.read()
    return Response(inject_bridge(html), mimetype='text/html')


def _clean_text(value, limit):
    return str(value or '').strip()[:limit]


def _empty_bits():
    return {'commands': [], 'teacher_notes': '', 'command_guide': {}}


def _trusted_bits(manifest):
    """把课件 manifest 收敛成可直接使用的片段：指令名过注册表白名单，自由文本限长。

    未注册的名字在此丢弃，模型就收不到该语法，也就不会输出课件执行不了的指令；
    manifest 本身的来源信任分级已在 material_manifest.manifest_bits 完成。
    """
    manifest = manifest if isinstance(manifest, dict) else {}
    commands = [name for name in dict.fromkeys(manifest.get('commands') or ())
                if name in MATERIAL_COMMANDS]
    guide = manifest.get('command_guide') if isinstance(manifest.get('command_guide'), dict) else {}
    bits = _empty_bits()
    bits['commands'] = commands
    bits['teacher_notes'] = _clean_text(manifest.get('teacher_notes'), 2000)
    bits['command_guide'] = {name: _clean_text(guide.get(name), 200) for name in commands
                             if guide.get(name)}
    return bits


def _material_bits(page_context):
    """取当前课件（或默认课程）的能力清单，无需请求上下文。

    带 material_id 的课件需要 owner 才能读盘，那部分由 _hydrate_material_context 在加载
    落盘文件时算好再注入；这里只处理能直接按编号定位到仓库内置文件的两种情况：
    打开了内置教程，或停在 /study 默认课程上（用 course_id 找到它对应的那份内置教程，
    才能在没有 iframe 时也拿到本课教学须知）。前端只上报编号，不上报文本。
    """
    page_context = page_context or {}
    builtin_id = str(page_context.get('builtin_id') or page_context.get('course_id') or '')
    if not builtin_id:
        return _empty_bits()
    try:
        metadata, _ = load_builtin_material(builtin_id)
    except (FileNotFoundError, ValueError):
        return _empty_bits()
    return _trusted_bits(metadata.get('manifest'))


def _hydrate_chat_bits(body, page_context):
    """取本轮该用的能力清单：优先用服务端注入的，没注入时回退到只读内置教程文件。

    前端提交的 body 里不可能带 material_bits（_hydrate_material_context 会先丢掉再按需注入），
    所以这里只信服务端自己写的值。
    """
    bits = body.get('material_bits') if isinstance(body, dict) else None
    if isinstance(bits, dict):
        return _trusted_bits(bits)
    return _material_bits(page_context)


def _material_commands(metadata):
    """给前端的课件能力列表：app.js 据此决定要不要把指令发进课件。"""
    return _trusted_bits((metadata or {}).get('manifest'))['commands']


def _chat_messages(body, memory_block='', material_bits=None):
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
    # 右侧为课件 iframe（已注入桥接脚本）时才下发高亮指令规则。
    has_viewer = bool(page_context.get('material_id') or page_context.get('builtin_id'))
    # 显式传入优先（正常请求链路）；为 None 表示调用方未预推（如单测直接调），回退到只读内置教程文件。
    bits = _hydrate_chat_bits(body, page_context) \
        if material_bits is None else _trusted_bits(material_bits)
    system_prompt = build_system_prompt(
        memory_block, enable_highlight=has_viewer, material_bits=bits)
    messages = [{'role': 'system', 'content': system_prompt}]
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
        'commands': _material_commands(material),
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


def _builtin_payload(material):
    return {
        'id': material['id'],
        'title': material['title'],
        'subtitle': material.get('subtitle', ''),
        'description': material.get('description', ''),
        'duration': material.get('duration', ''),
        'source_type': 'builtin',
        'source_label': material.get('source_label', '系统内置教程'),
        'text': material.get('text', ''),
        'commands': _material_commands(material),
        'viewer_url': url_for(
            'aiteacher.view_builtin_material', material_id=material['id']),
    }


def _hydrate_material_context(body):
    """用服务端已保存的正文与能力清单覆盖前端材料上下文，避免丢失或篡改。"""
    page_context = body.get('page_context') or {}
    hydrated = dict(body)
    # 先丢掉前端可能伪造的同名字段，后面只由服务端从落盘文件重新得出。
    hydrated.pop('material_bits', None)
    builtin_id = page_context.get('builtin_id')
    if builtin_id:
        metadata, _ = load_builtin_material(builtin_id)
        hydrated_context = dict(page_context)
        hydrated_context.update({
            'course_title': metadata['title'],
            'lesson_title': '系统内置教程',
            'goal': metadata.get('description', ''),
            'material_type': 'builtin',
            'material_source': metadata.get('source_label', ''),
            'visible_text': metadata.get('text', ''),
        })
        hydrated['page_context'] = hydrated_context
        hydrated['material_bits'] = _trusted_bits(metadata.get('manifest'))
        return hydrated
    material_id = page_context.get('material_id')
    if not material_id:
        return hydrated
    metadata, _ = _load_current_material(material_id)
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
    # AI 生成的课件也能靠自己的 manifest 拿到操作指令；上传/抓取页只会得到 commands。
    hydrated['material_bits'] = _trusted_bits(metadata.get('manifest'))
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


@aiteacher_bp.route('/api/builtin-materials')
def builtin_materials():
    return jsonify({
        'success': True,
        'materials': [_builtin_payload(item) for item in list_builtin_materials()],
    })


@aiteacher_bp.route('/api/builtin-materials/<material_id>')
def builtin_material(material_id):
    try:
        material, _ = load_builtin_material(material_id)
        return jsonify({'success': True, 'material': _builtin_payload(material)})
    except FileNotFoundError:
        return jsonify({'success': False, 'error': '内置教程不存在'}), 404


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
    response = _viewer_response(viewer_path)
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['Content-Security-Policy'] = (
        "sandbox allow-scripts allow-forms; default-src 'none'; "
        "style-src 'unsafe-inline' https: http:; "
        "script-src 'unsafe-inline'; img-src data: blob: https: http:; "
        "font-src data: https: http:; media-src data: blob: https: http:; "
        "connect-src 'none'; frame-src 'none'; form-action 'none';"
    )
    return response


@aiteacher_bp.route('/builtins/<material_id>')
def view_builtin_material(material_id):
    try:
        _, viewer_path = load_builtin_material(material_id)
    except FileNotFoundError:
        return jsonify({'success': False, 'error': '内置教程不存在'}), 404
    response = _viewer_response(viewer_path)
    response.headers['Cache-Control'] = 'public, max-age=300'
    response.headers['Content-Security-Policy'] = (
        "sandbox allow-scripts; default-src 'none'; "
        "style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
        "img-src data:; connect-src 'none'; frame-src 'none'; form-action 'none';"
    )
    return response


@aiteacher_bp.route('/api/chat', methods=['POST'])
def chat():
    body = request.get_json(silent=True) or {}
    try:
        body = _hydrate_material_context(body)
    except (MaterialError, FileNotFoundError):
        return jsonify({'success': False, 'error': '当前学习材料已经不可用，请重新打开'}), 400

    page_context = body.get('page_context') or {}
    owner = _current_material_owner()
    material_id = page_context.get('builtin_id') or page_context.get('material_id') or ''
    memory_block = memory.load_memory_context(owner, material_id)
    user_message, messages = _chat_messages(
        body, memory_block, body.get('material_bits'))
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
            reply_text = ''.join(full_reply)
            yield _sse({'type': 'done', 'text': reply_text})
            _schedule_background_work(
                client, owner, material_id,
                page_context.get('course_title', ''), user_message,
                reply_text, page_context)
        except Exception as exc:
            logger.error('aiteacher chat 失败: %s', exc)
            yield _sse({'type': 'error', 'message': 'AI老师暂时没有连上，请稍后再试。'})

    response = Response(stream_with_context(generate()), content_type='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


def _schedule_background_work(client, owner, material_id, material_title,
                             user_message, reply_text, page_context):
    """后台线程：先持久化本轮聊天历史（用于下次恢复），再提炼记忆。

    任一步失败都不影响已经返回给用户的主对话流。
    """
    context_snapshot = dict(page_context or {})
    context_snapshot.pop('visible_text', None)  # 不需要把整段材料交给提炼器

    def _worker():
        # 1. 保存聊天历史（不过滤短消息，恢复需要完整上下文）。
        try:
            if chat_store.is_enabled():
                chat_store.save_turn(
                    owner, material_id, user_message, reply_text,
                    title=material_title,
                    metadata={'preferences': (context_snapshot.get('preferences') or {})})
        except Exception as exc:
            logger.warning('后台保存聊天历史异常（已忽略）: %s', exc)
        # 2. 提炼记忆（信息量过低的轮次跳过，控制每轮成本）。
        try:
            if memory.is_memory_enabled() and len(user_message or '') >= 4 and reply_text:
                memory.extract_and_store(
                    client, owner, material_id, material_title,
                    user_message, reply_text, context_snapshot)
        except Exception as exc:
            logger.warning('后台记忆提炼异常（已忽略）: %s', exc)

    threading.Thread(target=_worker, daemon=True).start()


@aiteacher_bp.route('/api/chat/history')
def chat_history():
    owner = _current_material_owner()
    doc_id = _clean_text(request.args.get('doc_id'), 80)
    messages = chat_store.load_history(owner, doc_id) if doc_id else []
    return jsonify({'success': True, 'messages': messages})


@aiteacher_bp.route('/api/memory')
def get_memory():
    owner = _current_material_owner()
    return jsonify({'success': True, 'enabled': memory.is_memory_enabled(),
                    'profile': memory.get_user_profile(owner)})


@aiteacher_bp.route('/api/memory', methods=['DELETE'])
def delete_memory():
    owner = _current_material_owner()
    ok = memory.clear_memory(owner)
    return jsonify({'success': ok})


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


@aiteacher_bp.route('/api/tts', methods=['POST'])
def tts():
    body = request.get_json(silent=True) or {}
    text = _clean_text(body.get('text'), 4000)
    if not text:
        return jsonify({'success': False, 'error': '没有需要合成的文字'}), 400
    try:
        from src.apps.aiteacher.voice import synthesize
        clips, info = synthesize(text, voice=_clean_text(body.get('voice'), 40))
        # voice/degraded 告诉前端“真正出声的是哪个音色”：服务端不得已换人时，
        # 由页面提示用户，不让他在不知情的情况下听到另一个人的声音。
        return jsonify({
            'success': True,
            'clips': clips,
            'requested_voice': info.get('requested', ''),
            'voice': info.get('served', ''),
            'degraded': bool(info.get('degraded')),
        })
    except Exception as exc:
        logger.error('aiteacher tts 失败: %s', exc)
        return jsonify({'success': False, 'error': str(exc)}), 502


@aiteacher_bp.route('/api/tts/voices', methods=['GET'])
def tts_voices():
    """返回可选音色列表与服务端默认音色，供前端音色面板使用。

    默认音色取 voice.DEFAULT_VOICE，一定得是跨请求稳定的固定音色；
    TTS_CONFIG['voice'] 只作为 VoxCPM2 失败时的 Qwen 回退音色，不在此下发。
    音色里的 design 字段是服务端内部的音色描述提示词，不下发给前端；
    unstable 则要下发——它表示该音色的说话人锁不住，面板需提前注明。
    """
    from src.apps.aiteacher.voice import VOICE_OPTIONS, DEFAULT_VOICE
    public_fields = ('code', 'name', 'gender', 'desc', 'unstable')
    return jsonify({
        'success': True,
        'default': DEFAULT_VOICE,
        'voices': [{key: option.get(key) for key in public_fields if key in option}
                   for option in VOICE_OPTIONS],
    })


# 主动等待判定的保守默认参数；可用 config.PROACTIVE_CONFIG 覆盖。
PROACTIVE_DEFAULTS = {
    'base_delay_ms': 10000,
    'max_nudges': 3,
    'min_check_ms': 4000,
    'max_check_ms': 30000,
    'timeout': 20,
}


def _proactive_config():
    merged = dict(PROACTIVE_DEFAULTS)
    cfg = getattr(config, 'PROACTIVE_CONFIG', {}) or {}
    if isinstance(cfg, dict):
        for key in list(merged):
            if key in cfg:
                merged[key] = cfg[key]
    return merged


def _clamp_int(value, low, high, default):
    try:
        num = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, num))


def _extract_json_object(raw):
    """从模型返回文本里安全抽出 JSON 对象；失败返回 None。"""
    text = str(raw or '').strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            return None
    return None


def _nudge_wait(pcfg):
    """安全降级：什么都不说，稍后再看一眼（判定失败=继续等待）。"""
    return {
        'success': False,
        'should_speak': False,
        'level': 0,
        'text': '',
        'await_reply': True,
        'next_check_in_ms': _clamp_int(pcfg.get('base_delay_ms'), 4000, 30000, 8000),
        'handoff': None,
    }


def _nudge_user_content(page_context, silence, engagement, nudge_count, cap):
    snapshot = {
        '当前环节': _clean_text(page_context.get('lesson_title'), 120),
        '教学目标': _clean_text(page_context.get('goal'), 240),
        '屏幕教学文字': _clean_text(page_context.get('visible_text'), 2000),
        '孩子刚才的操作': _clean_text(engagement.get('last_action') or page_context.get('last_action'), 300),
        '已拼出的表达': _clean_text(engagement.get('constructed_phrase') or page_context.get('constructed_phrase'), 200),
        '偏好设置': page_context.get('preferences') or {},
    }
    wait_state = {
        '距老师提问秒数': _clamp_int(silence.get('since_prompt_s'), 0, 3600, 0),
        '距老师说完秒数': _clamp_int(silence.get('since_ai_done_s'), 0, 3600, 0),
        '距孩子任何动作秒数': _clamp_int(silence.get('since_any_action_s'), 0, 3600, 0),
        '本次已提示次数': nudge_count,
        '同一提问提示上限': cap,
        '孩子平时回应耗时中位数毫秒': _clamp_int(engagement.get('baseline_latency_ms'), 0, 120000, 0),
        '已开始拼词但未完成': bool(engagement.get('partial_attempt')),
        '本轮是否已回应过': bool(engagement.get('answered_last_turn')),
    }
    payload = json.dumps(
        {'学习区状态': snapshot, '等待观察': wait_state}, ensure_ascii=False)[:MAX_CONTEXT_CHARS]
    return ('这是教学决策回合：孩子在你上一次提问后已经沉默，下面是学习区状态与等待观察数据。'
            '请按规则只输出一个 JSON 对象，判断此刻该不该开口、要不要继续等。\n\n' + payload)


def _parse_nudge_decision(raw, nudge_count, cap, pcfg):
    data = _extract_json_object(raw)
    if not isinstance(data, dict):
        return _nudge_wait(pcfg)
    min_check = _clamp_int(pcfg.get('min_check_ms'), 1000, 60000, 4000)
    max_check = _clamp_int(pcfg.get('max_check_ms'), min_check, 120000, 30000)
    should_speak = bool(data.get('should_speak'))
    level = _clamp_int(data.get('level'), 0, 4, 0)
    text = _clean_text(data.get('text'), 160)
    await_reply = bool(data.get('await_reply', True))
    next_check = _clamp_int(
        data.get('next_check_in_ms'), min_check, max_check,
        _clamp_int(pcfg.get('base_delay_ms'), min_check, max_check, 8000))
    handoff_raw = data.get('handoff')
    handoff = handoff_raw if handoff_raw in ('caregiver', 'break') else None
    if not text:
        should_speak = False
    # 到顶就不再问孩子，把控制权交还给照护者。
    if nudge_count >= cap:
        should_speak = False
        handoff = 'caregiver'
        await_reply = False
    return {
        'success': True,
        'should_speak': should_speak,
        'level': level,
        'text': text,
        'await_reply': await_reply,
        'next_check_in_ms': next_check,
        'handoff': handoff,
    }


@aiteacher_bp.route('/api/nudge', methods=['POST'])
def nudge():
    """孩子沉默一段时间后，判断 AI 老师此刻该不该主动开口引导。"""
    body = request.get_json(silent=True) or {}
    pcfg = _proactive_config()
    try:
        body = _hydrate_material_context(body)
    except (MaterialError, FileNotFoundError):
        decision = _nudge_wait(pcfg)
        decision['await_reply'] = False
        return jsonify(decision)

    page_context = body.get('page_context') or {}
    silence = body.get('silence') if isinstance(body.get('silence'), dict) else {}
    engagement = body.get('engagement') if isinstance(body.get('engagement'), dict) else {}
    cap = _clamp_int(pcfg.get('max_nudges'), 1, 8, 3)
    nudge_count = _clamp_int(silence.get('nudge_count'), 0, 50, 0)

    # 硬上限：到顶不再问孩子，直接交还照护者。
    if nudge_count >= cap:
        decision = _nudge_wait(pcfg)
        decision.update({'should_speak': False, 'handoff': 'caregiver', 'await_reply': False})
        return jsonify(decision)

    owner = _current_material_owner()
    material_id = page_context.get('builtin_id') or page_context.get('material_id') or ''
    memory_block = memory.load_memory_context(owner, material_id)
    system_prompt = build_proactive_system_prompt(
        memory_block, (body.get('material_bits') or {}).get('teacher_notes', ''))
    user_content = _nudge_user_content(page_context, silence, engagement, nudge_count, cap)

    try:
        client = LLMClient(language='zh')
        raw = client.generate(
            system_prompt, user_content, stream=False,
            temperature=0.3, timeout=int(pcfg.get('timeout') or 20))
        return jsonify(_parse_nudge_decision(raw, nudge_count, cap, pcfg))
    except Exception as exc:
        logger.error('aiteacher nudge 失败: %s', exc)
        return jsonify(_nudge_wait(pcfg))
