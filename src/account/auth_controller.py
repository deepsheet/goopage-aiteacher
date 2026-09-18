#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
认证控制器
处理登录、注册、登出等业务逻辑
"""

from flask import request, jsonify, session, current_app
from src.i18n import get_language_from_request, get_translation
from src.account.models import create_user, verify_login, get_user_by_id
from src.logger import logger


def handle_register():
    """
    处理用户注册请求

    @return {tuple} - (response, status_code)
    """
    lang = get_language_from_request()

    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': get_translation('error_invalid_request', lang)
            }), 400

        account = data.get('email', '').strip()  # 邮箱或手机号
        username = data.get('username', '').strip()
        password = data.get('password', '')

        # 验证必填字段
        if not all([account, username]):
            return jsonify({
                'status': 'error',
                'message': get_translation('error_account_required', lang)
            }), 400

        # 获取当前域名
        server = request.host

        # 创建用户
        result = create_user(
            username=username,
            email=account,  # 存储到email字段
            password=password,
            registsrc='aiteacher',
            server=server
        )

        if result['status'] == 'success':
            return jsonify({
                'status': 'success',
                'message': get_translation('success_register', lang),
                'user_id': result.get('user_id')
            }), 200
        else:
            # 翻译错误消息
            error_msg = result['message']
            if error_msg == 'email_exists':
                error_msg = get_translation('error_email_exists', lang)
            elif error_msg == 'username_exists':
                error_msg = get_translation('error_username_exists', lang)

            return jsonify({
                'status': 'error',
                'message': error_msg
            }), 400

    except Exception as e:
        logger.error(f"注册处理异常：{str(e)}")
        return jsonify({
            'status': 'error',
            'message': get_translation('error_register_failed', lang)
        }), 500


def handle_login():
    """
    处理用户登录请求

    @return {tuple} - (response, status_code)
    """
    lang = get_language_from_request()

    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': get_translation('error_invalid_request', lang)
            }), 400

        account = data.get('username', '').strip()  # 可以是用户名或邮箱
        password = data.get('password', '')

        if not account:
            return jsonify({
                'status': 'error',
                'message': get_translation('error_account_required', lang)
            }), 400

        # 验证登录
        result = verify_login(account=account, password=password)

        if result['status'] == 'success':
            user_info = result['user']

            # 保存用户信息到 session
            session['user_id'] = user_info['id']
            session['username'] = user_info['username']
            session['email'] = user_info['email']
            session['is_logged_in'] = True
            # 🔴 强制标记 session 已修改，确保 Flask 发送 Set-Cookie
            session.modified = True

            logger.info(f"用户登录成功，session已设置：{user_info['username']}")

            return jsonify({
                'status': 'success',
                'message': get_translation('success_login', lang),
                'user': {
                    'id': user_info['id'],
                    'username': user_info['username'],
                    'email': user_info['email']
                }
            }), 200
        else:
            # 翻译错误消息
            error_msg = result['message']
            if error_msg == 'account_not_found':
                error_msg = get_translation('error_account_not_found', lang)
            elif error_msg == 'wrong_password':
                error_msg = get_translation('error_wrong_password', lang)

            return jsonify({
                'status': 'error',
                'message': error_msg
            }), 401

    except Exception as e:
        logger.error(f"登录处理异常：{str(e)}")
        return jsonify({
            'status': 'error',
            'message': get_translation('error_login_failed', lang)
        }), 500


def handle_logout():
    """
    处理用户登出请求

    @return {tuple} - (response, status_code)
    """
    lang = get_language_from_request()

    try:
        username = session.get('username', '未知用户')

        session['is_logged_in'] = False
        session.pop('user_id', None)
        session.pop('username', None)
        session.pop('email', None)

        logger.info(f"用户登出：{username}")

        response = jsonify({
            'status': 'success',
            'message': get_translation('success_logout', lang)
        })
        # 🔴 同时删除浏览器中的 session cookie（双保险）
        response.delete_cookie('session', path='/')
        # 强制禁用缓存，避免浏览器使用缓存的登录状态
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

        return response, 200

    except Exception as e:
        logger.error(f"登出处理异常：{str(e)}")
        return jsonify({
            'status': 'error',
            'message': get_translation('error_logout_failed', lang)
        }), 500


def handle_logout_as_redirect(redirect_url):
    """
    页面跳转模式登出：清空 session 并重定向
    不手动删 key/cookie，让 Flask-Session 自动处理

    @param {str} redirect_url - 登出后跳转的 URL
    @return {Response} - 重定向响应
    """
    try:
        username = session.get('username', '未知用户')

        # 清空用户信息，保留 session 结构避免触发 save_session 的空 session 分支
        session['is_logged_in'] = False
        session.pop('user_id', None)
        session.pop('username', None)
        session.pop('email', None)

        logger.info(f"用户登出（跳转模式）：{username} -> {redirect_url}")

        from flask import redirect
        response = redirect(redirect_url)

        # 强制禁用缓存
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

        return response

    except Exception as e:
        logger.error(f"登出跳转处理异常：{str(e)}")
        from flask import redirect
        return redirect('/')


def handle_check_login():
    """
    检查用户登录状态

    @return {tuple} - (response, status_code)
    """
    try:
        is_logged_in = session.get('is_logged_in', False)

        if is_logged_in:
            user_info = {
                'id': session.get('user_id'),
                'username': session.get('username'),
                'email': session.get('email')
            }
        else:
            user_info = None

        response = jsonify({
            'status': 'success',
            'isLoggedIn': is_logged_in,
            'user': user_info
        })
        # 禁止缓存登录状态检查结果
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        return response, 200

    except Exception as e:
        logger.error(f"检查登录状态异常：{str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


def handle_get_user_profile():
    """
    获取用户详细信息

    @return {tuple} - (response, status_code)
    """
    lang = get_language_from_request()

    try:
        # 检查是否登录
        if not session.get('is_logged_in', False):
            return jsonify({
                'status': 'error',
                'message': get_translation('error_not_logged_in', lang)
            }), 401

        user_id = session.get('user_id')
        username = session.get('username')
        email = session.get('email')

        # 获取用户详细信息
        from src.account.models import get_user_by_id
        user_detail = get_user_by_id(user_id)

        if not user_detail:
            return jsonify({
                'status': 'error',
                'message': get_translation('error_user_not_found', lang)
            }), 404

        # 构建响应数据
        profile_data = {
            'user_id': user_id,
            'username': username,
            'email': email,
            'register_time': user_detail.get('SYS_ADDTIME', '').strftime('%Y-%m-%d %H:%M:%S') if user_detail.get('SYS_ADDTIME') else '',
        }

        return jsonify({
            'status': 'success',
            'data': profile_data
        }), 200

    except Exception as e:
        logger.error(f"获取用户详细信息异常：{str(e)}")
        return jsonify({
            'status': 'error',
            'message': get_translation('error_get_profile_failed', lang)
        }), 500


def handle_set_password():
    """
    处理设置密码请求

    @return {tuple} - (response, status_code)
    """
    lang = get_language_from_request()

    try:
        # 检查是否登录
        if not session.get('is_logged_in', False):
            return jsonify({
                'status': 'error',
                'message': get_translation('error_not_logged_in', lang)
            }), 401

        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': get_translation('error_invalid_request', lang)
            }), 400

        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')

        if not new_password:
            return jsonify({
                'status': 'error',
                'message': '请输入新密码'
            }), 400

        if len(new_password) < 1:
            return jsonify({
                'status': 'error',
                'message': '密码长度至少1位'
            }), 400

        if len(new_password) > 200:
            return jsonify({
                'status': 'error',
                'message': '密码长度不能超过200个字符'
            }), 400

        user_id = session.get('user_id')

        # 获取用户信息
        from src.account.models import get_user_by_id, hash_password
        user_detail = get_user_by_id(user_id)

        if not user_detail:
            return jsonify({
                'status': 'error',
                'message': get_translation('error_user_not_found', lang)
            }), 404

        # 如果用户已有密码，验证原密码
        current_password = user_detail.get('psw', '')
        logger.info(f"设置密码 - 用户ID: {user_id}, 当前密码哈希: {current_password[:20] if current_password else '(空)'}, 提供的原密码: {'***' if old_password else '(空)'}")

        if current_password and old_password:
            # 验证原密码
            input_password_hash = hash_password(old_password)
            logger.info(f"设置密码 - 输入密码哈希: {input_password_hash[:20]}, 匹配: {input_password_hash == current_password}")

            if input_password_hash != current_password:
                logger.warning(f"设置密码失败 - 原密码错误, 用户ID: {user_id}")
                return jsonify({
                    'status': 'error',
                    'message': '原密码错误'
                }), 400
            else:
                logger.info(f"设置密码 - 原密码验证通过, 用户ID: {user_id}")
        elif current_password and not old_password:
            # 已有密码但未提供原密码
            logger.warning(f"设置密码失败 - 未提供原密码, 用户ID: {user_id}")
            return jsonify({
                'status': 'error',
                'message': '请输入原密码'
            }), 400
        elif not current_password:
            # 首次设置密码，无需验证原密码
            logger.info(f"设置密码 - 首次设置密码，跳过原密码验证, 用户ID: {user_id}")

        # 更新密码
        from src.db_manager import DatabaseManager
        db = DatabaseManager()
        try:
            db.connect()
            new_password_hash = hash_password(new_password)
            sql = "UPDATE sys_user SET psw = %s WHERE id = %s"
            db.cursor.execute(sql, (new_password_hash, user_id))
            db.conn.commit()

            logger.info(f"用户 {user_id} 密码更新成功")

            return jsonify({
                'status': 'success',
                'message': '密码设置成功'
            }), 200
        except Exception as e:
            db.conn.rollback()
            logger.error(f"更新密码失败: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': '密码设置失败，请重试'
            }), 500
        finally:
            db.disconnect()

    except Exception as e:
        logger.error(f"设置密码异常：{str(e)}")
        return jsonify({
            'status': 'error',
            'message': '系统错误，请重试'
        }), 500


def require_login(f):
    """
    登录装饰器：要求用户必须登录才能访问

    @param {function} f - 被装饰的函数
    @return {function} - 装饰后的函数
    """
    from functools import wraps
    from flask import redirect, url_for

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_logged_in', False):
            # 未登录，重定向到登录页面
            return redirect(url_for('account.login_page'))
        return f(*args, **kwargs)

    return decorated_function
