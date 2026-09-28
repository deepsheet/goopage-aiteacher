#!/usr/bin/env bash

# 从指定 GitHub 仓库同步 main 分支，然后提交并推送本地代码。
# 用法：./update-git.sh [提交说明]
# 预览：DRY_RUN=1 ./update-git.sh   只跑暂存与自检，列出将要提交的文件，不 pull/commit/push。
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
DRY_RUN="${DRY_RUN:-0}"
SECRET_PATTERN="(^|[^A-Za-z0-9])(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|LTAI[A-Za-z0-9]{12,}|AIza[0-9A-Za-z_-]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY)|(password|api_key|access_key_secret|secret_key)[[:space:]]*[:=][[:space:]]*[\"'][^\"']{4,}[\"']"
# 一眼假的占位值（测试夹具、模板变量）不算密钥
PLACEHOLDER_PATTERN='[\"'\'']((test|dummy|fake|sample|example|placeholder|changeme|secret123|your)[a-z0-9_-]{0,24}|x{4,}|\*{4,}|<[^>\"'\'']{1,40}>|[A-Za-z0-9_-]{0,24}[$][{][A-Za-z_]+[}])[\"'\'']'

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

if [ "$DRY_RUN" = "1" ]; then
  echo "📥 1/5 跳过 pull（DRY_RUN 预览模式）"
else
  echo "📥 1/5 拉取 GitHub 最新代码…"
  # autostash 只临时保存已追踪改动；被 .gitignore 排除的本机私密文件不会进入 stash。
  git pull --rebase --autostash "$REMOTE_NAME" "$BRANCH_NAME"
fi

echo "📦 2/5 暂存可公开的项目文件…"
git add -A -- .

excluded=0
while IFS= read -r -d '' path; do
  case "$path" in
    .env|*/.env|.env.*|*/.env.*|\
    config/config_local.py|*/config_local.py|\
    config/config-server.py|*/config-server.py|\
    deploy-to-china.sh|*/deploy-to-china.sh|\
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
# 逐文件扫描：测试与示例文件里假密钥字面量是预期内容（如 SECRET_KEY='test'），
# 整文件跳过，否则这个自检会永久阻断提交。
SCAN_SKIP_PATTERN='(^|/)tests?/|(^|/)test_[^/]*\.py$|(^|/)[^/]*_test\.py$|(^|/)conftest\.py$|\.example\.|(^|/)samples?/'
ADDED_TMP="$(mktemp)"
FILTER_TMP="$(mktemp)"
trap 'rm -f "$ADDED_TMP" "$FILTER_TMP"' EXIT

secret_hits=""
while IFS= read -r -d '' path; do
  if printf '%s\n' "$path" | grep -Eqi "$SCAN_SKIP_PATTERN"; then
    continue
  fi
  git diff --cached --no-color --unified=0 -- "$path" \
    | sed -n '/^+++ /d; s/^+// p' > "$ADDED_TMP"
  grep -Eiv "$PLACEHOLDER_PATTERN" "$ADDED_TMP" > "$FILTER_TMP" || true
  if grep -Eiq "$SECRET_PATTERN" "$FILTER_TMP"; then
    secret_hits="${secret_hits}  ❌ ${path}"$'\n'
  fi
done < <(git diff --cached --name-only -z --diff-filter=ACDMRTUXB)

if [ -n "$secret_hits" ]; then
  printf '%s' "$secret_hits" >&2
  fail "上述文件的改动中发现疑似密钥或非空敏感配置。请移到 config/config_local.py 或环境变量后重试。"
fi

if [ "$DRY_RUN" = "1" ]; then
  echo "🧪 5/5 DRY_RUN：以下文件会进入本次提交（未执行 commit / push）"
  git diff --cached --name-status
  exit 0
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
