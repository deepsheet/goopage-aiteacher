"""
File Upload Service

处理文件上传、删除、会话管理等核心业务逻辑。
基于 anytotable/utils/file_upload_handler.py 移植

提供以下功能：
- 文件上传到服务器（按session组织）
- 文件删除
- 会话文件夹管理
- 旧会话清理
"""

import os
import uuid
import time
import logging
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)


# 默认配置
DEFAULT_CONFIG = {
    'UPLOAD_FOLDER': 'temp',
    'MAX_CONTENT_LENGTH': 5 * 1024 * 1024,  # 5MB
    'ALLOWED_EXTENSIONS': {
        'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif',
        'doc', 'docx', 'xls', 'xlsx', 'csv',
        'html', 'htm'
    }
}


def allowed_file(filename, allowed_extensions):
    """
    检查文件扩展名是否允许

    @param filename: 文件名
    @param allowed_extensions: 允许的扩展名集合
    @return: True如果允许，False否则
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


def get_session_folder(session_id, base_folder='temp'):
    """
    获取或创建会话文件夹

    @param session_id: 会话标识符
    @param base_folder: 基础上传文件夹
    @return: 会话文件夹路径
    """
    session_folder = os.path.join(base_folder, session_id)
    if not os.path.exists(session_folder):
        os.makedirs(session_folder)
    return session_folder


def generate_random_filename(original_filename):
    """
    生成随机文件名，保留原始扩展名

    @param original_filename: 原始文件名
    @return: 带原始扩展名的新随机文件名
    """
    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
    random_name = str(uuid.uuid4()).replace('-', '')[:8]
    timestamp = int(time.time())
    return f"{random_name}_{timestamp}.{ext}" if ext else f"{random_name}_{timestamp}"


def upload_file(file, session_id=None, config=None):
    """
    上传文件到服务器

    @param file: Flask FileStorage对象
    @param session_id: 会话ID（可选）
    @param config: 配置字典（可选）
    @return: 包含success、path、filename、session_id的字典
    """
    upload_config = DEFAULT_CONFIG.copy()
    if config:
        upload_config.update(config)

    if not session_id:
        session_id = str(uuid.uuid4())

    # 检查文件
    if file.filename == '':
        raise ValueError('未选择文件')

    # 检查文件扩展名
    if not allowed_file(file.filename, upload_config['ALLOWED_EXTENSIONS']):
        raise ValueError('不允许的文件类型')

    try:
        # 创建会话文件夹
        session_folder = get_session_folder(session_id, upload_config['UPLOAD_FOLDER'])

        # 生成随机文件名
        filename = generate_random_filename(file.filename)
        file_path = os.path.join(session_folder, filename)

        # 保存文件
        file.save(file_path)

        logger.info(f"文件上传成功: {filename}, 会话: {session_id}")

        return {
            'success': True,
            'path': file_path,
            'filename': filename,
            'session_id': session_id
        }

    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        raise


def delete_file(filename, session_id, config=None):
    """
    删除文件

    @param filename: 完整文件路径
    @param session_id: 会话标识符
    @param config: 配置字典（可选）
    @return: True如果删除成功
    """
    upload_config = DEFAULT_CONFIG.copy()
    if config:
        upload_config.update(config)

    if not filename or not session_id:
        raise ValueError('缺少必要参数')

    try:
        # 验证文件在会话文件夹内（安全检查）
        session_folder = get_session_folder(session_id, upload_config['UPLOAD_FOLDER'])

        # 确保文件路径在会话文件夹内
        if not filename.startswith(session_folder):
            raise PermissionError('无效的文件路径')

        if os.path.exists(filename):
            os.remove(filename)
            logger.info(f"文件删除成功: {filename}")
            return True
        else:
            raise FileNotFoundError(f'文件不存在: {filename}')

    except Exception as e:
        logger.error(f"文件删除失败: {str(e)}")
        raise


def cleanup_old_sessions(base_folder=None, max_age_hours=24):
    """
    清理旧的会话文件夹

    @param base_folder: 基础上传文件夹
    @param max_age_hours: 最大保留时间（小时），默认24小时
    """
    if base_folder is None:
        base_folder = DEFAULT_CONFIG['UPLOAD_FOLDER']

    if not os.path.exists(base_folder):
        return

    current_time = time.time()
    max_age_seconds = max_age_hours * 3600

    for session_folder in os.listdir(base_folder):
        folder_path = os.path.join(base_folder, session_folder)

        if not os.path.isdir(folder_path):
            continue

        # 检查文件夹年龄
        folder_age = current_time - os.path.getmtime(folder_path)

        if folder_age > max_age_seconds:
            try:
                # 删除文件夹中的所有文件
                for filename in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)

                # 删除文件夹
                os.rmdir(folder_path)
                logger.info(f"已清理旧会话: {session_folder}")

            except Exception as e:
                logger.error(f"清理会话 {session_folder} 时出错: {str(e)}")
