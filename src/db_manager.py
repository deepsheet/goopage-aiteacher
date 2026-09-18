#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据库管理模块：负责与数据库的交互，执行SQL插入操作
"""

import sys
import os
import pymysql
import string
import random

# 添加项目根目录到系统路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.config import DB_CONFIG
from src.logger import logger

class DatabaseManager:
    """
    数据库管理类
    """
    def __init__(self):
        """
        初始化数据库连接
        """
        self.conn = None
        self.cursor = None

    def connect(self):
        """
        建立数据库连接

        @return {bool} - 连接是否成功
        """
        try:
            self.conn = pymysql.connect(
                host=DB_CONFIG["host"],
                port=DB_CONFIG["port"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                database=DB_CONFIG["database"],
                charset=DB_CONFIG["charset"]
            )
            self.cursor = self.conn.cursor()
            logger.info("数据库连接成功")
            return True
        except Exception as e:
            logger.error(f"数据库连接失败: {str(e)}")
            return False

    def disconnect(self):
        """
        关闭数据库连接
        """
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("数据库连接已关闭")

    def _generate_random_id(self, length):
        """
        生成指定长度的随机字符串

        @param {int} length - 字符串长度
        @return {str} - 随机字符串
        """
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for _ in range(length))