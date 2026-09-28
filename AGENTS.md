# AGENTS.md — 仓库工作合同

面向在本仓库工作的编码 Agent（Codex、Qoder 等）。只列约束与命令；产品与架构事实见 `docs/`。

## 目录边界

- 业务代码：`src/apps/aiteacher/`（课堂、教材、语音、记忆、历史）
- 通用模块：`src/account/`（账户）、`src/prompts/`（提示词唯一事实源）、`src/i18n/`（账户文案）、`src/services/` `src/utils/`（GoodPage 框架保留能力，当前课堂业务未直接依赖）
- 应用装配：`src/web_server.py`（Flask app、蓝图注册、安全头）、`app.py`（本地入口）
- 配置：`config/config.py`（可提交默认值）+ `config/config_local.py`（本机私有值，**已 gitignore**）
- 前端资源：`src/apps/aiteacher/static/`、`src/apps/aiteacher/templates/`、`src/templates/home.html`
- 内置课件：`src/apps/aiteacher/builtin_materials/*.html`（自包含，零依赖）
- 测试：`src/apps/aiteacher/tests/`
- 文档：`docs/`（`docs/material-protocol.md` 是课件协议唯一规范）
- **生成数据，不要手工编辑**：`data/users/`（学习材料落盘）、`userdata/`（`src/services/` 磁盘后端）、`logs/`、`.pytest_cache/`

## 常用命令

```bash
pip install -r requirements.txt            # 依赖安装
python app.py                              # 本地运行，默认 http://localhost:5058
./start_dev.sh                             # 开发模式（会先 kill 5058 端口与 app.py/gunicorn 进程，仅限本机）
python -m unittest src.apps.aiteacher.tests.smoke -v        # 冒烟测试（自动关闭记忆/历史）
python -m unittest src.apps.aiteacher.tests.test_memory -v  # 记忆/提示词单测（依赖 MySQL 的用例会自动跳过）
```

仓库**没有** lint、typecheck、build 与数据库迁移命令（未见相关配置或工具目录）；改动后的验证手段只有上面两组 `unittest`。

## 允许自主执行

- 读任意源码与配置（跳过 `.env`、`config/config_local.py`、`config/config-server.py` 等含真实密钥的文件）
- 在上述业务/通用/前端目录内编辑代码与文档
- 运行本地 `python app.py` 与两组 `unittest`
- 用 Flask test client 写临时断言脚本，但**任务结束前删除**（不留根目录散落的测试文件）

## 禁止（未获明确批准前）

- 运行 `./restart.sh`、`./stop.sh`、`pkill -f gunicorn`、`kill -9`：这些脚本按名字杀进程，会连带杀掉同一台服务器上的其他站点
- 执行 `deploy-to-china.sh`、`run_prod.sh`、`rsync` 上传、SSH 登录生产机
- 对生产/共享 MySQL 执行 `DROP`/`ALTER`/批量 `UPDATE`/建表；`at_memory` 只允许由应用启动路径惰性创建
- `git push --force`、`git reset --hard`、直接合并或推送到 `main`/`master`、跳过钩子
- 使用 `./git-commit-push.sh`：它执行 `git add -A`，会把 `data/users/`、日志、`.env` 等一并提交；需要提交时请显式列出文件
- 修改或提交 `.env`、`config/config_local.py`、`config/config-server.py`、`certs/`、`*.pem`、`*.key`
- 新增第三方依赖、修改 `requirements.txt` 中的版本锁（`gevent==23.9.1`、`urllib3<2` 是服务器 OpenSSL/Python 约束）
- 在文档、日志、提交信息或代码注释中写入真实 API Key、密码、Token、Cookie、服务器 IP/域名

## 生产环境边界

生产为共享服务器：双 gunicorn 实例（HTTPS 5058 / HTTP 5059），`run_prod.sh` 用 `logs/*.pid` 只管本服务。判断当前目标环境以**主机与路径**为准：本机路径在本仓库工作目录下，服务器部署目录见 `run_prod.sh` 首行。任何会影响线上进程、端口、证书或数据的操作都需要用户明确授权。

## 完成任务的定义

1. 相关 `unittest` 全绿（`Ran N tests ... OK`）；数据库不可用导致的 skip 要说明。
2. `git diff` 只包含本次任务的文件，无临时文件、无密钥、无生成数据。
3. 行为发生变化时同步更新对应 `docs/*`（见下表），并保证 `python3 <skill>/scripts/validate_docs.py .` 无 error。
4. 报告：改了什么、为什么、如何验证、未验证的部分标 `待确认`。

## 什么任务该读哪份文档

| 任务 | 先读 |
|---|---|
| 产品范围、用户、业务规则 | [docs/product.md](docs/product.md) |
| 组件职责、数据流、外部依赖、技术债 | [docs/architecture.md](docs/architecture.md) |
| 环境、配置项、测试怎么跑 | [docs/development.md](docs/development.md) |
| 发布、探活、回滚、共享服务器限制 | [docs/deployment.md](docs/deployment.md) |
| 增改 HTTP 接口与上下文载荷 | [docs/api.md](docs/api.md) |
| 表结构、落盘文件、建表策略 | [docs/database.md](docs/database.md) |
| 沙箱、SSRF、密钥、PII、提示注入 | [docs/security.md](docs/security.md) |
| 课件能力声明、高亮/指令桥接 | [docs/material-protocol.md](docs/material-protocol.md) |
| 既有技术选择的原因 | [docs/decisions/README.md](docs/decisions/README.md) |
| 多步骤任务与 Agent 交接 | [tasks/README.md](tasks/README.md) |
