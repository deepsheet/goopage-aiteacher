#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
阿里云OSS存储后端

所有 key 映射为 OSS Bucket 中的对象键。
OSS 没有真正的目录，所有目录操作基于前缀模拟。

依赖: pip install oss2
"""

import json
import oss2
from src.logger import logger


class OssStorageBackend:
    """
    阿里云OSS存储后端

    将 key（相对路径）映射为 OSS 对象键进行存储操作。
    """

    def __init__(self, config):
        self.endpoint = config['endpoint']
        self.bucket_name = config['bucket_name']
        self._cdn_domain = config.get('cdn_domain', None)
        self._public_read = config.get('public_read', False)

        auth = oss2.Auth(
            config['access_key_id'],
            config['access_key_secret']
        )
        self._bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)

        # 验证连接
        try:
            self._bucket.get_bucket_info()
            logger.info(f"OSS 连接成功，Bucket: {self.bucket_name}")
        except Exception as e:
            logger.warning(f"OSS 连接验证失败（操作时会重试）: {e}")

    # ============================================================
    # 读操作
    # ============================================================

    def read_text(self, key):
        """读取文本对象内容"""
        obj = self._bucket.get_object(key)
        return obj.read().decode('utf-8')

    def read_bytes(self, key):
        """读取二进制对象内容"""
        obj = self._bucket.get_object(key)
        return obj.read()

    # ============================================================
    # 写操作
    # ============================================================

    def write_text(self, key, content):
        """写入文本对象"""
        self._bucket.put_object(
            key,
            content.encode('utf-8'),
            headers={'Content-Type': 'text/plain; charset=utf-8'}
        )

    def write_bytes(self, key, content, content_type=None):
        """写入二进制对象，可通过 content_type 指定 MIME 类型"""
        headers = {}
        if content_type:
            headers['Content-Type'] = content_type
        self._bucket.put_object(key, content, headers=headers)

    def write_file(self, key, file_obj):
        """从 Flask FileStorage 对象上传到 OSS"""
        data = file_obj.read()
        content_type = file_obj.content_type or 'application/octet-stream'
        self._bucket.put_object(
            key,
            data,
            headers={'Content-Type': content_type}
        )

    # ============================================================
    # 删除操作
    # ============================================================

    def delete(self, key):
        """删除单个对象"""
        self._bucket.delete_object(key)

    def delete_dir(self, prefix):
        """递归删除前缀下的所有对象"""
        prefix = prefix.rstrip('/') + '/'
        deleted = 0
        for obj in oss2.ObjectIterator(self._bucket, prefix=prefix):
            self._bucket.delete_object(obj.key)
            deleted += 1
        logger.info(f"已删除 {deleted} 个对象，前缀: {prefix}")

    # ============================================================
    # 查询操作
    # ============================================================

    def exists(self, key):
        """检查对象是否存在"""
        return self._bucket.object_exists(key)

    def list_keys(self, prefix):
        """递归列出前缀下的所有对象 key"""
        result = []
        for obj in oss2.ObjectIterator(self._bucket, prefix=prefix):
            result.append(obj.key)
        return sorted(result)

    def list_dir(self, prefix):
        """列出一个前缀下的直接子项（模拟目录），返回 [{'name': str, 'is_dir': bool}]"""
        prefix_clean = prefix.rstrip('/') + '/' if prefix else ''
        result = []
        for obj in oss2.ObjectIterator(self._bucket, prefix=prefix_clean, delimiter='/'):
            if obj.is_prefix():
                dir_name = obj.key[len(prefix_clean):].rstrip('/')
                if dir_name and not dir_name.startswith('.'):
                    result.append({'name': dir_name, 'is_dir': True})
            else:
                file_name = obj.key[len(prefix_clean):]
                if file_name and not file_name.startswith('.'):
                    result.append({'name': file_name, 'is_dir': False})
        return sorted(result, key=lambda x: (not x['is_dir'], x['name']))

    # ============================================================
    # 目录操作
    # ============================================================

    def ensure_dir(self, key):
        """OSS 无需创建目录"""
        pass

    # ============================================================
    # 元数据
    # ============================================================

    def get_file_size(self, key):
        """获取对象大小（字节）"""
        meta = self._bucket.head_object(key)
        return meta.content_length

    def get_modified_time(self, key):
        """获取对象最后修改时间（Unix 时间戳）"""
        meta = self._bucket.head_object(key)
        return meta.last_modified.timestamp()

    def get_public_url(self, key):
        """获取对象的公开访问URL"""
        if self._public_read:
            if self._cdn_domain:
                return f"https://{self._cdn_domain}/{key}"
            return f"https://{self._bucket_name}.{self.endpoint}/{key}"
        # 私有 Bucket 返回签名URL（有效期 1 小时）
        return self._bucket.sign_url('GET', key, 3600)
