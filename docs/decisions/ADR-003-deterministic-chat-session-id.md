# ADR-003：用 `md5(user::doc)` 生成确定性聊天会话号

- 状态：已采用
- 记录日期：2026-09-27（补记，`chat_store.py` 模块文档串已写明约定）

## 背景

需求是「一个用户 × 一份教程 = 一个会话，下次打开能恢复」。落点却是两张**不属于本项目**的既有表 `ai_chat_sessions` / `ai_chat_messages`：本项目只读写，不建表也不改结构（见 [database.md](../database.md) 第 4 节）。表里已经存在其它来源写入的短随机 id。

常规做法是「先按 `(user_id, doc_id)` 查询会话，没有就插入」，但这在共享表上并不干净。

## 决策

不查再插，而是**直接算出主键**：`session_id = md5('<user_id>::<doc_id>')`，32 位 hex。消息号则用「16 位纳秒时间 hex + 16 位随机 hex」，使 `ORDER BY id` 天然等于时间正序。

## 依据

| 证据 | 说明 |
|---|---|
| `src/apps/aiteacher/chat_store.py` 模块文档串 | 「会话 id 用二者的 md5（32 位 hex）生成，保证同一教程复用同一会话，且与库中既有的短随机 id 不冲突」 |
| `chat_store.session_id()` | 实现即 `hashlib.md5('%s::%s' % (user_id, doc_id))`，输入先经 `_normalize_user_id`（≤50）与 `_normalize_doc_id`（≤32） |
| `chat_store._new_message_id()` | `'%016x%s' % (time.time_ns(), uuid4().hex[:16])`，注释「保证 `ORDER BY id` 即时间正序（同秒消息也不错序）」 |
| `chat_store._ensure_session()` | 依赖主键做 `INSERT … ON DUPLICATE KEY UPDATE`，因此幂等性来自主键而不是查询 |
| `chat_store.load_history()` | `ORDER BY id DESC LIMIT n` 后在内存翻正，读路径完全不依赖时间列 |

## 放弃的方案

- **先 `SELECT` 再 `INSERT`**：并发或重复打开时会产生两个会话（无唯一约束可依赖），且多一次往返。
- **给 `ai_chat_sessions` 加 `(user_id, current_document_id)` 唯一索引**：需要改动共用表的 DDL，影响面超出本项目，且没有迁移工具兜底。
- **UUID 作为消息号**：无法用主键排序，恢复历史必须按 `created_at` 排序，而同秒消息会错序。

## 影响与代价

- 正面：无需查询即可定位会话，写入幂等；不污染既有表的 id 空间；读路径不需要时间索引。
- 代价：md5 在这里只当**确定性标识**用，不是安全用途（不含防篡改语义）；`user_id`/`doc_id` 一旦截断规则改变，历史就会落到另一个会话上——所以长度上限（50 / 32）属于契约的一部分，改动前必须先想清楚历史迁移。
