# 开发指南（development）

> 本文只收录**来自真实配置文件或已实际执行过**的命令与配置项。未定义的命令一律标注「仓库中不存在」。

## 1. 环境要求

| 项 | 值 | 依据 |
|---|---|---|
| Python | 3.9 及以上 | `README.md`；`requirements.txt` 注明 `gevent==23.9.1` 是「最后一个提供 cp39 预编译 wheel 的版本」 |
| 本机已验证环境 | Python 3.11.4（`python3 -V`），依赖装在系统解释器，仓库无 `.venv/` | 本次文档审计实际执行结果 |
| Web 框架 | Flask `>=2.3,<4`（本机为 2.3.3）、Flask-Cors、Flask-Session | `requirements.txt` |
| 数据库 | MySQL（PyMySQL 客户端） | `requirements.txt`、`src/db_manager.py`、`src/account/models.py` |
| 缓存/会话 | Redis 可选，未启动时自动回退签名 Cookie Session | `src/web_server.py` |
| 生产 WSGI | Gunicorn + gevent | `requirements.txt`、`gunicorn.conf.py` |
| 默认端口 | 5058（`PORT` 可覆盖） | `app.py`、`gunicorn.conf.py` |

本机开发**不强制**安装 Redis；不装也能跑首页与课堂。

## 2. 安装依赖

```bash
python3 -m venv .venv && source .venv/bin/activate   # 推荐，但仓库未预置虚拟环境
pip install -r requirements.txt
```

`gevent==23.9.1` 与 `urllib3<2` 是为兼容生产服务器的 Python 3.9 + OpenSSL 1.0.2 而固定，本机开发同样可用；**不要**在本机随手升级这两个包（见 [deployment.md](deployment.md)）。

## 3. 配置

配置分三层，后者覆盖前者：

1. `config/config.py`：可提交的公共默认值（Key 留空、host 为 localhost）。
2. `config/config_local.py`：本机私有值，**已被 `.gitignore` 忽略**，从示例复制：
   ```bash
   cp config/config_local.example.py config/config_local.py
   ```
3. 环境变量与 `.env`（`app.py` 启动时 `load_dotenv()` 加载）：`.env` 同样被忽略，仓库中没有 `.env.example`。

### Python 配置变量（名称，不含值）

| 变量 | 作用 | 读取位置 |
|---|---|---|
| `CURRENT_MODEL` | 选择 `deepseek` 或 `qwen` | `src/llm_client.py` |
| `DEEPSEEK_API_KEY` / `DEEPSEEK_API_URL` / `DEEPSEEK_MODEL` | DeepSeek 对话 | `src/llm_client.py` |
| `QWEN_API_KEY` / `QWEN_BASE_URL` / `QWEN_MODEL` | Qwen 对话（也作语音默认 Key 的回退） | `src/llm_client.py`、`src/apps/aiteacher/voice.py` |
| `DASHSCOPE_API_KEY` / `DASHSCOPE_BASE_URL` | ASR/TTS 首选密钥与端点 | `src/apps/aiteacher/voice.py` |
| `TTS_CONFIG` | Qwen3-TTS 模型、回退音色、端点、分块字数、超时 | `src/apps/aiteacher/voice.py::_tts_config` |
| `VOXCPM_CONFIG` / `MODELBEST_API_KEY` | 可选真人感 TTS；未配置时回落 Qwen3-TTS | `config/config_local.example.py`、`voice.py` |
| `PROACTIVE_CONFIG` | 主动等待判定的延迟、上限与超时 | `src/apps/aiteacher/routes.py::_proactive_config` |
| `DB_CONFIG` | MySQL 连接（默认 `localhost:3306`，库名 `uni`） | `src/account/models.py`、`memory.py`、`chat_store.py`、`db_manager.py` |
| `REDIS_CONFIG` | Session Redis | `src/web_server.py` |
| `LOG_DIR` | 日志目录，默认 `logs` | `src/logger.py` |
| `STORAGE_CONFIG` | `src/services/` 的存储后端选择（`disk`/`oss`），课堂业务未使用 | `src/services/file_storage_service.py` |
| `DEFAULT_LANGUAGE` / `SUPPORTED_LANGUAGES` | 账户模块文案语言 | `src/i18n` |

### 环境变量

| 变量 | 作用 | 默认 |
|---|---|---|
| `SECRET_KEY` | 会话签名密钥；未设置时随机生成、重启即失效（生产必设） | 随机 |
| `HOST` / `PORT` | `app.py` 监听地址与端口 | `0.0.0.0` / `5058` |
| `FLASK_ENV` | `development` 时开启模板/静态缓存关闭与 debug 重载 | 未设 |
| `FLASK_DEBUG` | 由启动脚本设置，配合 `FLASK_ENV` | 未设 |
| `AITEACHER_DATA_ROOT` | 学习材料存储根目录 | 仓库根目录下的 `data/users` |
| `AITEACHER_MEMORY` | 记忆功能开关 | 开；`0`/`false`/`off`/`no` 关闭 |
| `AITEACHER_MEMORY_BUDGET` | 注入提示词的记忆字数预算 | `2000` |
| `AITEACHER_CHAT_HISTORY` | 聊天历史持久化开关 | 开；同上取值 |
| `AITEACHER_MATERIAL_MAX_TOKENS` | 生成整页课件的最大输出 token | `30000` |

密钥值一律不写进文档、日志或提交信息（见 [security.md](security.md)）。

## 4. 启动

```bash
python app.py            # 前台启动，http://localhost:5058/
./start_dev.sh           # 开发模式：先清理 5058 端口与 app.py/gunicorn 进程再启动（仅本机！）
./dev.sh                 # 仅设置 FLASK_ENV=development 后 python app.py，不清理端口
```

页面：`/` 宣传首页，`/study` 课堂，`/aiteacher/` 子应用入口，`/health` 探活。

⚠️ `start_dev.sh`、`restart.sh`、`stop.sh` 内含 `pkill -f gunicorn` 与 `kill -9`。生产服务器上有多个站点共用 gunicorn，**这些脚本绝不能在那台机器上执行**（`run_prod.sh` 才是服务器用的 pidfile 方式，见 [deployment.md](deployment.md)）。

## 5. 测试

```bash
python -m unittest src.apps.aiteacher.tests.smoke -v
python -m unittest src.apps.aiteacher.tests.test_memory -v
```

- 本次文档审计实际执行结果：`smoke` 34 个用例 `OK`，`test_memory` 17 个用例 `OK`（本机 MySQL 可用）。
- `src/apps/aiteacher/tests/smoke.py` 在 `setUp` 中把 `AITEACHER_CHAT_HISTORY`/`AITEACHER_MEMORY` 置为 `0`，并把 `materials.DATA_ROOT` 指向临时目录，**因此冒烟测试不会写真实数据库和用户目录**。
- `src/apps/aiteacher/tests/test_memory.py` 中依赖数据库的用例在 MySQL 不可用时自动跳过。
- 测试文件位置约定：正式测试放 `src/apps/aiteacher/tests/`。仓库根目录的 `.cursorrules` 曾要求测试写进 `debug/`，与现状不符，见「常见开发问题」。

## 6. 代码质量与构建

仓库中**不存在** lint、format、typecheck、build 配置（无 `pyproject.toml`、`setup.cfg`、`tox.ini`、`Makefile`、`.pre-commit-config.yaml`，`package.json` 与前端构建链也没有）。前端 `app.js`/`app.css` 为手写源码，直接由 Flask 静态目录提供，无需构建。

CI/CD：仓库中**不存在** `.github/workflows`、`.gitlab-ci.yml`、`Jenkinsfile` 等流水线配置。

## 7. 数据库初始化与迁移

**没有迁移工具**（无 `migrations/`、无 `.sql` 文件）。启动后各表的处理方式：

| 表 | 谁负责建 |
|---|---|
| `at_memory` | `src/apps/aiteacher/memory.py` 首次使用时惰性 `CREATE TABLE IF NOT EXISTS` |
| `sys_user` | 需已存在（GoodPage 框架既有表；列结构见 [database.md](database.md)） |
| `ai_chat_sessions`、`ai_chat_messages` | 需已存在（本项目只读写，不建表） |

新环境若要完整跑通历史与账户功能，需要先自备这两组表；缺失时对应功能会静默降级（写入失败仅记日志）。建表 DDL 建议见 [database.md](database.md)。

## 8. 常见开发问题

| 症状 | 原因与处理 |
|---|---|
| 启动日志出现 `⚠️ 未设置 SECRET_KEY 环境变量` | 正常提示（`src/web_server.py`）；本地无影响，重启后旧会话失效 |
| 日志出现 `Redis 不可用，使用 Cookie Session` | 未装/未启动 Redis，属预期降级；需要跨设备会话时再启 Redis |
| `pip install` 时 gevent 或 urllib3 编译失败 | 服务器侧 OpenSSL/Python 版本约束；按 `requirements.txt` 注释使用 cp39 组合，不要放开 pin |
| 对话返回「AI老师暂时没有连上」 | 未配置模型 Key 或 `CURRENT_MODEL` 指向未配 Key 的模型；查 `logs/<日期>.log` |
| 语音没出声 | 语音需要安全上下文：HTTP 端口下浏览器可能拦截自动播放；服务器 HTTPS 实例使用自签证书，需先信任 |
| TTS 换了音色 | VoxCPM2 音色无法锁定说话人（`voice.py` 的 `unstable` 标记），服务端会以 `degraded` 告知前端 |
| 刷新后课件进度没了 | 预览 iframe 无 `allow-same-origin`，课件内不能用 `localStorage`，进度只在内存（[material-protocol.md](material-protocol.md) 第 2 节） |
| 材料打开报「学习材料已经不可用」 | `data/users/<owner>/` 下文件被删或 owner 变了（换浏览器/清 Cookie 会换 guest 目录） |
| 根目录放新文件后 git 看不见 | `.gitignore` 是白名单式（先 `/*`），需显式 `!/新文件` 放行；`.cursorrules` 里「文件放 `docs/`、`debug/`」的约定同样要配合放行 |
| `.cursorrules` 与实际结构不一致 | 该规则要求测试进 `debug/`、文档进 `docs/`，而实际测试在 `src/apps/aiteacher/tests/`；以本仓库现状与 [AGENTS.md](../AGENTS.md) 为准 |
