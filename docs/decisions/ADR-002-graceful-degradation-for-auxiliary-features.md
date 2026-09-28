# ADR-002：辅助功能一律优雅降级，不得阻断对话主链路

- 状态：已采用
- 记录日期：2026-09-27（补记，代码中已有一致实现）

## 背景

除对话本身之外，系统还挂着四类辅助能力：三层记忆、聊天历史持久化、Redis 会话、语音（ASR/TTS）与主动等待判定。它们各自依赖外部服务（MySQL、Redis、模型侧的额外一次调用），故障概率不为零，且都不是「孩子此刻要能继续上课」的必要条件。

## 决策

辅助能力失败必须表现为**功能不可用**，而不是**请求失败**：读取路径返回空集合，写入路径静默失败并只记日志，判定路径返回安全默认值。主对话链路（`/api/chat` 的流式返回）优先保证。

## 依据

| 证据 | 说明 |
|---|---|
| `src/apps/aiteacher/memory.py` 模块文档串 | 「所有对外函数都做优雅降级：数据库不可用时读取返回空、写入静默失败，绝不因为记忆功能异常而打断主对话链路」 |
| `memory.ensure_memory_table()` | 建表异常时返回 `False` 并 `logger.warning('记忆表不可用，已跳过记忆功能：%s')`，调用方据此跳过 |
| `src/apps/aiteacher/chat_store.py::save_turn()` | 异常回滚后 `logger.warning('保存聊天历史失败（已忽略）：%s')` 并 `return 0`，不向上抛 |
| `chat_store.load_history()` | 异常时 `return []` |
| `src/apps/aiteacher/routes.py::_schedule_background_work()` | 保存历史与提炼记忆各自包 `try/except`，注释「任一步失败都不影响已经返回给用户的主对话流」 |
| `routes._nudge_wait()` 文档串 | 「安全降级：什么都不说，稍后再看一眼（判定失败=继续等待）」 |
| `src/web_server.py` Redis 分支 | ping 失败则回退签名 Cookie Session，注释写明是为了「让新贡献者可以零基础设施启动」 |
| `routes.chat()` 的 `error` 事件 | 模型失败时仍以 SSE 返回友好文案，不抛 500 |

## 放弃的方案

- **把记忆/历史做成强依赖（失败即报错）**：会让一次数据库抖动直接打断上课；与「AI 对话是唯一主链路」的判断冲突。
- **引入重试队列或任务框架**：仓库中没有 Celery/队列等基础设施，为辅助功能引入它会显著提高部署门槛（见 [architecture.md](../architecture.md) 第 10 节约束 4）。
- **feature flag 全链路预检**：未实现；当前用环境变量总开关（`AITEACHER_MEMORY`、`AITEACHER_CHAT_HISTORY`）承担同等角色。

## 影响与代价

- 正面：单机、无 Redis、无既有聊天表的环境下产品依然可跑；故障影响面被限制在单个功能。
- 代价：**静默失败难以察觉** —— 历史或记忆可能长期没在写，只有日志知道；因此新增辅助能力时必须同时给出可观测手段（`GET /aiteacher/api/memory` 的 `enabled` 字段即是这类自检出口），并在日志里留下明确 warning。后台 daemon 线程无重试，进程回收即丢任务。
