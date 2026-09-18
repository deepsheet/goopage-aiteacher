#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
国际化(i18n)模块 - 多语言支持
包含 UI 翻译文本和 LLM 提示词模板
采用延迟加载机制,每种语言独立文件,按需加载

架构说明:
1. 小型文本(导航、按钮等) -> zh.py / en.py (主文件)
2. 中型页面(Terms, Privacy等) -> terms_zh.py, terms_en.py (独立模块)
3. 大型文档(API Docs等) -> api_docs.html, api_docs_en.html (复制文件)
"""

import importlib
from flask import request, make_response
from config.config import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES


# 缓存已加载的语言模块
_loaded_locales = {}
_loaded_prompts = {}
_loaded_modules = {}  # 新增：缓存独立模块


def _load_locale(lang):
    """
    动态加载指定语言的翻译文件

    @param {str} lang - 语言代码
    @return {dict} - 翻译字典
    """
    if lang not in _loaded_locales:
        try:
            # 动态导入语言模块
            module = importlib.import_module(f'src.i18n.{lang}')
            _loaded_locales[lang] = module.TRANSLATIONS
        except ImportError:
            # 如果找不到指定语言,尝试加载默认语言
            if lang != DEFAULT_LANGUAGE:
                return _load_locale(DEFAULT_LANGUAGE)
            return {}

    return _loaded_locales[lang]


def _load_prompt(lang):
    """
    动态加载指定语言的 LLM 提示词文件

    @param {str} lang - 语言代码
    @return {dict} - 提示词字典
    """
    if lang not in _loaded_prompts:
        try:
            # 动态导入提示词模块
            module = importlib.import_module(f'src.i18n.{lang}')
            _loaded_prompts[lang] = module.LLM_PROMPTS
        except ImportError:
            # 如果找不到指定语言,尝试加载默认语言
            if lang != DEFAULT_LANGUAGE:
                return _load_prompt(DEFAULT_LANGUAGE)
            return {}

    return _loaded_prompts[lang]


def _load_module(module_name, lang):
    """
    动态加载独立的多语言模块（如 terms, privacy 等）

    @param {str} module_name - 模块名称 (如 'terms', 'privacy')
    @param {str} lang - 语言代码
    @return {dict} - 翻译字典
    """
    cache_key = f"{module_name}_{lang}"

    if cache_key not in _loaded_modules:
        try:
            # 尝试加载指定语言的模块 (如 terms_zh, terms_en)
            module = importlib.import_module(f'src.i18n.{module_name}_{lang}')
            # 获取模块中的翻译字典 (约定: {MODULE_NAME}_TRANSLATIONS)
            var_name = f"{module_name.upper()}_TRANSLATIONS"
            _loaded_modules[cache_key] = getattr(module, var_name, {})
        except ImportError:
            # 如果找不到指定语言，尝试加载默认语言
            if lang != DEFAULT_LANGUAGE:
                return _load_module(module_name, DEFAULT_LANGUAGE)
            _loaded_modules[cache_key] = {}

    return _loaded_modules[cache_key]


def get_language_from_request():
    """
    从请求中获取语言偏好

    优先级：
    1. Cookie 中的 language_preference
    2. 浏览器 Accept-Language 头部
    3. 配置的默认语言

    @return {str} - 语言代码 ('zh' 或 'en')
    """
    # 1. 检查 Cookie
    lang = request.cookies.get('language_preference')
    if lang and lang in SUPPORTED_LANGUAGES:
        return lang

    # 2. 检查浏览器 Accept-Language
    accept_lang = request.headers.get('Accept-Language', '')
    if accept_lang:
        accept_lang_lower = accept_lang.lower()
        # 如果明确指定英文且不包含中文，则使用英文
        if 'en' in accept_lang_lower and 'zh' not in accept_lang_lower:
            return 'en'
        # 如果包含中文，优先使用中文
        if 'zh' in accept_lang_lower:
            return 'zh'

    # 3. 返回默认语言
    return DEFAULT_LANGUAGE


def get_translation(key, lang=None):
    """
    获取翻译文本（支持命名空间）

    支持的格式:
    - 普通键: 'contact_email' -> 从主文件查找
    - 命名空间: 'terms.title' -> 从 terms 模块查找
    - 嵌套命名空间: 'api.overview.title' -> 未来可扩展

    @param {str} key - 翻译键 (可包含命名空间，如 'terms.title')
    @param {str} lang - 可选的语言代码,如果不提供则从请求中获取
    @return {str} - 翻译后的文本,如果找不到则返回键名本身
    """
    if lang is None:
        try:
            lang = get_language_from_request()
        except RuntimeError:
            # 如果没有请求上下文，使用默认语言
            lang = DEFAULT_LANGUAGE

    # 检查是否包含命名空间 (如 'terms.title')
    if '.' in key:
        parts = key.split('.', 1)
        module_name = parts[0]
        sub_key = parts[1] if len(parts) > 1 else key

        # 从独立模块加载
        module_translations = _load_module(module_name, lang)
        if module_translations:
            text = module_translations.get(sub_key)
            if text:
                return text

        # 如果找不到，尝试默认语言
        if lang != DEFAULT_LANGUAGE:
            default_module = _load_module(module_name, DEFAULT_LANGUAGE)
            text = default_module.get(sub_key)
            if text:
                return text

        # 还是找不到，返回键名
        return key

    # 普通键：从主语言文件查找
    translations = _load_locale(lang)
    if translations:
        text = translations.get(key)
        if text:
            return text

    # 如果找不到,尝试使用默认语言
    if lang != DEFAULT_LANGUAGE:
        default_translations = _load_locale(DEFAULT_LANGUAGE)
        text = default_translations.get(key)
        if text:
            return text

    # 如果还是找不到,返回键名本身
    return key


def get_llm_prompt(prompt_type, lang=None):
    """
    获取指定语言的 LLM 提示词

    @param {str} prompt_type - 提示词类型(如 'format_system', 'title_user' 等)
    @param {str} lang - 可选的语言代码,如果不提供则从请求中获取
    @return {str} - 提示词文本
    """
    if lang is None:
        lang = get_language_from_request()

    # 加载指定语言的提示词
    prompts = _load_prompt(lang)
    if prompts:
        prompt = prompts.get(prompt_type)
        if prompt:
            return prompt

    # 如果找不到,尝试使用默认语言
    if lang != DEFAULT_LANGUAGE:
        default_prompts = _load_prompt(DEFAULT_LANGUAGE)
        prompt = default_prompts.get(prompt_type)
        if prompt:
            return prompt

    # 如果还是找不到,返回空字符串
    return ''


def create_language_response(response, lang):
    """
    为响应设置语言 Cookie

    @param {Response} response - Flask 响应对象
    @param {str} lang - 语言代码
    @return {Response} - 设置了 Cookie 的响应对象
    """
    resp = make_response(response)
    # 设置 Cookie，过期时间 365 天
    resp.set_cookie('language_preference', lang, max_age=365*24*3600, path='/')
    return resp


def get_all_translations(lang=None):
    """
    获取指定语言的所有翻译(用于前端 JavaScript)

    @param {str} lang - 可选的语言代码
    @return {dict} - 翻译字典
    """
    if lang is None:
        lang = get_language_from_request()

    return _load_locale(lang)
