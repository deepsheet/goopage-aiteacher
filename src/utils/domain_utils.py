#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
域名工具模块
提供统一的域名获取和管理功能
"""

from flask import request, has_request_context
from config.config import MAIN_DOMAIN


def get_current_base_url():
    """
    获取当前请求的基础URL（协议 + 域名 + 端口）

    @return {str} - 例如: https://example.com 或 http://127.0.0.1:5058
                     如果不在请求上下文中，返回配置的主域名
    """
    if has_request_context():
        protocol = request.scheme  # http 或 https
        host = request.host  # 例如：localhost:8080 或 www.example.com
        return f"{protocol}://{host}"
    else:
        # 不在请求上下文中时，使用配置的主域名
        return MAIN_DOMAIN


def get_current_domain():
    """
    获取当前请求的域名（不包含协议）

    @return {str} - 例如: example.com 或 127.0.0.1:5058
                     如果不在请求上下文中，返回主域名的host部分
    """
    if has_request_context():
        return request.host
    else:
        # 从主域名中提取host部分
        from urllib.parse import urlparse
        parsed = urlparse(MAIN_DOMAIN)
        return parsed.netloc or MAIN_DOMAIN


def generate_share_image_url(article_id):
    """
    生成分享图片URL

    @param {str} article_id - 文章ID
    @return {str} - 完整的分享图片URL
    """
    base_url = get_current_base_url()
    return f"{base_url}/api/share/cover/{article_id}"


def generate_article_url(article_id):
    """
    生成文章URL

    @param {str} article_id - 文章ID
    @return {str} - 完整的文章URL
    """
    base_url = get_current_base_url()
    return f"{base_url}/p/{article_id}"


def generate_favicon_url():
    """
    生成favicon URL

    @return {str} - 完整的favicon URL
    """
    base_url = get_current_base_url()
    return f"{base_url}/favicon.ico"
