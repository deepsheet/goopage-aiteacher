#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
账户模块路由
定义登录、注册等页面的路由和API接口
"""

from flask import Blueprint, render_template, request, jsonify, session, send_from_directory, redirect
import os
from src.i18n import get_language_from_request, get_translation, create_language_response
from src.account.auth_controller import handle_register, handle_login, handle_logout, handle_logout_as_redirect, handle_check_login, handle_get_user_profile, handle_set_password
from src.logger import logger

# 创建 Blueprint，指定模板和静态文件目录
account_bp = Blueprint(
    'account',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/account/static'
)


# ==================== 页面路由 ====================

@account_bp.route('/login')
def login_page():
    """
    登录页面

    @return {Response} - HTML 页面
    """
    lang = get_language_from_request()
    logger.info(f"访问登录页面，语言：{lang}")

    # 如果已登录，重定向到首页
    if session.get('is_logged_in', False):
        return redirect('/')

    # 获取 redirect 参数（登录成功后跳转到该地址）
    redirect_url = request.args.get('redirect', '')

    response = render_template('login.html', lang=lang, t=lambda key: get_translation(key, lang), redirect_url=redirect_url)
    return create_language_response(response, lang)


@account_bp.route('/register')
def register_page():
    """
    注册页面

    @return {Response} - HTML 页面
    """
    lang = get_language_from_request()
    logger.info(f"访问注册页面，语言：{lang}")

    # 如果已登录，重定向到首页
    if session.get('is_logged_in', False):
        return redirect('/')

    response = render_template('register.html', lang=lang, t=lambda key: get_translation(key, lang))
    return create_language_response(response, lang)


# ==================== API 路由 ====================

@account_bp.route('/api/register', methods=['POST'])
def api_register():
    """
    用户注册 API

    @return {dict} - API 响应
    """
    return handle_register()


@account_bp.route('/api/login', methods=['POST'])
def api_login():
    """
    用户登录 API

    @return {dict} - API 响应
    """
    return handle_login()


@account_bp.route('/api/logout')
def api_logout():
    """
    用户登出 API

    @param {str} redirect - 可选，指定后以页面跳转方式登出（更可靠）
    @return {dict/Response} - JSON 响应或重定向
    """
    from flask import request
    from urllib.parse import urlparse
    redirect_url = request.args.get('redirect')
    if redirect_url:
        # 仅允许同站点或相对路径重定向（安全校验）
        parsed = urlparse(redirect_url)
        if parsed.netloc and parsed.netloc != request.host:
            redirect_url = '/'
        # 页面跳转模式：设置 cookie 后重定向（浏览器会正确处理 Set-Cookie）
        return handle_logout_as_redirect(redirect_url)
    # AJAX 模式：返回 JSON
    return handle_logout()


@account_bp.route('/api/check_login')
def api_check_login():
    """
    检查登录状态 API

    @return {dict} - API 响应
    """
    return handle_check_login()


@account_bp.route('/api/profile')
def api_get_user_profile():
    """
    获取用户详细信息 API

    @return {dict} - API 响应
    """
    return handle_get_user_profile()


@account_bp.route('/api/set_password', methods=['POST'])
def api_set_password():
    """
    设置密码 API

    @return {dict} - API 响应
    """
    return handle_set_password()


# ==================== 静态文件服务 ====================

@account_bp.route('/static/<path:filename>')
def serve_static(filename):
    """
    提供模块内的静态文件

    @param {str} filename - 文件名
    @return {Response} - 静态文件
    """
    static_folder = os.path.join(os.path.dirname(__file__), 'static')
    return send_from_directory(static_folder, filename)
