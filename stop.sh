#!/bin/bash

# 设置环境变量（固定使用 5058 端口）
export PORT=5058
export FLASK_ENV=development
export FLASK_DEBUG=1

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

# 方法 2：也杀死可能存在的 app.py 进程
pkill -f "python3 app.py" 2>/dev/null
pkill -f "python app.py" 2>/dev/null
sleep 2

echo "已完成端口清理"
