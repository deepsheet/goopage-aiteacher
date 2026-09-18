#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
用户模型模块
提供用户相关的数据库操作
"""

import sys
import os
import random
import string
import hashlib
from datetime import datetime

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pymysql
from config.config import DB_CONFIG
from src.logger import logger


def get_connection():
    """
    获取数据库连接

    @return {pymysql.Connection} - 数据库连接对象
    """
    return pymysql.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database'],
        charset=DB_CONFIG['charset']
    )


def generate_user_id(length=8):
    """
    生成指定长度的随机用户ID

    @param {int} length - ID长度
    @return {str} - 随机ID
    """
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def hash_password(password):
    """
    密码加密（MD5）

    @param {str} password - 明文密码
    @return {str} - MD5加密后的密码
    """
    if not password:
        return ''
    return hashlib.md5(password.encode('utf-8')).hexdigest()


def create_user(username, email, password='', registsrc='aiteacher', server='localhost'):
    """
    创建新用户

    @param {str} username - 用户名
    @param {str} email - 邮箱
    @param {str} password - 密码（可选）
    @param {str} registsrc - 注册来源（默认：aiteacher）
    @param {str} server - 服务器域名
    @return {dict} - 包含 status 和 message 的结果
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # 检查邮箱是否已存在
            cursor.execute('SELECT 1 FROM sys_user WHERE email = %s', (email,))
            if cursor.fetchone():
                return {'status': 'error', 'message': 'email_exists'}

            # 检查用户名是否已存在
            cursor.execute('SELECT 1 FROM sys_user WHERE name = %s', (username,))
            if cursor.fetchone():
                return {'status': 'error', 'message': 'username_exists'}

            # 生成用户ID和当前时间
            user_id = generate_user_id()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 插入新用户到 sys_user
            cursor.execute('''
                INSERT INTO sys_user
                (id, name, psw, email, registsrc, server, SYS_ADDUSER, SYS_ADDTIME)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (user_id, username, hash_password(password), email, registsrc, server, 'system', now))

        conn.commit()
        logger.info(f"用户注册成功：{username} ({email})")
        return {'status': 'success', 'message': 'register_success', 'user_id': user_id}

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"用户注册失败：{str(e)}")
        return {'status': 'error', 'message': f'register_failed: {str(e)}'}
    finally:
        if conn:
            conn.close()


def verify_login(account, password=''):
    """
    验证用户登录

    @param {str} account - 用户名或邮箱
    @param {str} password - 密码（可选，用于社交登录）
    @return {dict} - 包含 status 和用户信息的结果
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 查询用户（支持用户名或邮箱登录）
            query = '''
                SELECT id, name, email, psw
                FROM sys_user
                WHERE (name = %s OR email = %s)
            '''
            cursor.execute(query, (account, account))
            user = cursor.fetchone()

            if not user:
                return {'status': 'error', 'message': 'account_not_found'}

            # 检查用户是否设置了密码
            user_password = user.get('psw', '')

            # 如果用户已设置密码，必须验证
            if user_password:
                if not password:
                    # 用户有密码但未提供
                    return {'status': 'error', 'message': 'wrong_password'}

                # 验证密码
                cursor.execute('''
                    SELECT 1 FROM sys_user
                    WHERE id = %s AND psw = %s
                ''', (user['id'], hash_password(password)))

                if not cursor.fetchone():
                    return {'status': 'error', 'message': 'wrong_password'}
            # 如果用户未设置密码，允许免密登录（兼容老用户）

            # 更新最后登录时间
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                UPDATE sys_user
                SET lastlogintime = %s
                WHERE id = %s
            ''', (now, user['id']))

        conn.commit()
        logger.info(f"用户登录成功：{user['name']}")

        return {
            'status': 'success',
            'message': 'login_success',
            'user': {
                'id': user['id'],
                'username': user['name'],
                'email': user['email']
            }
        }

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"用户登录失败：{str(e)}")
        return {'status': 'error', 'message': f'login_failed: {str(e)}'}
    finally:
        if conn:
            conn.close()


def get_user_by_id(user_id):
    """
    根据用户ID获取用户信息

    @param {str} user_id - 用户ID
    @return {dict|None} - 用户信息字典，不存在则返回 None
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute('''
                SELECT id, name, email, psw, lastlogintime, SYS_ADDTIME
                FROM sys_user
                WHERE id = %s
            ''', (user_id,))
            user = cursor.fetchone()
            return user
    except Exception as e:
        logger.error(f"获取用户信息失败：{str(e)}")
        return None
    finally:
        if conn:
            conn.close()


def update_last_login(user_id):
    """
    更新用户最后登录时间

    @param {str} user_id - 用户ID
    @return {bool} - 是否更新成功
    """
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                UPDATE sys_user
                SET lastlogintime = %s
                WHERE id = %s
            ''', (now, user_id))
        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"更新最后登录时间失败：{str(e)}")
        return False
    finally:
        if conn:
            conn.close()
