#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
本地磁盘存储后端

所有 key 相对于项目根目录下的 base_dir（默认 'userdata'）。
提供与 OSS 后端一致的统一接口。
"""

import os
import shutil
from src.logger import logger


class DiskStorageBackend:
    """
    本地磁盘存储后端

    将 key（相对路径）映射到磁盘绝对路径，进行文件的读写/删除/列表操作。
    """

    def __init__(self, config):
        self.base_dir = config.get('base_dir', 'userdata')
        self._project_root = self._find_project_root()
        logger.info(f"磁盘存储后端已初始化，base_dir={self.base_dir}")

    def _find_project_root(self):
        """定位项目根目录（从 src/services/ 向上2级到项目根）"""
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

    def _to_abs_path(self, key):
        """key → 绝对磁盘路径"""
        return os.path.join(self._project_root, self.base_dir, key)

    def _safe_path(self, key):
        """
        安全路径校验，防止路径遍历攻击

        @param {str} key - 相对路径
        @return {str} - 安全的绝对路径
        @raise ValueError - 如果路径不在 base_dir 内
        """
        abs_path = os.path.abspath(self._to_abs_path(key))
        base_abs = os.path.abspath(os.path.join(self._project_root, self.base_dir))
        if not abs_path.startswith(base_abs):
            raise ValueError(f"非法路径访问: {key}")
        return abs_path

    # ============================================================
    # 读操作
    # ============================================================

    def read_text(self, key):
        """读取文本文件内容"""
        path = self._safe_path(key)
        if not os.path.exists(path):
            raise FileNotFoundError(f"文件不存在: {key}")
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def read_bytes(self, key):
        """读取二进制文件内容"""
        path = self._safe_path(key)
        if not os.path.exists(path):
            raise FileNotFoundError(f"文件不存在: {key}")
        with open(path, 'rb') as f:
            return f.read()

    # ============================================================
    # 写操作
    # ============================================================

    def write_text(self, key, content):
        """写入文本文件，自动创建父目录"""
        path = self._safe_path(key)
        self._ensure_dir_for_file(path)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def write_bytes(self, key, content, content_type=None):
        """写入二进制文件，content_type 在磁盘模式下忽略"""
        path = self._safe_path(key)
        self._ensure_dir_for_file(path)
        with open(path, 'wb') as f:
            f.write(content)

    def write_file(self, key, file_obj):
        """从 Flask FileStorage 对象保存文件到磁盘"""
        path = self._safe_path(key)
        self._ensure_dir_for_file(path)
        file_obj.save(path)

    # ============================================================
    # 删除操作
    # ============================================================

    def delete(self, key):
        """删除单个文件"""
        path = self._safe_path(key)
        if os.path.exists(path):
            os.remove(path)
            logger.debug(f"文件已删除: {key}")

    def delete_dir(self, prefix):
        """递归删除目录及其所有内容"""
        path = self._safe_path(prefix)
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
                logger.info(f"目录已删除: {prefix}")
            else:
                os.remove(path)
                logger.info(f"文件已删除: {prefix}")

    # ============================================================
    # 查询操作
    # ============================================================

    def exists(self, key):
        """检查文件是否存在"""
        path = self._to_abs_path(key)
        return os.path.exists(path)

    def list_keys(self, prefix):
        """递归列出前缀下的所有文件 key（相对于 base_dir）"""
        dir_path = self._safe_path(prefix)
        if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
            return []
        result = []
        base_abs = os.path.join(self._project_root, self.base_dir)
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if f.startswith('.'):
                    continue
                abs_f = os.path.join(root, f)
                rel = os.path.relpath(abs_f, base_abs)
                result.append(rel)
        return sorted(result)

    def list_dir(self, prefix):
        """列出一个前缀下的直接子项，返回 [{'name': str, 'is_dir': bool}]"""
        dir_path = self._safe_path(prefix)
        if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
            return []
        result = []
        for name in sorted(os.listdir(dir_path)):
            if name.startswith('.'):
                continue
            full = os.path.join(dir_path, name)
            result.append({
                'name': name,
                'is_dir': os.path.isdir(full)
            })
        return result

    # ============================================================
    # 目录操作
    # ============================================================

    def ensure_dir(self, key):
        """确保目录存在（末尾不带 '/' ）"""
        path = self._safe_path(key.rstrip('/'))
        os.makedirs(path, exist_ok=True)

    def _ensure_dir_for_file(self, path):
        """确保文件所在的父目录存在"""
        parent = os.path.dirname(path)
        os.makedirs(parent, exist_ok=True)

    # ============================================================
    # 元数据
    # ============================================================

    def get_file_size(self, key):
        """获取文件大小（字节）"""
        path = self._safe_path(key)
        return os.path.getsize(path)

    def get_modified_time(self, key):
        """获取文件最后修改时间（Unix 时间戳）"""
        path = self._safe_path(key)
        return os.path.getmtime(path)

    def get_public_url(self, key):
        """获取文件公开访问URL（相对于站点根路径）"""
        return '/' + os.path.join(self.base_dir, key).replace('\\', '/')
