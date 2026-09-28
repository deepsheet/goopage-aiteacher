#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""学习材料的生成、抓取、上传、文本提取和本地持久化。"""

import html
import ipaddress
import json
import os
import re
import socket
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import markdown
import requests
from bs4 import BeautifulSoup
from werkzeug.utils import secure_filename

from src.apps.aiteacher.material_manifest import manifest_bits
from src.logger import logger


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = Path(
    os.environ.get('AITEACHER_DATA_ROOT', PROJECT_ROOT / 'data' / 'users')
).expanduser().resolve()

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_FETCH_BYTES = 5 * 1024 * 1024
MAX_MATERIAL_TEXT_CHARS = 30000
# 生成整页 HTML 课件时的最大输出 token；现代模型支持长输出，默认 3 万。
MAX_HTML_OUTPUT_TOKENS = int(os.environ.get('AITEACHER_MATERIAL_MAX_TOKENS', '30000'))
ALLOWED_UPLOAD_EXTENSIONS = {'.html', '.htm', '.md', '.markdown', '.txt'}
MATERIAL_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{8,80}$')


class MaterialError(ValueError):
    """可以安全展示给用户的学习材料错误。"""


def safe_owner_name(value):
    """把用户名转换为安全且可读的单层目录名。"""
    cleaned = re.sub(r'[^\w.-]+', '-', str(value or ''), flags=re.UNICODE)
    cleaned = cleaned.strip('._-')[:64]
    return cleaned or 'guest'


def user_material_dir(owner):
    """返回用户材料目录，并确保结果不会逃逸 DATA_ROOT。"""
    root = DATA_ROOT.resolve()
    folder = (root / safe_owner_name(owner)).resolve()
    if folder.parent != root:
        raise MaterialError('无效的用户目录')
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _new_material_id():
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    return '%s-%s' % (stamp, uuid.uuid4().hex[:8])


def _decode_bytes(data, preferred_encoding=None):
    encodings = [preferred_encoding, 'utf-8-sig', 'utf-8', 'gb18030']
    for encoding in encodings:
        if not encoding:
            continue
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode('utf-8', errors='replace')


def extract_html_text(html_source):
    """提取网页中适合交给 AI 的可见文字。"""
    soup = BeautifulSoup(str(html_source or ''), 'html.parser')
    for node in soup(['script', 'style', 'noscript', 'template', 'svg']):
        node.decompose()
    text = soup.get_text('\n', strip=True)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text[:MAX_MATERIAL_TEXT_CHARS]


def _document_title(html_source, fallback):
    soup = BeautifulSoup(str(html_source or ''), 'html.parser')
    if soup.title and soup.title.string:
        return soup.title.string.strip()[:120]
    heading = soup.find(['h1', 'h2'])
    if heading:
        return heading.get_text(' ', strip=True)[:120]
    return str(fallback or '学习材料').strip()[:120] or '学习材料'


def _complete_html(html_source, title='学习材料', base_url=None):
    """确保材料是完整 HTML，并为远程快照补充 base URL。"""
    source = str(html_source or '').strip()
    if not source:
        raise MaterialError('学习材料内容为空')
    if '<html' not in source.lower():
        source = (
            '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s</title></head><body>%s</body></html>'
        ) % (html.escape(title), source)
    if base_url:
        soup = BeautifulSoup(source, 'html.parser')
        if soup.head is None:
            head = soup.new_tag('head')
            if soup.html:
                soup.html.insert(0, head)
            else:
                soup.insert(0, head)
        existing = soup.head.find('base')
        if existing:
            existing['href'] = base_url
        else:
            base = soup.new_tag('base', href=base_url)
            soup.head.insert(0, base)
        source = str(soup)
    return source


def _extract_generated_html(model_output):
    """从模型输出中只截取完整 HTML，丢弃可能混入的规划或解释文字。"""
    source = str(model_output or '').strip()
    source = re.sub(r'^\s*```(?:html)?\s*', '', source, flags=re.I)
    source = re.sub(r'\s*```\s*$', '', source, flags=re.I)
    lowered = source.lower()
    html_starts = [match.start() for match in re.finditer(r'<html(?:\s|>)', lowered)]
    doctype_starts = [match.start() for match in re.finditer(r'<!doctype\s+html(?:\s|>)', lowered)]
    start = None
    # 选择靠近真正 <html> 根标签的 doctype，避免规划文字里提到标签时误截取。
    for doctype_start in reversed(doctype_starts):
        if any(doctype_start < html_start <= doctype_start + 300 for html_start in html_starts):
            start = doctype_start
            break
    if start is None and html_starts:
        start = html_starts[-1]
    if start is None:
        raise MaterialError('AI 没有返回可打开的 HTML 课件')
    end = lowered.rfind('</html>')
    if end >= start:
        document = source[start:end + len('</html>')].strip()
    else:
        # 模型输出被长度截断、没写到 </html>：
        # 不直接丢弃已生成的内容，先取 start 之后的全部输出，
        # 再交给 BeautifulSoup 自动闭合未关闭的标签，挽救大部分课件。
        document = source[start:].strip()
    if not document.lower().startswith('<!doctype html'):
        document = '<!doctype html>\n' + document
    soup = BeautifulSoup(document, 'html.parser')
    if soup.html is None or soup.body is None or len(extract_html_text(document)) < 20:
        raise MaterialError('AI 返回的 HTML 课件内容不完整')
    if end < start:
        document = str(soup)
        logger.warning('检测到课件 HTML 未正常收尾，已自动闭合标签挽救已生成内容')
    return document


def _text_document_html(title, text, is_markdown=False):
    if is_markdown:
        body = markdown.markdown(
            text,
            extensions=['extra', 'sane_lists'],
            output_format='html5',
        )
    else:
        body = '<pre>%s</pre>' % html.escape(text)
    return '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
:root {{ color-scheme: light; }}
body {{ margin:0; padding:clamp(24px,5vw,64px); color:#253028; background:#fbfcf8;
font:16px/1.8 system-ui,-apple-system,"Noto Sans SC",sans-serif; }}
article {{ max-width:860px; margin:auto; padding:clamp(24px,5vw,56px); background:#fff;
border:1px solid #e3e8df; border-radius:24px; box-shadow:0 18px 60px rgba(38,55,43,.08); }}
h1,h2,h3 {{ line-height:1.3; color:#1f5d4a; }}
pre {{ margin:0; white-space:pre-wrap; overflow-wrap:anywhere; font:inherit; }}
img {{ max-width:100%; }} table {{ border-collapse:collapse; width:100%; }}
th,td {{ border:1px solid #dfe5dc; padding:8px 10px; text-align:left; }}
code {{ background:#f0f3ee; border-radius:5px; padding:.1em .35em; }}
</style></head><body><article>{body}</article></body></html>'''.format(
        title=html.escape(title), body=body)


def _persistable_metadata(metadata):
    """落盘时去掉内嵌正文与派生字段：课件内容以 HTML 文件（viewer_file）为唯一事实源，
    JSON 只保留标题、来源与指向 html 文件的元数据；text 与 manifest 在读取时从 HTML 即时派生。"""
    return {key: value for key, value in metadata.items()
            if key not in ('text', 'manifest')}


def _write_material(owner, title, html_source, text, source_type,
                    source_label='', original_name=''):
    material_id = _new_material_id()
    folder = user_material_dir(owner)
    viewer_name = material_id + '.html'
    metadata_name = material_id + '.json'
    html_path = folder / viewer_name
    viewer_html = _complete_html(html_source, title)
    html_path.write_text(viewer_html, encoding='utf-8')
    metadata = {
        'id': material_id,
        'title': str(title or '学习材料')[:120],
        'source_type': source_type,
        'source_label': str(source_label or '')[:500],
        'original_name': str(original_name or '')[:255],
        'text': str(text or '')[:MAX_MATERIAL_TEXT_CHARS],
        'viewer_file': viewer_name,
        'created_at': datetime.now().isoformat(timespec='seconds'),
    }
    (folder / metadata_name).write_text(
        json.dumps(_persistable_metadata(metadata), ensure_ascii=False, indent=2),
        encoding='utf-8')
    # 创建响应就带上能力清单，否则前端刚拿到这份课件时会误判它不支持任何操作指令。
    # 落盘的 JSON 不含该字段（_persistable_metadata 已剔除），读取时一律从 HTML 即时派生。
    metadata['manifest'] = manifest_bits(metadata, viewer_html)
    return metadata


def create_generated_material(owner, requirement, llm_client):
    requirement = str(requirement or '').strip()
    if not requirement:
        raise MaterialError('请描述想学习的内容或目标')
    if len(requirement) > 6000:
        raise MaterialError('学习需求不能超过 6000 个字符')

    system_prompt = """你是一位优秀的课程设计师和前端开发者。请根据学习需求生成一个完整、独立、可直接打开的中文 HTML 教学网页。
要求：
1. 只输出 HTML，从 <!doctype html> 开始，不要 Markdown 代码块或解释。
2. 页面必须包含清晰的学习目标、分步骤讲解、例子、练习和答案提示。
3. 使用响应式布局、舒适字号、高对比度和内联 CSS；允许少量内联 JavaScript 实现练习互动。
4. 不引用外部脚本，不提交表单到外部网站，不收集个人信息。
5. 内容应准确、循序渐进，并适合学生独立阅读与 AI 老师配合讲解。
6. 篇幅要适度、确保在输出上限内完成：宁可每节精炼，也必须以 </html> 正常收尾，切勿中途断掉。
7. 本页会被放进一个 sandbox 的 iframe，与左侧 AI 对话区通过 postMessage 配合（协议见 docs/material-protocol.md）。若页面有练习/闯关等互动区，按下面接入：
   - 上报学习事件：parent.postMessage({type:'aiteacher-learning-action', action:'一句话说明刚发生了什么', spoken:'', respond:false}, '*')。只在关键节点（同一处连错两次、学生主动求助、本环节完成）把 respond 设为 true 以召唤老师；填对一格这类高频事件保持 respond:false。要读给孩子听的话放 spoken，页面刚加载时不要发 spoken（没有用户手势，朗读会被浏览器拦掉）。
   - 接受老师操作：实现 window.__aiteacherCmd = function ({action, value}) { ... return true或false }，必须同步返回布尔值，同一条指令重复到达不能出错，找不到目标或不支持就返回 false。
   - 声明能力：在 </body> 前加一段 <script type="application/aiteacher+json" id="aiteacher-manifest">，内容是 {"schema":1,"commands":["hint"],"teacher_notes":"给老师的本课教学须知"}。commands 只能填 hint / reveal / step 中你真正实现了的那几个：hint=给目标一个提示，reveal=公布目标答案，step=跳到指定环节。没有互动区就整段脚本不要写，也不要在代码里写 teacher_notes 以外的提示词。
8. iframe 内没有可用的 localStorage，学习进度只存内存；AI 老师只能读到页面上可见的文字，所以答案、选项含义、判分要点必须写成页面可见内容，不能只藏在 data-* 属性里。"""
    generation_options = {}
    if str(getattr(llm_client, 'model_name', '')).lower() == 'deepseek':
        # 网页生成需要把输出额度留给完整 HTML，避免默认思考过程挤占 token。
        generation_options['thinking'] = 'disabled'
    generated = llm_client.generate(
        system_prompt,
        '学习需求：\n' + requirement,
        max_tokens=MAX_HTML_OUTPUT_TOKENS,
        temperature=0.45,
        stream=False,
        timeout=600,
        **generation_options,
    )
    try:
        completed = _extract_generated_html(generated)
    except MaterialError:
        # 某些推理模型会只返回规划文字；自动追加一次严格纠正，而不是保存错误内容。
        generated = llm_client.generate(
            system_prompt,
            '学习需求：\n%s\n\n上一次没有返回完整网页。现在不要分析、不要解释，直接从 <!doctype html> 开始输出完整 HTML，并以 </html> 结束。' % requirement,
            max_tokens=MAX_HTML_OUTPUT_TOKENS,
            temperature=0.25,
            stream=False,
            timeout=600,
            **generation_options,
        )
        completed = _extract_generated_html(generated)
    title = _document_title(completed, requirement[:40])
    text = extract_html_text(completed)
    return _write_material(
        owner, title, completed, text, 'generated', requirement[:500])


def _validate_fetch_url(url):
    parsed = urlsplit(str(url or '').strip())
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise MaterialError('请输入以 http:// 或 https:// 开头的网址')
    if parsed.username or parsed.password:
        raise MaterialError('网址不能包含账号或密码')
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 80, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise MaterialError('无法解析这个网址') from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        # 本产品明确支持 localhost 和局域网学习页面；仍阻止链路本地
        # （包括常见云元数据地址）、组播、未指定和其他保留地址。
        if (not ip.is_loopback and
                (ip.is_link_local or ip.is_multicast or
                 ip.is_unspecified or ip.is_reserved)):
            raise MaterialError('不允许访问链路本地、保留或组播地址')
    return parsed.geturl()


def _download_url(url):
    current_url = _validate_fetch_url(url)
    headers = {'User-Agent': 'AITeacher/1.0 (+local learning material reader)'}
    for _ in range(5):
        response = requests.get(
            current_url,
            headers=headers,
            timeout=(5, 20),
            stream=True,
            allow_redirects=False,
        )
        if response.status_code in (301, 302, 303, 307, 308):
            redirect_to = response.headers.get('Location')
            response.close()
            if not redirect_to:
                raise MaterialError('网页重定向地址无效')
            current_url = _validate_fetch_url(urljoin(current_url, redirect_to))
            continue
        if response.status_code >= 400:
            status = response.status_code
            response.close()
            raise MaterialError('网页访问失败（HTTP %s）' % status)
        content_length = int(response.headers.get('Content-Length') or 0)
        if content_length > MAX_FETCH_BYTES:
            response.close()
            raise MaterialError('网页内容不能超过 5MB')
        chunks = []
        size = 0
        for chunk in response.iter_content(64 * 1024):
            if not chunk:
                continue
            size += len(chunk)
            if size > MAX_FETCH_BYTES:
                response.close()
                raise MaterialError('网页内容不能超过 5MB')
            chunks.append(chunk)
        data = b''.join(chunks)
        content_type = (response.headers.get('Content-Type') or '').lower()
        encoding = response.encoding
        response.close()
        return current_url, data, content_type, encoding
    raise MaterialError('网页重定向次数过多')


def create_url_material(owner, url):
    final_url, data, content_type, encoding = _download_url(url)
    text_source = _decode_bytes(data, encoding)
    is_html = ('html' in content_type or
               '<html' in text_source[:1000].lower() or
               '<!doctype html' in text_source[:1000].lower())
    if is_html:
        snapshot = _complete_html(text_source, final_url, base_url=final_url)
        title = _document_title(snapshot, urlsplit(final_url).hostname)
        extracted = extract_html_text(snapshot)
    elif ('text/' in content_type or 'markdown' in content_type or not content_type):
        title = Path(urlsplit(final_url).path).name or urlsplit(final_url).hostname
        extracted = text_source[:MAX_MATERIAL_TEXT_CHARS]
        snapshot = _text_document_html(title, extracted, 'markdown' in content_type)
    else:
        raise MaterialError('该网址不是可读取的网页或文本内容')
    return _write_material(
        owner, title, snapshot, extracted, 'url', final_url)


def create_uploaded_material(owner, uploaded_file):
    original_name = Path(str(uploaded_file.filename or '')).name
    extension = Path(original_name).suffix.lower()
    safe_stem = secure_filename(Path(original_name).stem) or 'material'
    filename = safe_stem[:180] + extension
    if not original_name or extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise MaterialError('仅支持 HTML、Markdown 和 TXT 文件')
    data = uploaded_file.stream.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise MaterialError('上传文件内容为空')
    if len(data) > MAX_UPLOAD_BYTES:
        raise MaterialError('上传文件不能超过 5MB')
    source = _decode_bytes(data)
    title = Path(filename).stem[:120] or '学习材料'
    if extension in ('.html', '.htm'):
        snapshot = _complete_html(source, title)
        title = _document_title(snapshot, title)
        extracted = extract_html_text(snapshot)
    elif extension in ('.md', '.markdown'):
        extracted = source[:MAX_MATERIAL_TEXT_CHARS]
        snapshot = _text_document_html(title, extracted, is_markdown=True)
    else:
        extracted = source[:MAX_MATERIAL_TEXT_CHARS]
        snapshot = _text_document_html(title, extracted)
    return _write_material(
        owner, title, snapshot, extracted, 'upload', original_name, original_name)


def load_material(owner, material_id):
    if not MATERIAL_ID_PATTERN.fullmatch(str(material_id or '')):
        raise MaterialError('无效的学习材料编号')
    folder = user_material_dir(owner)
    metadata_path = folder / (material_id + '.json')
    if not metadata_path.is_file():
        raise FileNotFoundError('学习材料不存在')
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    viewer_path = (folder / metadata['viewer_file']).resolve()
    if viewer_path.parent != folder.resolve() or not viewer_path.is_file():
        raise FileNotFoundError('学习材料文件不存在')
    source = viewer_path.read_text(encoding='utf-8', errors='replace')
    if metadata.get('source_type') == 'generated':
        # 兼容早期版本：模型可能把规划文字放在完整 HTML 前面。
        try:
            repaired = _extract_generated_html(source)
        except MaterialError:
            repaired = None
        if repaired and repaired.strip() != source.strip():
            viewer_path.write_text(repaired, encoding='utf-8')
            metadata['title'] = _document_title(repaired, metadata.get('title'))
            metadata_path.write_text(
                json.dumps(_persistable_metadata(metadata), ensure_ascii=False, indent=2),
                encoding='utf-8')
            source = repaired
    # 课件正文以 HTML 文件为唯一事实源，读取时即时派生纯文本与能力清单供 AI 讲解使用。
    metadata['text'] = extract_html_text(source)
    metadata['manifest'] = manifest_bits(metadata, source)
    return metadata, viewer_path


def list_materials(owner, limit=50):
    """列出当前用户已保存且仍可打开的材料，最新的排在前面。"""
    folder = user_material_dir(owner)
    materials = []
    candidates = sorted(
        folder.glob('*.json'), key=lambda path: path.stat().st_mtime, reverse=True)
    for metadata_path in candidates:
        if len(materials) >= limit:
            break
        material_id = metadata_path.stem
        try:
            metadata, _ = load_material(owner, material_id)
        except (MaterialError, FileNotFoundError, KeyError, json.JSONDecodeError):
            continue
        materials.append(metadata)
    return materials
