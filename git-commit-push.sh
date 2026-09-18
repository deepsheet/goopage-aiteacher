#!/bin/bash

# Git 自动提交推送脚本
# 用法: ./git-commit-push.sh [commit_message]

# 获取提交信息，如果没有提供则使用默认消息
COMMIT_MSG="${1:-auto: update code changes}"

echo "=========================================="
echo "Git 自动提交推送脚本"
echo "=========================================="
echo ""

# 1. 检查当前状态
echo "📋 步骤 1: 检查 Git 状态..."
git status --short
echo ""

# 2. 检查是否有修改
CHANGES=$(git status --porcelain)
if [ -z "$CHANGES" ]; then
    echo "✅ 没有需要提交的更改"
    exit 0
fi

# 3. 添加所有更改
echo "📦 步骤 2: 添加所有更改到暂存区..."
git add -A
echo "✅ 已添加所有更改"
echo ""

# 4. 提交更改
echo "💾 步骤 3: 提交更改..."
echo "提交信息: $COMMIT_MSG"
git commit -m "$COMMIT_MSG"

if [ $? -ne 0 ]; then
    echo "❌ 提交失败"
    exit 1
fi
echo "✅ 提交成功"
echo ""

# 5. 推送到远程仓库
echo "🚀 步骤 4: 推送到远程仓库..."
git push origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ 所有操作完成！"
    echo "=========================================="
    echo ""
    echo "最新提交:"
    git log --oneline -1
else
    echo ""
    echo "❌ 推送失败，请检查网络连接或权限"
    exit 1
fi
