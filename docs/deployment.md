# 部署与发布（deployment）

> 本文只记录仓库中**真实存在**的脚本与配置。任何密钥、服务器地址、SSH 路径都不写入本文（见 [security.md](security.md)）。

## 1. 环境划分

| 环境 | 启动方式 | 说明 |
|---|---|---|
| 本机开发 | `python app.py` / `./dev.sh` / `./start_dev.sh` | Flask 内置服务器，默认 `0.0.0.0:5058` |
| 生产（服务器） | `./run_prod.sh`（由 gunicorn 守护） | 双实例：5058 HTTPS + 5059 HTTP，站点目录 `/alidata/www/aiteacher` |
| 预发布/ staging | — | **仓库中不存在**对应配置 |

服务器是**多站点共享**环境（同机还跑着 goodpage 等其它 gunicorn 站点），这决定了下面所有安全约束。

## 2. 运行时配置

`gunicorn.conf.py`（生产实际值）：

| 项 | 值 | 备注 |
|---|---|---|
| `workers` | 3 | 注释标注「2 核 CPU 建议 2-3 个 worker」 |
| `worker_class` | `gevent` | I/O 密集（外部模型调用） |
| `worker_connections` | 50 | |
| `bind` | `0.0.0.0:$PORT`，`PORT` 默认 5058 | HTTP 实例通过 `PORT=5059` 覆盖 |
| `timeout` | 600 秒 | 留给 LLM 长响应，**也是 SSE 流的最大存活时间** |
| `daemon` | `True` | gunicorn 自行后台化，因此必须用 pidfile 管理 |
| `max_requests` / `jitter` | 1000 / 50 | worker 定期回收 |
| `preload_app` | `False` | 省内存 |
| `accesslog` / `errorlog` | `logs/gunicorn_access.log` / `logs/gunicorn_error.log` | 相对路径，取决于启动时的 cwd |
| `proc_name` | `aiteacher` | |

应用日志另有 `logs/<日期>.log`（`src/logger.py`），与 gunicorn 日志分开。

## 3. 配置来源（服务器上）

`run_prod.sh` 在启动前依次做三件事：

1. `cd /alidata/www/aiteacher`（脚本里写死的目标目录）。
2. `set -a; . ./.env; set +a` —— 把 `.env` 全量导出为环境变量（`SECRET_KEY`、`PORT`、`HOST`、`FLASK_ENV`、`FLASK_DEBUG` 等）。
3. `mkdir -p logs userdata data/users` —— 保证运行期目录存在。

Python 侧配置仍来自 `config/config.py` + `config/config_local.py`（后者不入库、不覆盖，见 [development.md](development.md) 第 3 节）。HTTPS 实例还需要 `certs/aiteacher.crt` 与 `certs/aiteacher.key`（自签，仓库中不存在、也不应存在）。

## 4. 发布流程

### 4.1 代码同步（`deploy-to-china.sh`，在本机执行）

脚本通过 rsync 推到服务器，策略上有四处关键设计：

| 步骤 | 行为 | 原因 |
|---|---|---|
| 根目录同步 | `rsync -avz`，**不带 `--delete`** | 保留服务器独有文件：`certs/`、`venv/`、`run_prod.sh`、数据目录 |
| 依赖文件 | 单独同步 `requirements.txt` | 保证依赖声明一致 |
| `src/` 同步 | `rsync -avz --delete`，仅作用于 `src/` | 源码与本地严格一致，删除的模块不会在服务器残留 |
| 显式排除 | `config/config_local.py`、`.env`、`data/`、`userdata/`、`certs/`、`venv/`、`logs/`、`docs/`、`debug/`、各类 `deploy*.sh`/`restart.sh`/`start_dev.sh`/`stop.sh`/`dev.sh`/`update-git.sh`/`git-commit-push.sh` | 生产配置与运行数据永不被本机文件覆盖；危险脚本不上传 |

远程侧依次执行：不存在 `run_prod.sh` 时**自动生成一份等价脚本** → 检查/安装 `libGL` 相关系统库 → 当 `UPDATE_DEPENDENCIES=true` 时用阿里云镜像 `pip install -r requirements.txt` → 清理 `__pycache__`/`*.pyc` → `bash ./run_prod.sh` → 健康检查。

`UPDATE_DEPENDENCIES` 默认 `false`：改依赖时要手动改开关，否则新依赖不会装。

### 4.2 服务重启（`run_prod.sh`）

用两个 pidfile（`logs/aiteacher_5058.pid`、`logs/aiteacher_5059.pid`）管理本服务：存在且进程存活则 `kill`，等 3 秒，再分别拉起 HTTPS 与 HTTP 实例。HTTP 实例额外用 `-w 2` 减少资源占用。

⚠️ **生产服务器上禁止执行** `restart.sh`、`stop.sh`、`start_dev.sh`：它们含 `pkill -f gunicorn` 与 `kill -9`，会把同机其它站点一起杀掉。`deploy-to-china.sh` 也在注释里明确了这一点，并且不上传这些脚本。

### 4.3 依赖版本约束

`requirements.txt` 固定了 `gevent==23.9.1`（最后一个提供 cp39 预编译 wheel 的版本）与 `urllib3<2`（服务器 OpenSSL 1.0.2）。放开 pin 前必须先在服务器环境验证，否则可能装不上或运行期报错。

## 5. 迁移步骤

**仓库中没有数据库迁移工具**（无 `migrations/`、无 `.sql`、无 alembic）。

| 场景 | 需要做的事 |
|---|---|
| `at_memory` | 无需操作，首次使用记忆功能时自动 `CREATE TABLE IF NOT EXISTS` |
| `ai_chat_sessions` / `ai_chat_messages` | 必须由数据库侧预先存在；本项目只读写不建表，缺失时历史功能静默降级 |
| `sys_user` | 账户框架既有表，需预先存在 |
| 新增根目录文件入库 | 修改 `.gitignore` 白名单放行（`/*` 之后要 `!/新文件`），否则文件根本不会进入版本控制 |
| 前端资源 | 无构建步骤，`src/apps/aiteacher/static/` 直接由 Flask 提供 |

建议的表结构与 DDL 见 [database.md](database.md)。

## 6. 发布后验证

1. 健康检查（脚本内使用的判据，**必须看 HTTP 状态码**，`curl -s` 拿到 404 也是 0 退出码）：
   ```bash
   curl -sk -o /dev/null -m 10 -w '%{http_code}' https://127.0.0.1:5058/health
   curl -s  -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1:5059/health
   ```
   期望 `200`，响应体 `{"app": "aiteacher", "status": "ok"}`（`src/web_server.py`）。任一端口返回 200 即视为成功。
2. 失败时脚本 `tail -30 logs/gunicorn_error.log` 并退出码 1。
3. 人工复核：`/study` 能打开、一轮对话有流式回复、`/api/tts/voices` 返回音色、打开内置教程能渲染 iframe。
4. 语音必须走 HTTPS 实例（浏览器把录音/自动播放限制在非安全上下文之外）；HTTP 实例仅用于文字自测，且使用自签证书，首次访问需信任证书。

## 7. 回滚

| 类型 | 方法 |
|---|---|
| 代码 | rsync 是覆盖式的，`src/` 还带 `--delete`，**没有自动备份**：回滚只能在本机 `git revert`/切到上一提交后重新执行 `deploy-to-china.sh`。因此发布前确认本机工作区干净是必要前提。 |
| 依赖 | 把 `UPDATE_DEPENDENCIES` 置回 `false` 不会卸载已装的包；需要回滚时在服务器 venv 内显式安装旧版本。 |
| 数据库 | 记忆表可 `TRUNCATE at_memory`（会丢失全部学员画像，谨慎）；`data/users/` 是文件存储，回滚前请先在服务器上备份该目录。 |
| 运行数据 | 部署脚本不触碰 `data/`、`userdata/`、`.env`、`config_local.py`，因此单纯回滚代码不会影响用户材料。 |

## 8. 生产环境限制与安全边界

1. **不得在生产机器上执行全局 pkill**（见 4.2）。
2. **不得让本机文件覆盖服务器配置与数据**：只同步代码，不同步 `config_local.py`/`.env`/`data/`。
3. **不得把密钥写进代码、文档、日志或提交信息**；`config/config_local.example.py` 只提供键名与占位。
4. `SECRET_KEY` 必须在生产设置，否则每次重启随机生成、已登录会话全部失效。
5. 后台工作是进程内 daemon 线程，worker 被 `max_requests` 回收时未完成的记忆提炼会丢失——这是已知取舍，不是故障。
6. `git-commit-push.sh` 使用 `git add -A`，会把工作区所有改动（含数据、日志、密钥文件）一起提交，**不适合**在自动化流程或他人分支上调用。
7. 本仓库的发布与 GitHub 推送是两个独立动作：`update-git.sh` 只校验远程地址并做密钥扫描后 push `main`，不会触发任何部署。

## 9. 待确认

- `deploy-to-china.sh` 目前未纳入版本控制（untracked），且其中写死了服务器地址与 SSH 密钥路径，是否需要改造为读取本地配置后再入库。
- 是否有容器化或 CI 发布计划（仓库中不存在 `Dockerfile`、`docker-compose.yml`、Kubernetes/Terraform 或任何流水线配置）。
- 服务器的 Web 反代/防火墙拓扑：仓库里只有 gunicorn 直接监听 `0.0.0.0` 的证据，没有 Nginx 等配置。
