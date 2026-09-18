#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
应用入口文件：启动Web服务器，提供API接口
"""

import os
import sys
from dotenv import load_dotenv

# 🔴 加载 .env 配置文件（必须在读取环境变量之前）
load_dotenv()

from src.web_server import run_server
from src.logger import logger

def main():
    """
    主函数：应用程序入口点
    @returns {int} - 返回状态码，0表示成功，1表示失败
    """
    try:
        # 🔴 检查是否使用 Gunicorn 启动
        if 'gunicorn' in os.environ.get('SERVER_SOFTWARE', ''):
            logger.info("检测到 Gunicorn 环境，跳过 app.run()")
            return 0

        print("调试：进入 main 函数")  # 添加调试打印
        # 本地默认使用 5058；部署时可通过 PORT 覆盖
        port = int(os.environ.get('PORT', 5058))
        host = os.environ.get('HOST', '0.0.0.0')

        logger.info("启动 AI Teacher 服务")
        run_server(host=host, port=port)
        return 0
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
