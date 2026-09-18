#!/bin/bash

# 🟢 生产环境启动脚本 - 使用 Gunicorn + Gevent（多进程并发）
# 用于服务器部署，支持高并发

# 设置环境变量（生产环境）
export PORT=5058
export FLASK_ENV=production
export FLASK_DEBUG=0

# 确保日志目录存在
mkdir -p logs

# 先关闭已存在的服务
echo "正在检查并关闭已存在的服务..."

# 方法 1：查找并杀死占用 5058 端口的进程
echo "检查 5058 端口是否被占用..."
PID=$(lsof -ti:5058)
if [ ! -z "$PID" ]; then
    echo "发现占用 5058 端口的进程 (PID: $PID)，正在停止..."
    kill -9 $PID
    sleep 2
    echo "已停止占用端口的进程"
else
    echo "5058 端口未被占用"
fi

# 方法 2：也杀死可能存在的 app.py 进程和 gunicorn 进程
pkill -f "python3 app.py" 2>/dev/null
pkill -f "python app.py" 2>/dev/null
pkill -f "gunicorn" 2>/dev/null
sleep 2

echo "已完成端口清理"

# 启动服务 - 使用 Gunicorn + Gevent（多进程异步模式）
echo "正在启动 AI Teacher 服务，详细日志请查看 logs/gunicorn_error.log ..."
gunicorn -c gunicorn.conf.py src.web_server:app

# 等待服务启动
sleep 3

# 检查服务是否成功启动
if curl -s http://localhost:${PORT}/health > /dev/null; then
    echo "服务启动成功！"
    echo "服务运行在 http://localhost:${PORT}"

    # 自动打开网页
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open "http://localhost:${PORT}"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        xdg-open "http://localhost:${PORT}"
    fi
else
    echo "服务启动失败，请检查日志文件 logs/server.log"
    echo "最后 10 行日志："
    tail -n 10 logs/server.log
fi

echo ""
echo "可以通过以下命令检查服务状态："
echo "curl http://localhost:${PORT}/health"

# 提示如何设置定时任务
# echo "要设置定时任务，请运行以下命令："
# echo "crontab -e"
# echo "并添加以下内容："
# cat crontab_config.txt
