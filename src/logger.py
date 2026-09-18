#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
日志模块：负责记录程序运行过程中的各种信息
"""

import os
import logging
from datetime import datetime
import sys

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.config import LOG_DIR

class Logger:
    """
    日志记录器类
    """
    def __init__(self):
        """
        初始化日志记录器
        """
        # 确保日志目录存在
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)

        # 获取今天的日期作为文件名
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = os.path.join(LOG_DIR, f"{today}.log")

        # 配置日志格式
        self.logger = logging.getLogger("aiteacher")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        # 文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 设置日志格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # 添加处理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def info(self, message, *args, **kwargs):
        """
        记录信息日志

        @param {str} message - 要记录的信息
        """
        self.logger.info(message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        """
        记录错误日志

        @param {str} message - 要记录的错误信息
        """
        self.logger.error(message, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        """
        记录警告日志

        @param {str} message - 要记录的警告信息
        """
        self.logger.warning(message, *args, **kwargs)

    def debug(self, message, *args, **kwargs):
        """
        记录调试日志

        @param {str} message - 要记录的调试信息
        """
        self.logger.debug(message, *args, **kwargs)

# 创建一个全局的日志实例
logger = Logger()
