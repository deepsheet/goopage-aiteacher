"""
File Text Extractor Service

从各种文件格式中提取文本内容。
支持：图片(OCR)、PDF、Word、Excel、纯文本等格式。

基于 anytotable/server/analyzefile.py 移植
"""

import os
import logging
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import pytesseract
import cv2
import numpy as np
from pdfminer.high_level import extract_text as extract_pdf_text
from docx import Document
import openpyxl

logger = logging.getLogger(__name__)


def _clean_extracted_text(text):
    """
    清理提取的文本：去除多余空行，保留最多连续2个空行
    """
    lines = text.split('\n')
    cleaned = []
    empty_count = 0
    for line in lines:
        if line.strip() == '':
            empty_count += 1
            if empty_count <= 2:
                cleaned.append(line)
        else:
            empty_count = 0
            cleaned.append(line)
    return '\n'.join(cleaned).strip()


def recognize_text_with_tesseract(image_data):
    """
    使用 Tesseract OCR 识别图片中的文字

    @param image_data: 图片的二进制数据
    @return: 识别出的文字
    """
    try:
        # 将二进制数据转换为numpy数组
        nparr = np.frombuffer(image_data, np.uint8)
        # 将numpy数组解码为图像
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # 图像预处理
        # 1. 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # 2. 降噪
        denoised = cv2.fastNlMeansDenoising(gray)
        # 3. 二值化
        _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 使用Tesseract进行OCR识别
        # 设置识别语言为中文和英文
        text = pytesseract.image_to_string(binary, lang='chi_sim+eng')

        return text.strip()

    except Exception as e:
        logger.error(f"Tesseract OCR 识别失败: {str(e)}")
        logger.error(f"错误详情: {e.__class__.__name__}")
        return ""


def extract_text_from_single_file(file_path):
    """
    从单个文件中提取文本内容

    @param file_path: 文件路径
    @return: 提取的文本内容
    """
    if not os.path.exists(file_path):
        logger.warning(f"文件不存在: {file_path}")
        return ""

    # 支持的文件扩展名
    supported_extensions = {
        # 图片
        '.jpg', '.jpeg', '.png', '.bmp', '.gif',
        # 文档
        '.pdf', '.doc', '.docx', '.txt', '.html', '.htm',
        # 表格
        '.xls', '.xlsx', '.csv'
    }

    try:
        # 检查文件扩展名
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in supported_extensions:
            logger.warning(f"不支持的文件类型: {file_ext}")
            return ""

        text = ""
        if file_ext in {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}:
            # 处理图片文件
            with open(file_path, 'rb') as f:
                image_data = f.read()
            text = recognize_text_with_tesseract(image_data)
        elif file_ext == '.pdf':
            # 处理PDF文件
            text = extract_pdf_text(file_path)
        elif file_ext in {'.doc', '.docx'}:
            # 处理Word文件
            doc = Document(file_path)
            text = '\n'.join([para.text for para in doc.paragraphs])
        elif file_ext == '.txt':
            # 处理文本文件
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        elif file_ext in {'.xls', '.xlsx', '.csv'}:
            # 处理Excel文件
            wb = openpyxl.load_workbook(file_path)
            text = ""
            for sheet in wb:
                for row in sheet.iter_rows(values_only=True):
                    text += '\t'.join([str(cell) if cell is not None else '' for cell in row]) + '\n'
        elif file_ext in {'.html', '.htm'}:
            # 处理HTML文件：正则提取纯文本
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                html_content = f.read()
            # 先提取<body>标签内的内容
            body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.IGNORECASE | re.DOTALL)
            body_content = body_match.group(1) if body_match else html_content
            # 移除script和style标签及其内容
            text = re.sub(r'<script[^>]*>.*?</script>', '', body_content, flags=re.IGNORECASE | re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.IGNORECASE | re.DOTALL)
            # 在块级标签前后添加换行，使纯文本保留段落结构
            text = re.sub(r'<br[^>]*>', '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'</?(?:p|div|h[1-6]|li|tr|td|th|blockquote|section|article|header|footer|nav|table|ul|ol|dl|dt|dd|pre|figure|figcaption|details|summary|hr)[^>]*>', '\n', text, flags=re.IGNORECASE)
            # 移除所有HTML标签
            text = re.sub(r'<[^>]+>', '', text)
            # 解码常见HTML实体
            text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            text = text.replace('&nbsp;', ' ').replace('&quot;', '"')
            # 清理多余空行
            text = _clean_extracted_text(text)

        return text.strip()

    except Exception as e:
        logger.error(f"处理文件 {file_path} 时出错: {str(e)}")
        return ""


def get_uploadfile_text(uploadfile_session_id, base_folder='temp'):
    """
    获取上传文件的文本内容（批量提取）

    @param uploadfile_session_id: 上传文件的会话ID
    @param base_folder: 基础文件夹路径
    @return: 上传文件的文本内容
    """
    if not uploadfile_session_id:
        return ""

    # 获取会话文件夹路径
    session_folder = os.path.join(base_folder, uploadfile_session_id)
    if not os.path.exists(session_folder):
        logger.warning(f"会话文件夹不存在: {session_folder}")
        return ""

    # 支持的文件扩展名
    supported_extensions = {
        # 图片
        '.jpg', '.jpeg', '.png', '.bmp', '.gif',
        # 文档
        '.pdf', '.doc', '.docx', '.txt', '.html', '.htm',
        # 表格
        '.xls', '.xlsx', '.csv'
    }

    # 存储所有文件的文本内容
    all_texts = ["以下是从几个文件中读取的文本:"]

    # 遍历会话文件夹中的所有文件
    for filename in os.listdir(session_folder):
        file_path = os.path.join(session_folder, filename)
        if not os.path.isfile(file_path):
            continue

        # 检查文件扩展名
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in supported_extensions:
            continue

        try:
            text = ""
            if file_ext in {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}:
                # 处理图片文件
                with open(file_path, 'rb') as f:
                    image_data = f.read()
                text = recognize_text_with_tesseract(image_data)
            elif file_ext == '.pdf':
                # 处理PDF文件
                text = extract_pdf_text(file_path)
            elif file_ext in {'.doc', '.docx'}:
                # 处理Word文件
                doc = Document(file_path)
                text = '\n'.join([para.text for para in doc.paragraphs])
            elif file_ext == '.txt':
                # 处理文本文件
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            elif file_ext in {'.xls', '.xlsx', '.csv'}:
                # 处理Excel文件
                wb = openpyxl.load_workbook(file_path)
                text = ""
                for sheet in wb:
                    for row in sheet.iter_rows(values_only=True):
                        text += '\t'.join([str(cell) if cell is not None else '' for cell in row]) + '\n'
            elif file_ext in {'.html', '.htm'}:
                # 处理HTML文件：正则提取纯文本
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    html_content = f.read()
                # 先提取<body>标签内的内容
                body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.IGNORECASE | re.DOTALL)
                body_content = body_match.group(1) if body_match else html_content
                # 移除script和style标签及其内容
                text = re.sub(r'<script[^>]*>.*?</script>', '', body_content, flags=re.IGNORECASE | re.DOTALL)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.IGNORECASE | re.DOTALL)
                # 在块级标签前后添加换行，使纯文本保留段落结构
                text = re.sub(r'<br[^>]*>', '\n', text, flags=re.IGNORECASE)
                text = re.sub(r'</?(?:p|div|h[1-6]|li|tr|td|th|blockquote|section|article|header|footer|nav|table|ul|ol|dl|dt|dd|pre|figure|figcaption|details|summary|hr)[^>]*>', '\n', text, flags=re.IGNORECASE)
                # 移除所有HTML标签
                text = re.sub(r'<[^>]+>', '', text)
                # 解码常见HTML实体
                text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                text = text.replace('&nbsp;', ' ').replace('&quot;', '"')
                # 清理多余空行
                text = _clean_extracted_text(text)

            if text:
                all_texts.append(f"从文件({filename})读取的文本:{text}")

        except Exception as e:
            logger.error(f"处理文件 {filename} 时出错: {str(e)}")
            continue

    # 将所有文本内容合并
    return "\n\n".join(all_texts)
