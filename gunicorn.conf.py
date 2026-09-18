import multiprocessing
import os

# 从环境变量获取端口，默认 5058
PORT = int(os.getenv('PORT', '5058'))

# 工作进程数（2核CPU建议2-3个worker）
workers = 3

# 使用 gevent 异步模式（适合 I/O 密集型任务）
worker_class = 'gevent'

# 每个 worker 的最大并发连接数
worker_connections = 50

# 绑定的地址和端口
bind = f'0.0.0.0:{PORT}'

# 超时时间（LLM API 调用可能需要较长时间）
timeout = 600

# 访问日志和错误日志
accesslog = 'logs/gunicorn_access.log'
errorlog = 'logs/gunicorn_error.log'
loglevel = 'info'

# 后台运行
daemon = True

# 进程名称
proc_name = 'aiteacher'

# 最大请求数后重启 worker（防止内存泄漏）
max_requests = 1000
max_requests_jitter = 50

# 不预加载应用（节省内存）
preload_app = False
