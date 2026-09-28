#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A教师的语音转文字客户端；密钥始终保留在服务端。"""

import base64
import json
import os
import re
import struct

import requests

import config.config as config
from src.logger import logger


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


# 默认的非实时语音合成端点（阿里云百炼 DashScope 公共端点）。
TTS_ENDPOINT = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation'

# 合成前需要去掉的行内 Markdown 符号（*、#、`、~），与前端保持
# 一致，避免把符号读成“星号 / 井号”。
_MD_NOISE_RE = re.compile(r'[*#`~]')

# 默认选中的音色（用户没有主动选择时使用）。
# 必须是固定音色：VoxCPM2 的音色靠文字描述现场"演"一个说话人，实测同一句
# 两次合成的基频能差 12~18%（听着就是换了个人），不能当默认音色，详见下方
# VOXCPM_VOICE_OPTIONS 的 unstable 标记。
DEFAULT_VOICE = 'Serena'

# Qwen3-TTS 的回退音色；VoxCPM2 不可用时用它保证孩子仍然有声音。
FALLBACK_QWEN_VOICE = 'Cherry'

# ModelBest（OpenBMB）VoxCPM2：与 Qwen 的固定音色代码不同，它的音色是用
# 自然语言「描述」出来的，可选范围不受白名单限制。
VOXCPM_ENDPOINT = 'https://api.modelbest.cn/v1/audio/speech'
VOXCPM_MODEL = 'VoxCPM2'

# ⚠️ 描述必须写成「半角」括号并放在正文最前面：实测半角 (描述) 会被当成
# 音色设计说明、不会被念出来；一旦写成全角（描述）就会被当正文照读。
QWEN_VOICE_OPTIONS = [
    {'code': 'Cherry', 'name': '芊悦', 'gender': '女声', 'desc': '阳光亲切的小姐姐'},
    {'code': 'Serena', 'name': '苏瑶', 'gender': '女声', 'desc': '温柔舒缓，适合耐心讲解'},
    {'code': 'Maia', 'name': '四月', 'gender': '女声', 'desc': '知性与温柔并存'},
    {'code': 'Momo', 'name': '茉兔', 'gender': '女声', 'desc': '撒娇搞怪，逗孩子开心'},
    {'code': 'Vivian', 'name': '十三', 'gender': '女声', 'desc': '拽拽的、可爱的小暴躁'},
    {'code': 'Bella', 'name': '萌宝', 'gender': '童声', 'desc': '软萌小萝莉，奶声奶气'},
    {'code': 'Stella', 'name': '阿月', 'gender': '童声', 'desc': '甜甜的迷糊少女音'},
    {'code': 'Chelsie', 'name': '千雪', 'gender': '女声', 'desc': '二次元虚拟女友感'},
    {'code': 'Pip', 'name': '顽屁小孩', 'gender': '童声', 'desc': '调皮童真，像蜡笔小新'},
    {'code': 'Ethan', 'name': '晨煦', 'gender': '男声', 'desc': '标准普通话，阳光有活力'},
    {'code': 'Moon', 'name': '月白', 'gender': '男声', 'desc': '率性帅气，利落干脆'},
    {'code': 'Kai', 'name': '凯', 'gender': '男声', 'desc': '温柔治愈，像做耳部 SPA'},
]

# 真人感更强的 VoxCPM2 音色组，放在面板最前面供优先选择。
# unstable：这个模型的音色无法锁定（voice 参数只认 default，也不接受参考音频
# 和 seed），每轮请求都可能换个说话人。前端要据此提醒用户，避免被当成故障。
VOXCPM_VOICE_OPTIONS = [
    {'code': 'vox-wenrou', 'name': '温柔老师', 'gender': '女声·真人',
     'desc': '年轻女声，温柔耐心，语速偏慢', 'unstable': True,
     'design': '年轻女性，声音温柔甜美，语速偏慢，耐心亲切，吐字清楚'},
    {'code': 'vox-kailang', 'name': '开朗姐姐', 'gender': '女声·真人',
     'desc': '明亮有笑意，适合带动情绪', 'unstable': True,
     'design': '年轻女性，声音明亮活泼，带着笑意，语速中等，有感染力'},
    {'code': 'vox-male', 'name': '男老师', 'gender': '男声·真人',
     'desc': '中年男声，低沉温和，句子清楚', 'unstable': True,
     'design': '中年男性，声音温和低沉，语速慢，吐字清楚，有耐心'},
    {'code': 'vox-kid', 'name': '同龄伙伴', 'gender': '童声·真人',
     'desc': '六岁童声，奶声奶气，陪孩子一起练', 'unstable': True,
     'design': '六岁小男孩，奶声奶气，说话清脆，语速偏慢，天真友好'},
]

VOICE_OPTIONS = VOXCPM_VOICE_OPTIONS + QWEN_VOICE_OPTIONS

VOICE_CODES = {option['code'] for option in VOICE_OPTIONS}

# 音色代码 -> VoxCPM2 的自然语言音色描述；没有登记在这里的代码走 Qwen。
VOXCPM_DESIGNS = {option['code']: option['design']
                  for option in VOXCPM_VOICE_OPTIONS}

QWEN_VOICE_CODES = {option['code'] for option in QWEN_VOICE_OPTIONS}


def _safe_voice(voice, fallback=None):
    """把外部传入的音色收敛到白名单，非法值回退到配置默认音色。"""
    selected = str(voice or '').strip()
    if selected in VOICE_CODES:
        return selected
    configured = str(fallback or '').strip()
    if configured in VOICE_CODES:
        return configured
    return DEFAULT_VOICE


def _tts_config():
    return getattr(config, 'TTS_CONFIG', {}) or {}


def _tts_text_clean(value):
    text = _MD_NOISE_RE.sub('', str(value or ''))
    return re.sub(r'\s+', ' ', text).strip()


def _split_text(text, limit):
    """把长文本按句子边界切成不超过 limit 字符的多段。"""
    limit = max(50, int(limit or 500))
    if len(text) <= limit:
        return [text]
    # 优先在句末标点处切分；其次按逗号；最后硬切。
    sentences = re.split(r'(?<=[。！？!?；;，,\n])', text)
    chunks = []
    buf = ''
    for sentence in sentences:
        if not sentence:
            continue
        if len(buf) + len(sentence) <= limit:
            buf += sentence
            continue
        if buf:
            chunks.append(buf)
            buf = ''
        # 单句本身就超长时，按固定长度硬切。
        while len(sentence) > limit:
            chunks.append(sentence[:limit])
            sentence = sentence[limit:]
        buf = sentence
    if buf:
        chunks.append(buf)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _synthesize_qwen(text, selected_voice, cfg):
    """调用 Qwen3-TTS 把文本合成为语音，返回多个 wav 的 data URI 列表。

    密钥始终保留在服务端；服务端拉取音频后以 base64 回传给浏览器，
    避免页面直接接触密钥、也规避音频 URL 的跨域/混合内容限制。
    """
    api_key = str(
        cfg.get('api_key')
        or getattr(config, 'DASHSCOPE_API_KEY', '')
        or getattr(config, 'QWEN_API_KEY', '')
        or ''
    ).strip()
    if not api_key:
        raise ValueError('服务器尚未配置语音合成 API Key')

    endpoint = str(cfg.get('endpoint') or TTS_ENDPOINT).strip()
    timeout = int(cfg.get('timeout') or 60)
    headers = {'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'}
    clips = []
    for chunk in _split_text(text, cfg.get('max_chars')):
        payload = {
            'model': cfg.get('model') or 'qwen3-tts-flash',
            'input': {
                'text': chunk,
                'voice': selected_voice,
                'language_type': cfg.get('language_type') or 'Chinese',
            },
        }
        response = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
        if response.status_code != 200:
            raise RuntimeError('语音合成服务返回 HTTP %s' % response.status_code)
        audio = (response.json().get('output') or {}).get('audio') or {}
        wav_bytes = b''
        if audio.get('data'):
            wav_bytes = base64.b64decode(audio['data'])
        elif audio.get('url'):
            download = requests.get(audio['url'], timeout=timeout)
            if download.status_code != 200:
                raise RuntimeError('音频下载失败 HTTP %s' % download.status_code)
            wav_bytes = download.content
        if not wav_bytes:
            raise RuntimeError('语音合成没有返回音频')
        clips.append('data:audio/wav;base64,' + base64.b64encode(wav_bytes).decode('ascii'))
    if not clips:
        raise ValueError('没有可合成的文字内容')
    return clips


def _voxcpm_config():
    cfg = getattr(config, 'VOXCPM_CONFIG', {}) or {}
    api_key = str(
        cfg.get('api_key')
        or getattr(config, 'MODELBEST_API_KEY', '')
        or ''
    ).strip()
    return cfg, api_key


def _fix_wav_sizes(blob):
    """把服务端写死为 0xffffffff 占位的 RIFF/data 长度回填成真实值。"""
    if len(blob) < 44 or blob[:4] != b'RIFF' or blob[8:12] != b'WAVE':
        return blob
    out = bytearray(blob)
    struct.pack_into('<I', out, 4, len(out) - 8)
    data_at = out.find(b'data', 12)
    if data_at != -1:
        struct.pack_into('<I', out, data_at + 4, len(out) - data_at - 8)
    return bytes(out)


def _voxcpm_request(endpoint, api_key, model, text, timeout):
    """请求一次 VoxCPM2，返回拼好的 wav 字节；没有音频时返回空 bytes。

    VoxCPM2 只有 SSE 分块返回：首个分块带 44 字节 RIFF 头，之后是连续的
    裸 PCM，按顺序拼接才是一个完整 wav（48kHz/单声道/16bit）。
    """
    response = requests.post(
        endpoint,
        headers={'Authorization': 'Bearer ' + api_key,
                 'Content-Type': 'application/json'},
        json={'model': model, 'input': text,
              'voice': 'default', 'response_format': 'wav'},
        timeout=timeout,
        stream=True,
    )
    if response.status_code != 200:
        raise RuntimeError('语音合成服务返回 HTTP %s' % response.status_code)
    pieces = []
    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith('data:'):
            continue
        try:
            event = json.loads(line[5:].strip())
        except ValueError:
            continue
        if event.get('error'):
            raise RuntimeError('语音合成失败: %s' % str(event.get('error'))[:200])
        if event.get('type') == 'speech.audio.delta' and event.get('audio'):
            pieces.append(base64.b64decode(event['audio']))
    return _fix_wav_sizes(b''.join(pieces)) if pieces else b''


def _synthesize_voxcpm(text, design):
    """用 VoxCPM2 合成，返回 wav data URI 列表。

    两个实测坑点：
    1. 每个分块都要重新带上 (音色描述)，否则后半段会掉回默认音色、听起来像换了人；
    2. 单次长度必须收紧，input+output 合计受 4096 token 限制，超出后服务端
       不报错、直接静默截断音频。
    """
    cfg, api_key = _voxcpm_config()
    if not api_key:
        raise ValueError('服务器尚未配置 ModelBest 语音合成 API Key')
    endpoint = str(cfg.get('endpoint') or VOXCPM_ENDPOINT).strip()
    model = str(cfg.get('model') or VOXCPM_MODEL).strip()
    timeout = int(cfg.get('timeout') or 60)
    limit = int(cfg.get('max_chars') or 400)
    clips = []
    for chunk in _split_text(text, limit):
        wav = _voxcpm_request(endpoint, api_key, model,
                              '(%s)%s' % (design, chunk), timeout)
        if not wav:
            # 超长被静默截断、或额度用尽时都会走到这里，交给调用方回落。
            raise RuntimeError('语音合成没有返回音频')
        clips.append('data:audio/wav;base64,' + base64.b64encode(wav).decode('ascii'))
    if not clips:
        raise ValueError('没有可合成的文字内容')
    return clips


def synthesize(text, voice=None):
    """把文本合成为语音，返回 ``(clips, info)``。

    voice：音色代码。``vox-`` 开头走 ModelBest VoxCPM2（用自然语言描述定制
    音色，真人感更强），其余走阿里云百炼 Qwen3-TTS 固定音色。

    info 形如 ``{'requested': 用户选的音色, 'served': 真正出声的音色,
    'degraded': 是否换了音色, 'reason': 换的原因}``。VoxCPM2 失败时会回落到
    Qwen3-TTS 保证孩子仍然有声音，但那等于换了个人说话，所以必须标出来交给
    前端提示用户，不能再静默替换。
    """
    clean = _tts_text_clean(text)
    selected = _safe_voice(voice)
    info = {'requested': selected, 'served': selected, 'degraded': False, 'reason': ''}
    if not clean:
        return [], info
    cfg = _tts_config()
    # 不传 cfg['voice'] 作为兼容回退：那个值是 Qwen 回退音色，不是默认上口音色。
    design = VOXCPM_DESIGNS.get(selected)
    if not design:
        return _synthesize_qwen(clean, selected, cfg), info
    try:
        return _synthesize_voxcpm(clean, design), info
    except Exception as exc:
        logger.warning('VoxCPM2 合成失败，回落 Qwen3-TTS: %s', exc)
        configured = str(cfg.get('voice') or '').strip()
        fallback = configured if configured in QWEN_VOICE_CODES else FALLBACK_QWEN_VOICE
        clips = _synthesize_qwen(clean, fallback, cfg)
        info.update(served=fallback, degraded=True, reason=str(exc)[:200])
        return clips, info
