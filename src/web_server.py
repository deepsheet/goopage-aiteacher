#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Web服务器主入口模块
负责 Flask 应用初始化、配置和路由注册

框架说明：
- Redis Session 会话管理
- CORS 跨域配置
- 业务模块以 Blueprint 方式在此注册
"""

import sys
import os
import secrets
import redis

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, jsonify, render_template, send_from_directory
from flask_cors import CORS
from flask_session import Session
from src.logger import logger
from config.config import REDIS_CONFIG

# 创建 Flask 应用
app = Flask(__name__, static_folder='static', template_folder='templates')

# 配置 Session（必须设置 SECRET_KEY）
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    _secret_key = secrets.token_hex(32)
    logger.warning("⚠️ 未设置 SECRET_KEY 环境变量，已生成临时随机密钥（重启后失效）")
app.secret_key = _secret_key

app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 7  # 7 天过期
app.config['SESSION_KEY_PREFIX'] = 'aiteacher-session:'
_session_redis = redis.Redis(
    host=REDIS_CONFIG['host'],
    port=REDIS_CONFIG['port'],
    password=REDIS_CONFIG['password'],
    socket_timeout=0.3,
    socket_connect_timeout=0.3,
)
try:
    _session_redis.ping()
except redis.RedisError as exc:
    # 首页和体验课程不依赖 Redis。未安装/未启动 Redis 时回退到
    # Flask 的签名 Cookie Session，让新贡献者可以零基础设施启动。
    logger.warning("Redis 不可用，使用 Cookie Session：%s", exc)
else:
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_REDIS'] = _session_redis
    Session(app)
    logger.info("Redis Session 已初始化")

# 🔴 开发模式配置：禁用模板和静态文件缓存
if os.environ.get('FLASK_ENV') == 'development':
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.config['STATIC_CACHE_TIMEOUT'] = 0

# 配置 CORS
CORS(app, resources={r"/api/*": {"origins": "*", "allow_headers": "*"}})

# ============================================================
# Blueprint 注册区（业务模块在此注册）
# ============================================================

# 🔴 注册账户模块 Blueprint
from src.account import account_bp
app.register_blueprint(account_bp, url_prefix='/account')
logger.info("账户模块已初始化")

# 注册 AI 教师核心子应用。保留 /aiteacher 前缀，方便未来并列更多子产品。
from src.apps.aiteacher import aiteacher_bp
from src.apps.aiteacher.course import DEMO_COURSE
app.register_blueprint(aiteacher_bp, url_prefix='/aiteacher')
logger.info("AI 教师模块已初始化")

# ============================================================
# 通用路由
# ============================================================

@app.route('/')
def index():
    """项目首页：直接进入 AI 陪练课堂。"""
    return render_template('aiteacher/index.html', course=DEMO_COURSE)


@app.route('/health')
def health():
    """供启动脚本和部署平台探活，不依赖数据库或外部 AI。"""
    return jsonify({'app': 'aiteacher', 'status': 'ok'})


@app.route('/favicon.ico')
def favicon():
    """提供仓库根目录中的站点图标。"""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return send_from_directory(project_root, 'favicon.ico', mimetype='image/x-icon')


# ============================================================
# 安全响应头（通用安全头）
# ============================================================
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'no-referrer-when-downgrade'
    return response


# ============================================================
# 全局错误处理
# ============================================================
@app.errorhandler(404)
def not_found(error):
    return jsonify({'status': 'error', 'message': '页面不存在'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"服务器内部错误: {str(error)}")
    return jsonify({'status': 'error', 'message': '服务器内部错误'}), 500


def run_server(host='0.0.0.0', port=5058):
    """
    启动Web服务器

    @param {str} host - 主机地址
    @param {int} port - 端口号
    """
    logger.info(f"启动Web服务器，监听 {host}:{port}")
    # 本地开发环境启用调试模式和自动重载
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(host=host, port=port, debug=debug_mode, use_reloader=debug_mode)


if __name__ == "__main__":
    run_server()
