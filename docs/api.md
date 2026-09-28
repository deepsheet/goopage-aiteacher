# HTTP 接口（api）

> 本文是接口清单与契约的**唯一权威来源**。所有条目直接读自 `src/web_server.py`、`src/apps/aiteacher/routes.py`、`src/account/routes.py`，不含推测。

## 1. 约定

- Blueprint 前缀：课堂 `/aiteacher`，账户 `/account`，应用级路由无前缀。
- 请求体除上传外均为 JSON；响应统一带 `success: true|false`，失败时带中文 `error` 字段。
- 材料归属由会话推导（`routes._current_material_owner()`）：登录用户为 `safe_owner_name(username)`，未登录为 `guest-<16位hex>`。**接口没有强制登录要求**，详见 [security.md](security.md)。
- 长度上限（`routes.py` 顶部常量）：单条用户输入 `MAX_MESSAGE_CHARS = 1200`，上下文总量 `MAX_CONTEXT_CHARS = 16000`，取用的历史条数 `MAX_HISTORY_ITEMS = 16`。
- CORS 仅对 `/api/*` 前缀放开 `origins: "*"`（`src/web_server.py`）；`/aiteacher/api/*` 与 `/account/api/*` 不在该前缀下，属同源。

## 2. 应用级

| 方法与路径 | 说明 |
|---|---|
| `GET /` | 宣传首页，渲染 `src/templates/home.html` |
| `GET /study` | AI 课堂主页，直接渲染 `src/apps/aiteacher/templates/aiteacher/index.html` 并注入 `DEMO_COURSE` |
| `GET /health` | 探活，返回 `{"app": "aiteacher", "status": "ok"}` |
| `GET /favicon.ico` | 站点图标 |

## 3. 课堂 `/aiteacher`

### 3.1 页面与预览

| 方法与路径 | 说明 |
|---|---|
| `GET /aiteacher/` | 课堂入口页（与 `/study` 同一模板） |
| `GET /aiteacher/materials/<material_id>` | 沙箱预览用户材料。响应头 `Cache-Control: private, no-store`，CSP `sandbox allow-scripts allow-forms; default-src 'none'; …; connect-src 'none'; frame-src 'none'; form-action 'none';` |
| `GET /aiteacher/builtins/<material_id>` | 沙箱预览内置教程。`Cache-Control: public, max-age=300`，CSP 更严（无 `allow-forms`，`img-src data:`） |

预览页会被注入桥接脚本（`material_bridge.inject_bridge`），桥接与指令协议见 [material-protocol.md](material-protocol.md)。

### 3.2 对话

`POST /aiteacher/api/chat` —— **SSE 流式**（`text/event-stream`，`Cache-Control: no-cache`，`X-Accel-Buffering: no`）。

请求体：

| 字段 | 类型 | 说明 |
|---|---|---|
| `message` | str | 本轮用户输入，超 1200 字符会被截断 |
| `history` | list | 前端持有的历史；服务端最终只取最近 16 条 |
| `page_context` | object | 学习区状态：`builtin_id` / `material_id`、`course_title`、`lesson_title`、`goal`、`visible_text`、`last_action`、`preferences` 等 |
| `material_bits` | object | **会被服务端丢弃并重建**，见下 |

服务端处理顺序：`_hydrate_material_context()` 先删除前端伪造的 `material_bits`，再从落盘文件读取权威正文与 manifest；然后加载记忆、`build_system_prompt()` 拼装、以 `temperature=0.45` 请求流式接口。

事件序列：

| 事件 | 载荷 |
|---|---|
| `ready` | `{"type":"ready"}` |
| `delta` | `{"type":"delta","text":"…"}` 逐字片段 |
| `done` | `{"type":"done","text":"完整回复"}`，随后触发后台保存历史与记忆提炼 |
| `error` | `{"type":"error","message":"AI老师暂时没有连上，请稍后再试。"}` |

模型返回空内容也走 `error`。材料已不可用时在建立流之前返回 `400`。

`POST /aiteacher/api/nudge` —— 孩子沉默后的「该不该主动开口」判定。

请求体：`page_context`、`silence`（`since_prompt_s`、`since_ai_done_s`、`since_any_action_s`、`nudge_count`）、`engagement`（`last_action`、`constructed_phrase`、`baseline_latency_ms`、`partial_attempt`、`answered_last_turn`）。

响应：`{success, should_speak, level(0-4), text(≤160字), await_reply, next_check_in_ms, handoff}`。

行为约束（`_parse_nudge_decision` / `nudge`）：

- `nudge_count >= max_nudges`（默认 3，可用 `config.PROACTIVE_CONFIG` 覆盖，clamp 到 1-8）时**不再问孩子**，直接返回 `should_speak=false`、`handoff='caregiver'`、`await_reply=false`。
- `handoff` 只接受 `caregiver` / `break`，其它值归一为 `null`。
- `text` 为空则强制 `should_speak=false`。
- 模型调用失败、JSON 解析失败、材料不可用 → 一律返回「继续等待」的安全默认（`success=false`，`next_check_in_ms` 取 `base_delay_ms` clamp 到 4000-30000）。
- `next_check_in_ms` clamp 到 `[min_check_ms, max_check_ms]`（默认 4000 / 30000）。

### 3.3 历史与记忆

| 方法与路径 | 说明 |
|---|---|
| `GET /aiteacher/api/chat/history?doc_id=` | 该用户 × 该教程的历史消息，时间正序；`doc_id` 截断至 80 字符，缺失时返回空数组 |
| `GET /aiteacher/api/memory` | `{success, enabled, profile}`，`profile` 为 user 层画像 |
| `DELETE /aiteacher/api/memory` | 清除当前 owner 的 user 层记忆，返回 `{success}` |

### 3.4 学习材料

| 方法与路径 | 说明 |
|---|---|
| `POST /aiteacher/api/material/generate` | `{requirement}` → 模型产出自包含 HTML 课件；`MaterialError` → 400，其它异常 → 502 |
| `POST /aiteacher/api/material/url` | `{url}` → 抓取网页存为快照；URL 校验失败 → 400，连不上 → 502（策略见 [security.md](security.md)） |
| `POST /aiteacher/api/material/upload` | `multipart/form-data`，字段名 `file`；扩展名限 `.html/.htm/.md/.markdown/.txt`，≤ 5MB，超限 → 400 |
| `GET /aiteacher/api/materials` | 已保存材料列表（按 `created_at` 倒序，**最多 50 条**），并回显 `storage_path` / `storage_paths` |
| `GET /aiteacher/api/materials/<material_id>` | 单个材料详情 |
| `GET /aiteacher/api/builtin-materials` | 内置教程列表 |
| `GET /aiteacher/api/builtin-materials/<material_id>` | 单个内置教程；不存在 → 404 |
| `GET /aiteacher/api/course` | `{success, course: DEMO_COURSE}`，课件加载失败时的降级展示数据 |

材料详情响应字段（`_material_payload`）：`id`、`title`、`source_type`、`source_label`、`original_name`、`text`、`created_at`、`commands`、`viewer_url`；内置教程额外含 `subtitle`、`description`、`duration`，且 `source_type` 固定为 `builtin`。列表项为精简版（`_material_summary_payload`，不含 `text`/`commands`/`viewer_url`）。

### 3.5 语音

| 方法与路径 | 说明 |
|---|---|
| `POST /aiteacher/api/asr` | `multipart/form-data`，字段名 `audio`；≤ 12MB（超出 → 413），空 → 400，转写失败 → 502，成功返回 `{success, text}` |
| `POST /aiteacher/api/tts` | `{text(≤4000字), voice}` → `{success, clips, requested_voice, voice, degraded}`；`clips` 是 base64 data URI 列表，失败 → 502 |
| `GET /aiteacher/api/tts/voices` | `{success, default, voices[]}`，每项含 `code`、`name`、`gender`、`desc`，可能带 `unstable` |

TTS 语义要点：`voice.DEFAULT_VOICE = 'Serena'` 是服务端默认音色；`voice.FALLBACK_QWEN_VOICE = 'Cherry'` 只在 VoxCPM2 不可用时作为 Qwen 回退音色，**不下发给前端**。`degraded=true` 表示服务端不得已换了说话人，前端需提示用户。`unstable` 表示该音色锁不住说话人。音色对象的 `design` 字段是服务端内部提示词，刻意不下发。

## 4. 账户 `/account`

| 方法与路径 | 说明 |
|---|---|
| `GET /account/login` · `GET /account/register` | 登录 / 注册页面 |
| `POST /account/api/register` | 注册，写入 MySQL `sys_user` |
| `POST /account/api/login` | 登录，支持用户名或邮箱 |
| `GET /account/api/logout` | 登出 |
| `GET /account/api/check_login` | 会话有效性 |
| `GET /account/api/profile` | 当前用户资料 |
| `POST /account/api/set_password` | 修改密码 |
| `GET /account/static/<path:filename>` | 模块静态资源 |

## 5. 错误与返回码速查

| 场景 | 位置 | 状态码 |
|---|---|---|
| 材料已不可用 | `chat`、`saved_material`、`view_material` | 400 / 404 |
| 用户输入为空 | `chat` | 400（`请说点什么或输入一段话`） |
| 模型调用失败 | `generate_material`、`material_from_url`、`asr`、`tts` | 502 |
| 上传缺文件 / 超限 | `upload_material`、`asr` | 400 / 413 |
| 读盘异常 | `saved_materials` | 500 |

`nudge` 是唯一**不返回错误状态码**的接口：任何异常都降级为 200 + 安全默认判断。
