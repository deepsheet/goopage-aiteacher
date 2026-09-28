# 数据与存储（database）

> 本文是数据落盘与表结构的**唯一权威来源**。架构层面的概览见 [architecture.md](architecture.md)。

## 1. 命名与归属约定

- 本项目**新建**的 MySQL 表统一以 `at_` 前缀命名（当前只有 `at_memory`）。
- `ai_chat_sessions` / `ai_chat_messages` 是**复用的既有表**，`sys_user` 是账户框架共用表，均不受该约定约束，本项目也**不为它们建表或改结构**。
- 材料 owner（数据归属键）由 `routes._current_material_owner()` 决定：登录用户 → `safe_owner_name(username)`；未登录 → 首次访问时生成 `session['aiteacher_guest_id']`，目录名为 `guest-<16位hex>`。
- 共享记忆的 owner 常量：`memory.SHARED_OWNER = '__shared__'`（material / product 层写入该 owner）。

## 2. 存储总览

| 数据 | 介质 | 位置 | 建表/建目录责任 |
|---|---|---|---|
| 学习材料正文 | 文件 | `data/users/<owner>/<id>.html` | 写文件即创建 |
| 学习材料元数据 | 文件 | `data/users/<owner>/<id>.json` | 同上 |
| 三层记忆 | MySQL | `at_memory` | `memory.ensure_memory_table()` 惰性建表 |
| 聊天会话 | MySQL | `ai_chat_sessions` | **外部提供** |
| 聊天消息 | MySQL | `ai_chat_messages` | **外部提供** |
| 账户 | MySQL | `sys_user` | **外部提供**（GoodPage 框架既有表） |
| 会话状态 | Redis 或签名 Cookie | — | Flask-Session |
| 学习偏好、课件进度 | 浏览器 | `localStorage` | — |

`data/users/` 是默认根目录，可用环境变量 `AITEACHER_DATA_ROOT` 覆盖（`materials.DATA_ROOT`）。该目录被 `.gitignore` 忽略，不随代码走；多实例部署需要共享磁盘。

## 3. `at_memory`（三层记忆）

实际执行的 DDL（`src/apps/aiteacher/memory.py`）：

```sql
CREATE TABLE IF NOT EXISTS at_memory (
    id BIGINT NOT NULL AUTO_INCREMENT,
    owner VARCHAR(80) NOT NULL,
    scope VARCHAR(16) NOT NULL,
    material_id VARCHAR(80) NOT NULL DEFAULT '',
    category VARCHAR(40) NOT NULL,
    mem_value TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_mem (owner, scope, material_id, category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

| 列 | 含义 |
|---|---|
| `owner` | 用户标识（用户名安全化后的名字 / `guest-xxx` / `__shared__`） |
| `scope` | `user`（个人画像）、`material`（教材经验）、`product`（全局沉淀） |
| `material_id` | 教材 id；`user`/`product` 层为空串 |
| `category` | 分类键，写入受 `src/prompts/memory_extractor.py` 白名单约束 |
| `mem_value` | 记忆内容（文本） |

行为约束：

- 唯一键使同一 `(owner, scope, material_id, category)` 只有一行，新信息通过 `ON DUPLICATE KEY UPDATE` 覆盖旧值（更新而非累积）。
- 每个 category 最多保留 `MAX_ITEMS_PER_CATEGORY = 20` 条。
- 注入提示词时按 `user > material > product` 优先级，在 `MEMORY_CONTEXT_BUDGET`（默认 2000 字，`AITEACHER_MEMORY_BUDGET` 可覆盖）内裁剪。
- 分类键到中文标签的映射见 `memory.CATEGORY_LABELS`（如 `learner_name` → 称呼、`weak_points` → 薄弱点、`effective_explanations` → 有效讲法）。
- 建表或读写失败**只写日志**，主对话链路继续（`ensure_memory_table` 异常返回 `False`，调用方跳过记忆）。

## 4. `ai_chat_sessions` / `ai_chat_messages`（聊天历史）

本项目只使用下列列，表必须已存在：

| 表 | 被读写的列 |
|---|---|
| `ai_chat_sessions` | `id`、`user_id`、`title`、`current_document_id`、`message_count`、`last_message_at`、`created_at`、`updated_at` |
| `ai_chat_messages` | `id`、`session_id`、`role`、`content`、`metadata`、`created_at` |

关键设计（`src/apps/aiteacher/chat_store.py`）：

- **会话号是确定性的**：`session_id = md5('<user_id>::<doc_id>')`，32 位 hex。一个 (用户, 教程) 恒定映射到同一会话，因此无需给既有表加唯一约束，重复打开/并发写入也稳定。
- **消息号可排序**：`_new_message_id()` = 16 位纳秒时间 hex + 16 位随机 hex，保证 `ORDER BY id` 即时间正序，同秒消息也不错序。
- **写入格式**：`_ensure_session()` 用 `INSERT … ON DUPLICATE KEY UPDATE updated_at=NOW(), title=IFNULL(title, ?)`；每轮写 user + assistant 两条，`role` 只取这两个值；随后 `UPDATE … message_count = message_count + n, last_message_at=NOW()`。
- **长度限制**：`user_id` 截断 50 字符（`MAX_USER_ID_CHARS`），`doc_id` 截断 32 字符（`MAX_DOC_ID_CHARS`），单条 `content` 截断 20000 字符；`metadata` 存 JSON（当前写学习偏好快照）。
- **读取**：`load_history()` 默认 `DEFAULT_HISTORY_LIMIT = 60`，`ORDER BY id DESC LIMIT n` 后在内存翻正为时间正序；`role` 不在白名单或内容为空的行被丢弃。
- 整张功能可用 `AITEACHER_CHAT_HISTORY=0` 关闭；表缺失时 `save_turn()` 回滚并返回 0（历史功能静默失效，对话不受影响）。

新环境若需要这两张表，可参考如下最小 DDL（**这是根据代码用到的列推导的建议结构，仓库中不存在该文件，上线前请按现有库规范复核**）：

```sql
CREATE TABLE IF NOT EXISTS ai_chat_sessions (
    id VARCHAR(32) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    title VARCHAR(255) DEFAULT NULL,
    current_document_id VARCHAR(32) DEFAULT NULL,
    message_count INT NOT NULL DEFAULT 0,
    last_message_at DATETIME DEFAULT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY idx_user_doc (user_id, current_document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ai_chat_messages (
    id VARCHAR(32) NOT NULL,
    session_id VARCHAR(32) NOT NULL,
    role VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT DEFAULT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY idx_session (session_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 5. `sys_user`（账户）

`src/account/models.py` 实际引用的列：

| 列 | 用途 |
|---|---|
| `id` | `generate_user_id()` 生成 |
| `name` | 用户名，登录时与 `email` 一起匹配 |
| `psw` | 口令散列，`hash_password()` = **MD5**（已知技术债） |
| `email` | 注册时查重，可用于登录 |
| `registsrc` / `server` | 注册来源与站点标识 |
| `SYS_ADDUSER` / `SYS_ADDTIME` | 固定写 `'system'` 与当前时间 |
| `lastlogintime` | 登录时更新 |
| `wechat_unionid` / `wechat_nickname` / `google_id` | 社交登录相关列（代码中存在查询路径） |

注册流程会先 `SELECT 1 FROM sys_user WHERE email = %s` / `name = %s` 查重。该表与 GoodPage 框架共用，**不要**由本项目改结构。

## 6. 学习材料的文件模型

一份材料 = **一对文件**，位于 `data/users/<owner>/`：

| 文件 | 角色 |
|---|---|
| `<id>.html` | 课件网页，**内容的唯一事实源**（由 `_complete_html()` 补全为完整文档） |
| `<id>.json` | 元数据：`id`、`title`(≤120)、`source_type`、`source_label`(≤500)、`original_name`(≤255)、`viewer_file`、`created_at` |

要点：

- 落盘 JSON **不含** `text` 与 `manifest`（`_persistable_metadata()` 显式剔除）；纯文本与能力清单在 `load_material()` 读取时从 HTML 即时派生，避免正文出现两份事实源。（例外：`data/users/` 中在本约定之前的旧文件仍带 `text` 字段，读取路径不依赖它。）
- 材料 id 由 `_new_material_id()` 生成（时间戳 + 短随机），目录按 owner 隔离。
- 内置教程不落 `data/users/`：清单在 `builtin_materials.py`，本体是 `src/apps/aiteacher/builtin_materials/*.html`。
- 文本长度上限：提取/截取后 `MAX_MATERIAL_TEXT_CHARS = 30000` 字符；抓取网页与上传文件均限 `5MB`（`MAX_FETCH_BYTES` / `MAX_UPLOAD_BYTES`）。
- 允许上传的扩展名：`.html`、`.htm`、`.md`、`.markdown`、`.txt`。

## 7. 数据生命周期与隐私

| 数据 | 可清除方式 | 说明 |
|---|---|---|
| 记忆 | `DELETE /aiteacher/api/memory`（仅 user 层） | material/product 层为共享沉淀，无删除接口 |
| 聊天历史 | 无接口 | 表内长期保留，需 DBA 侧清理 |
| 学习材料 | 无删除接口 | 直接删 `data/users/<owner>/` 下文件对 |
| 会话 | 浏览器清 Cookie | Redis 侧无主动清理 |
| 偏好 | 浏览器 `localStorage` | 从不写入服务端表 |

`data/users/` 下已有真实学习记录（HTML/JSON 成对），属用户数据，**不得**提交进版本控制、**不得**作为示例复制到文档或代码里。记忆写入前经 `parse_deltas()` 做分类白名单、scope 匹配、置信度与 PII/敏感词过滤（详见 [security.md](security.md)）。
