#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ID 生成工具模块
提供文章 ID 生成和智能文件名生成功能
"""

import random
import string
import re
import time
from src.logger import logger


def generate_random_id(length=16):
    """
    生成指定长度的随机字符串ID（字母+数字）

    @param {int} length - ID长度
    @return {str} - 随机ID
    """
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def generate_article_id(length=8):
    """
    生成 8 位随机小写字母的文章 ID

    @return {str} - 文章 ID
    """
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))


def generate_smart_filename(title, article_id=None):
    """
    根据文章标题生成智能文件名
    规则：
    1. 只保留英文字母、数字和汉字
    2. 去除所有空格和特殊字符
    3. 限制长度，避免过长
    4. 如果有 article_id，格式为：文件ID_中文标题.html

    @param {str} title - 文章标题
    @param {str} article_id - 文章 ID（可选）
    @return {str} - 智能文件名（包含 .html 扩展名）
    """
    logger.info(f"原始标题：{title}")

    # 如果标题为空或只有空格，使用默认名称
    if not title or not title.strip():
        logger.warning("标题为空，使用默认名称")
        title = 'untitled'

    # 只保留英文字母、数字和汉字，去除所有其他字符（包括空格）
    # 允许的字符：字母 (a-zA-Z)、数字 (0-9)、汉字 (\u4e00-\u9fff)
    cleaned_title = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]', '', title)

    logger.info(f"清理后标题：{cleaned_title}")

    # 如果清理后为空，使用默认名称
    if not cleaned_title:
        logger.warning("清理后标题为空，使用默认名称")
        cleaned_title = 'untitled'

    # 限制长度（最多 50 个字符，避免文件名过长）
    if len(cleaned_title) > 50:
        cleaned_title = cleaned_title[:50]
        logger.info(f"截断后标题：{cleaned_title}")

    # 生成文件名
    if article_id:
        # 新格式：文件ID_中文标题.html
        filename = f"{article_id}_{cleaned_title}.html"
    else:
        # 旧格式：标题_时间戳.html（向后兼容）
        timestamp = int(time.time())
        filename = f"{cleaned_title}_{timestamp}.html"

    logger.info(f"生成智能文件名：{filename}")
    return filename
