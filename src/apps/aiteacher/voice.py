#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A教师的语音转文字客户端；密钥始终保留在服务端。"""

import base64
import os

import requests

import config.config as config


MIME_TYPES = {
    '.webm': 'audio/webm',
    '.wav': 'audio/wav',
    '.mp3': 'audio/mpeg',
    '.m4a': 'audio/mp4',
    '.ogg': 'audio/ogg',
}


def _base_url():
    configured = str(getattr(config, 'DASHSCOPE_BASE_URL', '') or '').strip()
    if configured:
        return configured.rstrip('/').rsplit('/chat/completions', 1)[0]
    qwen_url = str(getattr(config, 'QWEN_BASE_URL', '') or '').strip()
    if qwen_url and 'token-plan' not in qwen_url:
        return qwen_url.rstrip('/').rsplit('/chat/completions', 1)[0]
    return 'https://dashscope.aliyuncs.com/compatible-mode/v1'


def transcribe(audio_bytes, filename='speech.webm'):
    """调用千问 ASR，把浏览器录音转换为中文文本。"""
    api_key = (getattr(config, 'DASHSCOPE_API_KEY', '') or
               getattr(config, 'QWEN_API_KEY', ''))
    if not api_key:
        raise ValueError('服务器尚未配置语音识别 API Key')

    ext = os.path.splitext(filename or '')[1].lower() or '.webm'
    mime = MIME_TYPES.get(ext, 'application/octet-stream')
    data_uri = 'data:%s;base64,%s' % (
        mime, base64.b64encode(audio_bytes).decode('ascii'))
    response = requests.post(
        _base_url() + '/chat/completions',
        headers={'Authorization': 'Bearer ' + api_key},
        json={
            'model': 'qwen3-asr-flash',
            'messages': [{
                'role': 'user',
                'content': [{'type': 'input_audio', 'input_audio': data_uri}],
            }],
        },
        timeout=120,
    )
    if response.status_code != 200:
        raise RuntimeError('语音识别服务返回 HTTP %s' % response.status_code)
    choices = response.json().get('choices') or []
    text = ((choices[0].get('message') or {}).get('content') if choices else '')
    text = str(text or '').strip()
    if not text:
        raise ValueError('没有识别到清晰的话语，请再试一次')
    return text
