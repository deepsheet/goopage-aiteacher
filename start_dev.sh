#!/bin/bash

# 🔵 开发环境启动脚本 - 使用 Flask 内置服务器（支持热重载）
echo "🚀 启动 AI Teacher 开发环境..."
echo "📝 调试模式：已启用"
echo "🔄 代码热重载：已启用"
echo "🌐 端口：5058"
echo "⚠️  注意：仅用于本地开发，不要用于生产环境"
echo ""

# 设置开发环境变量
export FLASK_ENV=development
export FLASK_DEBUG=1
export PORT=5058
export HOST=0.0.0.0

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

# 启动服务（Flask 内置服务器，支持热重载）
echo "启动 AI Teacher（开发模式 - Flask 内置服务器）..."
echo "详细日志请查看 logs/server.log"
echo ""
python3 app.py
