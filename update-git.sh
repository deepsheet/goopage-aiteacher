#!/usr/bin/env bash

# 从指定 GitHub 仓库同步 main 分支，然后提交并推送本地代码。
# 用法：./update-git.sh [提交说明]
#
# 安全原则：
# - 本机配置、密钥、用户数据和日志不会被上传，也不会被删除。
# - 暂存内容中发现疑似真实密钥时立即停止，不执行 commit/push。

set -Eeuo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPECTED_HTTPS="https://github.com/deepsheet/goopage-aiteacher.git"
EXPECTED_SSH="git@github.com:deepsheet/goopage-aiteacher.git"
REMOTE_NAME="origin"
BRANCH_NAME="main"
COMMIT_MESSAGE="${1:-chore: sync local updates}"
SECRET_PATTERN="(^|[^A-Za-z0-9])(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|LTAI[A-Za-z0-9]{12,}|AIza[0-9A-Za-z_-]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY)|(password|api_key|access_key_secret|secret_key)[[:space:]]*[:=][[:space:]]*[\"'][^\"']{4,}[\"']"

cd "$REPO_DIR"

fail() {
  echo "❌ $*" >&2
  exit 1
}

echo "=========================================="
echo "同步 goopage-aiteacher"
echo "=========================================="

git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || fail "当前目录不是 Git 仓库：$REPO_DIR"

REMOTE_URL="$(git remote get-url "$REMOTE_NAME" 2>/dev/null || true)"
case "$REMOTE_URL" in
  "$EXPECTED_HTTPS"|"$EXPECTED_SSH") ;;
  *) fail "origin 地址不符合预期：${REMOTE_URL:-未配置}" ;;
esac

CURRENT_BRANCH="$(git branch --show-current)"
[ "$CURRENT_BRANCH" = "$BRANCH_NAME" ] \
  || fail "请先切换到 $BRANCH_NAME 分支，当前分支是 ${CURRENT_BRANCH:-detached HEAD}"

echo "📥 1/5 拉取 GitHub 最新代码…"
# autostash 只临时保存已追踪改动；被 .gitignore 排除的本机私密文件不会进入 stash。
git pull --rebase --autostash "$REMOTE_NAME" "$BRANCH_NAME"

echo "📦 2/5 暂存可公开的项目文件…"
git add -A -- .

excluded=0
while IFS= read -r -d '' path; do
  case "$path" in
    .env|*/.env|.env.*|*/.env.*|\
    config/config_local.py|*/config_local.py|\
    *.pem|*.key|*.p12|*.pfx|\
    data/*|*/data/*|userdata/*|*/userdata/*|userfiles/*|*/userfiles/*|\
    logs/*|*/logs/*|.aws/*|*/.aws/*|.ssh/*|*/.ssh/*|\
    *credentials*.json|*service-account*.json)
      git restore --staged -- "$path" 2>/dev/null || git reset -q HEAD -- "$path"
      echo "🔒 已排除敏感文件：$path"
      excluded=1
      ;;
  esac
done < <(git diff --cached --name-only -z --diff-filter=ACDMRTUXB)

if [ "$excluded" -eq 1 ]; then
  echo "   上述文件仍保留在本机，只是不进入本次提交。"
fi

echo "🔍 3/5 检查暂存内容…"
git diff --cached --check

# 只检查新增行；匹配常见云密钥、私钥和非空的敏感配置字面量。
if git diff --cached --no-color --unified=0 -- . \
  | sed -n '/^+++ /d; /^+/p' \
  | grep -Eiq "$SECRET_PATTERN"; then
  fail "暂存内容中发现疑似密钥或非空敏感配置。请移到 config/config_local.py 或环境变量后重试。"
fi

if git diff --cached --quiet; then
  echo "✅ 4/5 没有本地改动需要提交。"
else
  echo "💾 4/5 创建提交：$COMMIT_MESSAGE"
  git commit -m "$COMMIT_MESSAGE"
fi

echo "🚀 5/5 推送到 GitHub…"
git push "$REMOTE_NAME" "$BRANCH_NAME"

echo ""
echo "✅ 同步完成"
git log --oneline -1
