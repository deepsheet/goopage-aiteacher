#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件存储服务 — 统一抽象层

所有文件操作必须通过此类，支持通过配置动态切换后端：
  - disk: 本地磁盘存储
  - oss:  阿里云OSS存储

使用方式：
    from src.services.file_storage_service import get_storage_service
    storage = get_storage_service()
    content = storage.read_text('userfiles/test.txt')
    storage.write_text('article_ids/abc.txt', 'filepath')

配置方式（config/config.py）：
    STORAGE_CONFIG = {
        'backend': 'disk',
        'disk': {'base_dir': 'userdata'},
        'oss': {
            'endpoint': 'oss-cn-beijing.aliyuncs.com',
            'access_key_id': '',
            'access_key_secret': '',
            'bucket_name': 'aiteacher-userdata',
        }
    }
"""

import json
from src.logger import logger


class FileStorageService:
    """
    文件存储服务统一接口

    所有 key 为相对路径（相对于 base_dir 或 Bucket 根），例如：
        'userfiles/username/202606/file.html'
        'article_ids/abc123.txt'
        'userfiles/apps/user123/myapp/index.html'

    Disk 模式: key 映射为 {base_dir}/{key}（base_dir 默认为 userdata）
    OSS 模式:  key 映射为 Bucket 中的对象键
    """

    _instance = None

    def __init__(self, config=None):
        if config is None:
            from config.config import STORAGE_CONFIG
            config = STORAGE_CONFIG

        self.backend_name = config.get('backend', 'disk')
        self._init_backend(config)

    def _normalize_key(self, key):
        """统一规范化 key：自动去除 userdata/ 前缀，兼容旧数据格式"""
        if key and isinstance(key, str) and key.startswith('userdata/'):
            key = key[len('userdata/'):]
        return key

    def _init_backend(self, config):
        """根据配置初始化后端实例"""
        backend_name = config.get('backend', 'disk')

        if backend_name == 'disk':
            from src.services.disk_storage import DiskStorageBackend
            disk_config = config.get('disk', {})
            self._backend = DiskStorageBackend(disk_config)

        elif backend_name == 'oss':
            from src.services.oss_storage import OssStorageBackend
            oss_config = config.get('oss', {})
            self._backend = OssStorageBackend(oss_config)

        else:
            raise ValueError(
                f"不支持的文件存储后端: {backend_name}，"
                f"请选择 'disk' 或 'oss'"
            )

        logger.info(f"文件存储服务已初始化，后端: {self.backend_name}")

    # ============================================================
    # 读操作
    # ============================================================

    def read_text(self, key):
        """读取文本文件内容，不存在时抛出 FileNotFoundError"""
        return self._backend.read_text(self._normalize_key(key))

    def read_bytes(self, key):
        """读取二进制文件内容，不存在时抛出 FileNotFoundError"""
        return self._backend.read_bytes(self._normalize_key(key))

    def read_json(self, key):
        """读取JSON文件，返回 dict/list；文件不存在或解析失败时返回 None"""
        try:
            text = self._backend.read_text(self._normalize_key(key))
            return json.loads(text)
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return None

    # ============================================================
    # 写操作
    # ============================================================

    def write_text(self, key, content):
        """写入文本文件，自动创建父目录"""
        self._backend.write_text(self._normalize_key(key), content)

    def write_bytes(self, key, content, content_type=None):
        """写入二进制文件，可指定 Content-Type（OSS 下设置 MIME 类型）"""
        self._backend.write_bytes(self._normalize_key(key), content, content_type=content_type)

    def write_json(self, key, data):
        """写入JSON数据（自动格式化缩进）"""
        content = json.dumps(data, ensure_ascii=False, indent=2)
        self._backend.write_text(self._normalize_key(key), content)

    def write_file(self, key, file_obj):
        """从 Flask FileStorage 对象保存文件到存储"""
        self._backend.write_file(self._normalize_key(key), file_obj)

    def copy_file(self, source_key, dest_key):
        """复制文件/对象"""
        data = self._backend.read_bytes(self._normalize_key(source_key))
        self._backend.write_bytes(self._normalize_key(dest_key), data)

    # ============================================================
    # 删除操作
    # ============================================================

    def delete(self, key):
        """删除单个文件/对象"""
        self._backend.delete(self._normalize_key(key))

    def delete_dir(self, prefix):
        """递归删除目录/前缀下的所有文件"""
        self._backend.delete_dir(self._normalize_key(prefix))

    # ============================================================
    # 查询操作
    # ============================================================

    def exists(self, key):
        """检查文件/对象是否存在"""
        return self._backend.exists(self._normalize_key(key))

    def list_keys(self, prefix):
        """递归列出前缀下的所有 key，返回排序后的列表"""
        return self._backend.list_keys(self._normalize_key(prefix))

    def list_dir(self, prefix):
        """列出一个前缀下的直接子项，返回 [{'name': str, 'is_dir': bool}]"""
        return self._backend.list_dir(self._normalize_key(prefix))

    # ============================================================
    # 目录操作
    # ============================================================

    def ensure_dir(self, key):
        """确保目录存在（磁盘模式创建目录，OSS模式为noop）"""
        self._backend.ensure_dir(self._normalize_key(key))

    # ============================================================
    # 元数据
    # ============================================================

    def get_file_size(self, key):
        """获取文件大小（字节）"""
        return self._backend.get_file_size(self._normalize_key(key))

    def get_modified_time(self, key):
        """获取文件最后修改时间（Unix时间戳）"""
        return self._backend.get_modified_time(self._normalize_key(key))

    def get_public_url(self, key):
        """获取文件公开访问URL"""
        return self._backend.get_public_url(self._normalize_key(key))

    # ============================================================
    # 后端查询
    # ============================================================

    def is_oss_backend(self):
        """判断当前是否为 OSS 后端"""
        return self.backend_name == 'oss'

    @property
    def base_dir(self):
        """获取存储根目录（仅磁盘模式下有意义）"""
        if hasattr(self._backend, 'base_dir'):
            return self._backend.base_dir
        return None


# ============================================================
# 全局单例
# ============================================================

_storage_instance = None


def get_storage_service():
    """
    获取全局 FileStorageService 实例（懒加载单例）

    在整个应用生命周期中共享同一个实例。
    可通过 reset_storage_service() 重置。
    """
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = FileStorageService()
    return _storage_instance


def reset_storage_service(config=None):
    """
    重置存储服务实例（用于测试或配置变更后）

    下次调用 get_storage_service() 时会重新初始化。

    @param config: 可选的新配置字典，不传则使用 config.config.STORAGE_CONFIG
    """
    global _storage_instance
    _storage_instance = None
    if config is not None:
        _storage_instance = FileStorageService(config)
