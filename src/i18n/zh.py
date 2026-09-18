#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
中文语言配置文件 - 包含翻译文本和 LLM 提示词

框架精简版：仅保留通用条目与账户模块所需条目，
新项目按需在此扩展（架构见 __init__.py 文档说明）。
"""

# ==================== UI 翻译文本 ====================
TRANSLATIONS = {
    # 通用/品牌
    'page_title': 'AI老师 · AI 陪练课堂',
    'brand_name': 'AI老师',
    'brand_slogan': '一起学，会更容易',
    'logo_alt': '网站图标',
    'back_to_home': '← 回首页',

    # ==================== 账户模块翻译 ====================
    # 页面标题
    'login_title': '登录',
    'register_title': '注册',

    # 表单标签
    'login': '登录',
    'register': '注册',
    'logout': '登出',
    'username': '用户名',
    'email': '邮箱/手机号',
    'password': '密码',
    'confirm_password': '确认密码',
    'username_or_email': '用户名或邮箱',

    # 占位符
    'enter_username_or_email': '请输入用户名或邮箱',
    'enter_password': '请输入密码',
    'enter_email': '请输入邮箱或手机号',
    'choose_username': '请设置用户名',
    'create_password': '请设置密码',
    'confirm_password_placeholder': '请再次输入密码',

    # 选项
    'remember_account': '记住账号',
    'optional': '可选',

    # 提示文本
    'no_account': '还没有账号？',
    'has_account': '已有账号？',

    # 按钮状态
    'logging_in': '登录中...',
    'registering': '注册中...',
    'btn_cancel': '取消',
    'btn_confirm': '确认',

    # 错误消息
    'error_account_required': '请输入用户名或邮箱',
    'error_password_required': '请输入密码',
    'error_email_required': '请输入邮箱或手机号',
    'error_username_required': '请输入用户名',
    'error_invalid_email': '邮箱或手机号格式不正确',
    'error_password_mismatch': '两次输入的密码不一致',
    'error_email_exists': '该邮箱或手机号已被注册',
    'error_username_exists': '该用户名已被使用',
    'error_account_not_found': '账号不存在',
    'error_wrong_password': '密码错误',
    'error_login_failed': '登录失败，请稍后重试',
    'error_register_failed': '注册失败，请稍后重试',
    'error_logout_failed': '登出失败',
    'error_network': '网络错误，请检查网络连接',
    'error_invalid_request': '无效的请求',
    'error_user_not_found': '用户不存在',
    'error_not_logged_in': '未登录',
    'error_get_profile_failed': '获取用户信息失败',

    # 成功消息
    'success_login': '登录成功',
    'success_register': '注册成功',
    'success_logout': '已登出',

    # 确认对话框
    'confirm_logout': '确定要登出吗？',
    'confirm_logout_title': '确认登出',
    'confirm_logout_message': '您确定要退出登录吗？',
    'btn_confirm_logout': '确认登出',

    # 错误页面
    'error_page_not_found_title': '页面不存在',
    'error_page_not_found_message': '页面不存在，或者生成时中断了。<br>请检查链接是否正确，或重新生成。',
}

# ==================== LLM 提示词（架构示例） ====================
LLM_PROMPTS = {
    'title_system': "你是一位专业的编辑,擅长为文章提炼精准、吸引人的标题。请根据用户提供的文章内容,生成一个简洁明了的标题。要求:1.只输出标题,不要其他说明;2.标题长度控制在 30 字以内;3.能够准确概括文章核心内容。",
    'title_user': "请为以下文章生成一个标题:\n\n{content}",
}
