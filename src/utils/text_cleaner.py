#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文本清理工具模块
用于处理用户输入的各种复杂字符，确保能安全保存到数据库
"""

import re
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from src.logger import logger
except ImportError:
    # 如果无法导入logger，使用print代替
    class SimpleLogger:
        def info(self, msg): print(f"[INFO] {msg}")
        def warning(self, msg): print(f"[WARNING] {msg}")
        def error(self, msg): print(f"[ERROR] {msg}")
    logger = SimpleLogger()


def clean_user_text(text, max_length=None, enable_sql_protection=True, enable_html_protection=True):
    """
    清理用户输入的文本，确保能安全保存到数据库

    @param {str} text - 用户输入的原始文本
    @param {int} max_length - 最大长度限制（None表示不限制）
    @param {bool} enable_sql_protection - 是否启用SQL注入防护
    @param {bool} enable_html_protection - 是否启用HTML/CSS注入防护
    @return {dict} - 包含清理后的文本和处理信息
        {
            'cleaned_text': str,      # 清理后的文本
            'removed_chars': list,    # 被移除的字符列表
            'warnings': list,         # 警告信息列表
            'original_length': int,   # 原始长度
            'cleaned_length': int     # 清理后长度
        }
    """
    if not text:
        return {
            'cleaned_text': '',
            'removed_chars': [],
            'warnings': [],
            'original_length': 0,
            'cleaned_length': 0
        }

    removed_chars = []
    warnings = []
    original_length = len(text)

    # 1. 替换常见的控制字符（保留换行符和制表符）
    # 控制字符范围: U+0000-U+001F, U+007F (DEL)
    control_chars_pattern = r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]'
    matches = re.findall(control_chars_pattern, text)
    if matches:
        unique_matches = list(set(matches))
        removed_chars.extend([f'控制字符(0x{ord(c):02X})' for c in unique_matches[:5]])
        if len(unique_matches) > 5:
            removed_chars.append(f'...及其他{len(unique_matches)-5}个控制字符')
        warnings.append(f'移除了 {len(matches)} 个控制字符')
        text = re.sub(control_chars_pattern, '', text)

    # 2. 处理Unicode替代字符 (U+FFFD )
    replacement_char_count = text.count('\ufffd')
    if replacement_char_count > 0:
        removed_chars.append(f'替代字符() x {replacement_char_count}')
        warnings.append(f'移除了 {replacement_char_count} 个无效Unicode字符')
        text = text.replace('\ufffd', '')

    # 3. 处理零宽字符（可能被用于隐藏信息）
    zero_width_chars = [
        '\u200b',  # 零宽空格
        '\u200c',  # 零宽非连接符
        '\u200d',  # 零宽连接符
        '\ufeff',  # 零宽不换行空格
        '\u2060',  # 词连接符
        '\u2061',  # 函数应用
        '\u2062',  # 不可见乘号
        '\u2063',  # 不可见分隔符
    ]

    zw_removed = 0
    for char in zero_width_chars:
        count = text.count(char)
        if count > 0:
            zw_removed += count
            text = text.replace(char, '')

    if zw_removed > 0:
        removed_chars.append(f'零宽字符 x {zw_removed}')
        warnings.append(f'移除了 {zw_removed} 个零宽字符（可能用于隐藏信息）')

    # 4. 处理双向文本控制字符（可能导致显示混乱）
    bidi_chars = [
        '\u202a',  # LRE - 从左到右嵌入
        '\u202b',  # RLE - 从右到左嵌入
        '\u202c',  # PDF - 弹出方向格式化
        '\u202d',  # LRO - 从左到右覆盖
        '\u202e',  # RLO - 从右到左覆盖
        '\u2066',  # LRI - 从左到右隔离
        '\u2067',  # RLI - 从右到左隔离
        '\u2068',  # FSI - 第一强隔离
        '\u2069',  # PDI - 弹出方向隔离
    ]

    bidi_removed = 0
    for char in bidi_chars:
        count = text.count(char)
        if count > 0:
            bidi_removed += count
            text = text.replace(char, '')

    if bidi_removed > 0:
        removed_chars.append(f'双向控制字符 x {bidi_removed}')
        warnings.append(f'移除了 {bidi_removed} 个双向文本控制字符')

    # 5. 标准化换行符（统一为 \n）
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # 6. SQL注入防护
    if enable_sql_protection:
        # 检测常见的SQL注入模式
        sql_patterns = [
            (r"'\s*(OR|AND)\s+'[^']*'\s*=\s*'[^']*'", 'SQL OR注入'),
            (r"'\s*;\s*(DROP|DELETE|UPDATE|INSERT)\s", 'SQL命令注入'),
            (r"--\s*$", 'SQL注释注入'),
            (r"/\*.*\*/", 'SQL块注释注入'),
            (r"'\s*UNION\s+SELECT", 'SQL UNION注入'),
        ]

        sql_injection_found = []
        for pattern, desc in sql_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                sql_injection_found.append(desc)

        if sql_injection_found:
            warnings.append(f'⚠️ 检测到潜在的SQL注入模式: {", ".join(sql_injection_found)}')
            logger.warning(f"检测到SQL注入尝试: {sql_injection_found}")
            # ⚠️ 重要提示：
            # 这里的检测只是辅助手段，真正的SQL注入防护应该使用参数化查询
            # 例如：cursor.execute("SELECT * FROM users WHERE name = %s", (user_input,))
            # 而不是：cursor.execute(f"SELECT * FROM users WHERE name = '{user_input}'")

    # 7. HTML/CSS注入防护
    if enable_html_protection:
        # 检测危险的HTML标签
        dangerous_tags = ['<script', '<iframe', '<object', '<embed', '<applet', '<form']
        found_tags = []
        for tag in dangerous_tags:
            if tag.lower() in text.lower():
                found_tags.append(tag)

        if found_tags:
            warnings.append(f'⚠️ 检测到危险的HTML标签: {", ".join(found_tags)}')
            logger.warning(f"检测到危险HTML标签: {found_tags}")
            # 移除这些标签（保留文本内容）
            for tag in found_tags:
                # 简单的标签移除，实际应该使用HTML解析器
                text = re.sub(re.escape(tag) + r'[^>]*>', '', text, flags=re.IGNORECASE)
                text = re.sub(r'</' + re.escape(tag.lstrip('<')) + r'>', '', text, flags=re.IGNORECASE)

        # 检测危险的CSS属性（可能用于XSS）
        dangerous_css = [
            r'expression\s*\(',  # CSS expression
            r'url\s*\(\s*["\']?\s*javascript:',  # javascript: URL
            r'behavior\s*:',  # IE behavior
            r'-moz-binding\s*:',  # Firefox binding
        ]

        css_issues = []
        for pattern in dangerous_css:
            if re.search(pattern, text, re.IGNORECASE):
                css_issues.append(pattern.split('\\')[0])

        if css_issues:
            warnings.append(f'⚠️ 检测到危险的CSS属性: {", ".join(css_issues)}')
            logger.warning(f"检测到危险CSS: {css_issues}")
            # 移除style属性中的危险内容
            text = re.sub(r'style\s*=\s*["\'][^"\']*(?:expression|javascript|behavior|-moz-binding)[^"\']*["\']',
                         'style=""', text, flags=re.IGNORECASE)

    # 8. 路径遍历防护
    # 检测可能的路径遍历攻击
    path_traversal_patterns = [
        r'\.\./',   # ../
        r'\.\.\\',  # ..\
        r'%2e%2e/', # URL编码的../
        r'%2e%2e%2f', # URL编码的../
    ]

    path_issues = []
    for pattern in path_traversal_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            path_issues.append(pattern.replace('\\', ''))

    if path_issues:
        warnings.append(f'⚠️ 检测到可能的路径遍历模式')
        logger.warning(f"检测到路径遍历尝试: {path_issues}")
        # 移除路径遍历序列
        text = re.sub(r'\.\.[/\\]', '', text)
        text = re.sub(r'%2e%2e[/\\%2f]', '', text, flags=re.IGNORECASE)

    # 9. 检查并警告过长的行（可能是单行超长文本）
    lines = text.split('\n')
    max_line_length = max(len(line) for line in lines) if lines else 0
    if max_line_length > 10000:
        warnings.append(f'检测到超长行（{max_line_length}字符），建议分段输入')

    # 10. 截断到最大长度（如果设置了限制）
    if max_length and len(text) > max_length:
        truncated_length = len(text) - max_length
        text = text[:max_length]
        removed_chars.append(f'超出长度限制的 {truncated_length} 个字符')
        warnings.append(f'文本过长，已截断到 {max_length} 字符')

    cleaned_length = len(text)

    # 记录日志
    if warnings:
        logger.info(f"文本清理完成: 原始{original_length}字符 -> 清理后{cleaned_length}字符")
        for warning in warnings:
            logger.info(f"  - {warning}")

    return {
        'cleaned_text': text,
        'removed_chars': removed_chars,
        'warnings': warnings,
        'original_length': original_length,
        'cleaned_length': cleaned_length
    }


def validate_text_for_database(text, field_type='LONGTEXT'):
    """
    验证文本是否适合保存到指定类型的数据库字段

    @param {str} text - 要验证的文本
    @param {str} field_type - 数据库字段类型
    @return {dict} - 验证结果
        {
            'valid': bool,           # 是否有效
            'message': str,          # 消息
            'suggestions': list      # 建议列表
        }
    """
    suggestions = []

    if not text:
        return {
            'valid': True,
            'message': '文本为空',
            'suggestions': []
        }

    # 检查字段类型对应的最大长度
    max_lengths = {
        'TINYTEXT': 255,
        'TEXT': 65535,
        'MEDIUMTEXT': 16777215,
        'LONGTEXT': 4294967295  # 4GB
    }

    max_len = max_lengths.get(field_type, 65535)

    # 估算字节大小（UTF-8编码）
    byte_size = len(text.encode('utf-8'))

    if byte_size > max_len:
        return {
            'valid': False,
            'message': f'文本过大（{byte_size}字节），超过{field_type}限制（{max_len}字节）',
            'suggestions': [
                f'请将文本缩短到 {max_len // 4} 字符以内',
                '或者考虑分多次保存',
                '或者联系管理员升级字段类型'
            ]
        }

    # 检查是否有过多特殊字符
    special_char_ratio = sum(1 for c in text if ord(c) > 127) / len(text) if text else 0
    if special_char_ratio > 0.5:
        suggestions.append('文本包含大量特殊字符，请确认内容正确性')

    # 检查是否有可疑的控制字符
    if re.search(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', text):
        suggestions.append('文本包含控制字符，可能影响显示')

    return {
        'valid': True,
        'message': f'文本有效（{len(text)}字符，{byte_size}字节）',
        'suggestions': suggestions
    }


def format_cleaning_report(clean_result):
    """
    格式化清理报告，用于返回给前端显示

    @param {dict} clean_result - clean_user_text() 的返回结果
    @return {str} - 格式化的报告文本
    """
    if not clean_result['warnings']:
        return None

    report_lines = ['⚠️ 文本处理提示：']

    for warning in clean_result['warnings']:
        report_lines.append(f'• {warning}')

    if clean_result['removed_chars']:
        report_lines.append('')
        report_lines.append('被处理的字符：')
        for char_info in clean_result['removed_chars'][:10]:  # 最多显示10条
            report_lines.append(f'  - {char_info}')

        if len(clean_result['removed_chars']) > 10:
            report_lines.append(f'  ... 及其他 {len(clean_result["removed_chars"]) - 10} 项')

    report_lines.append('')
    report_lines.append(f'原始长度：{clean_result["original_length"]} 字符')
    report_lines.append(f'处理后长度：{clean_result["cleaned_length"]} 字符')

    return '\n'.join(report_lines)


if __name__ == '__main__':
    # 测试用例
    test_cases = [
        ("正常文本", "这是一段正常的文本"),
        ("包含控制字符", "包含控制字符\x00\x01\x02的文本"),
        ("包含零宽字符", "包含零宽字符\u200b\u200c的文本"),
        ("包含emoji", "包含emoji😀🎉的文本"),
        ("混合文本", "混合文本：正常 + \x00控制 + \u200b零宽 + 😀emoji"),
        ("SQL注入尝试", "用户输入' OR '1'='1"),
        ("HTML标签", "文本<script>alert('xss')</script>内容"),
        ("CSS注入", "文本<style>expression(alert('xss'))</style>内容"),
        ("路径遍历", "文件../../etc/passwd路径"),
        ("单引号和双引号", "他说'你好'和\"世界\""),
        ("斜杠和反斜杠", "路径C:\\Users\\test和URL https://example.com"),
    ]

    print("=" * 80)
    print("文本清理功能测试（增强版）")
    print("=" * 80)

    for name, test_text in test_cases:
        print(f"\n测试: {name}")
        print(f"输入: {repr(test_text[:50])}{'...' if len(test_text) > 50 else ''}")
        print("-" * 80)

        result = clean_user_text(test_text)
        print(f"清理后: {repr(result['cleaned_text'][:50])}{'...' if len(result['cleaned_text']) > 50 else ''}")

        if result['warnings']:
            print("\n⚠️ 警告:")
            for warning in result['warnings']:
                print(f"  • {warning}")

        if result['removed_chars']:
            print("\n被处理的字符:")
            for char_info in result['removed_chars'][:5]:
                print(f"  - {char_info}")
            if len(result['removed_chars']) > 5:
                print(f"  ... 及其他 {len(result['removed_chars']) - 5} 项")

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)
