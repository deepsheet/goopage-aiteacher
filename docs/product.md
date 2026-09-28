# 产品说明（product）

> 本文是「做什么、为谁做、遵循哪些业务规则」的唯一事实源。系统结构见 [architecture.md](architecture.md)，接口见 [api.md](api.md)。
> 每条能力都标注证据来源；`待确认` 表示仓库中尚无可验证实现或结论。

## 1. 产品定位

AI Teacher 是一个**能感知学习内容的 AI 陪练课堂**：学习材料显示在右侧，老师在左侧陪练，老师每一轮都能看到学生此刻在屏幕上做什么、做到哪一步、刚才怎么回应。它把「阅读材料」和「有人陪着练」合并成一个页面，用于自学与在真人老师/照护者陪同下练习。

来源：`README.md`、`src/apps/aiteacher/course.py`、`src/prompts/teacher.py::CORE_ROLE`、`src/apps/aiteacher/static/app.js`。

**项目缘起**：本模块最初作为 GoodPage 多子应用框架下的一个子产品孵化（同框架另有「人人传记」子产品），沿用其 Flask 蓝图、账户、会话、i18n 与服务层骨架；如今已可独立运行，并在其上完整实现了对话、语音、教材、记忆与历史能力（框架遗留部分见 [architecture.md](architecture.md) 第 1 节）。内置示范课是一节面向自闭症儿童、神经多样性友好（neurodiversity-affirming）的功能性沟通体验课，**本产品是学习陪练工具，不用于诊断、治疗或替代专业支持**。

## 2. 目标用户（代码中可确认的角色）

| 角色 | 证据 |
|---|---|
| 学习者（含自闭症、语言障碍、英语学习者） | 内置课件 `src/apps/aiteacher/builtin_materials/functional-communication-starter.html`、`nce1-lesson1-handbag.html`；`course.py::DEMO_COURSE.principles` |
| 照护者 / 真人老师 | `routes.py::_parse_nudge_decision` 的 `handoff: 'caregiver'`；`course.py` 每站 `coach_note`（「带着练…」） |
| 注册用户 | `src/account/`（MySQL `sys_user`）、`materials.py::safe_owner_name` 以用户名建目录 |
| 未登录访客 | `routes.py::_current_material_owner` 生成 `guest-<会话编号>` 隔离目录 |

待确认：是否存在面向机构/多位学生集中管理的角色（仓库无相关代码）。

## 3. 解决的用户问题

- 独自看材料时没人提问、没人纠错；AI 通用助手又看不到学生此刻在学什么。
- 语言障碍儿童需要**低压力、可等待、接受非口语回应**的反复练习，而这类练习需要成人现场陪坐。
- 老师手工准备互动课件成本高：需要把学习目标快速变成一个可操作的网页。

## 4. 产品目标

1. 让模型基于「当前屏幕状态 + 操作历史 + 记忆」作答，而不是通用问答。
2. 让一份课件自带它自己的教学规则与交互能力，公共层不需要认识具体课件（见 [ADR-001](decisions/ADR-001-courseware-declares-its-own-capabilities.md)）。
3. 用得越久越贴合本人：跨会话记住称呼、表达方式、薄弱点与进度（`memory.py`）。
4. 任何辅助功能都不许打断对话主链路（见 [ADR-002](decisions/ADR-002-graceful-degradation-for-auxiliary-features.md)）。

## 5. 非目标

- **不做诊断、治疗或专业支持的替代**（`README.md`、本目录早期单页设计文档与 `course.py` 原则均明确此点）。
- 不强迫对视、不强迫复述，不把安静或回避当作不配合，接受近似发音（`course.py::principles`）。
- 不做通用聊天机器人、内容社区或课程分发平台：一切功能围绕「一份材料 + 一位老师」。
- 不在服务端保存学习偏好：偏好只存浏览器 `localStorage`（`static/app.js::persistState`）。
- 不做实时音视频课堂，不做多人同时协作。

## 6. 核心功能

| 功能 | 状态 | 证据 |
|---|---|---|
| 上下文感知 SSE 流式对话 | 已实现 | `routes.py::chat`、`_chat_messages` |
| 学习区状态上报（课程、屏幕文字、刚才的操作、已拼表达、偏好） | 已实现 | `src/apps/aiteacher/static/app.js`、`_hydrate_material_context` |
| 三层记忆（用户/教材/产品）提炼与注入 | 已实现 | `memory.py`、`src/prompts/memory_extractor.py` |
| 聊天历史持久化与恢复 | 已实现 | `chat_store.py`、`GET /aiteacher/api/chat/history` |
| AI 生成自包含 HTML 课件 | 已实现 | `materials.py::create_generated_material` |
| 导入网页为本地快照 | 已实现 | `materials.py::create_url_material` |
| 上传 HTML/Markdown/TXT | 已实现 | `materials.py::create_uploaded_material` |
| 内置教程库 | 已实现 | `builtin_materials.py::BUILTIN_CATALOG`（当前 2 课） |
| 课件双向联动（高亮、`hint`/`reveal`/`step`） | 已实现 | [material-protocol.md](material-protocol.md)、`material_bridge.py`、`material_manifest.py` |
| 录音转文字（ASR） | 已实现 | `voice.py::transcribe` |
| 服务端语音合成（TTS，多音色、失败回落） | 已实现 | `voice.py::synthesize`、`GET /aiteacher/api/tts/voices` |
| 主动等待判定（沉默时该不该开口） | 已实现，**默认关闭** | `routes.py::nudge`、`app.js` 初始 `proactiveWait: false` |
| 注册 / 登录 / 免密老账号兼容 | 已实现 | `src/account/` |
| 移动端自适应 | 已实现 | `src/apps/aiteacher/static/app.css`（4 处 `@media`） |
| 多语言界面 | 部分实现 | `src/i18n/` 仅用于账户文案；课堂提示词与界面为中文（`LLMClient(language='zh')`） |
| 对象存储（OSS）落盘 | 未启用 | `config/config.py::STORAGE_CONFIG['backend'] = 'disk'`，且课堂业务走 `materials.py` 本地目录 |
| 访客数据并入正式账号 | 未实现 | 待确认：仓库中没有 owner 合并逻辑 |

## 7. 关键业务规则

**教学与安全**
- 内置示范课《把想法说出来》共 **5 站**：选择 → 请求 → 拒绝/求助（`boundaries`）→ 轮流 → 开口说（`course.py::DEMO_COURSE.lessons`）。
- 提示阶梯「等待 → 指认 → 示范」，同一提问最多主动提示 `max_nudges`（默认 3）次，到顶即停止追问并把控制权交还照护者（`routes.py::_parse_nudge_decision`）。
- 主动等待判定的所有异常一律「继续等待、先不说话」（`_nudge_wait`）：判定失败时宁可安静。
- 高频小事件不得召唤模型，只在关键节点召唤（[material-protocol.md](material-protocol.md) 第 4 节）。

**限制与配额**
- 单条用户消息 ≤1200 字，学习区上下文 ≤16000 字，回传历史 ≤16 条（`routes.py` 顶部常量）。
- 上传/抓取单文件 ≤5MB，提取正文 ≤30000 字，录音 ≤12MB，TTS 单次文本 ≤4000 字，生成需求 ≤6000 字。
- 生成整页课件的最大输出 token 默认 30000（`AITEACHER_MATERIAL_MAX_TOKENS`）。
- 每类记忆最多保留 20 条、注入预算默认 2000 字，重复记忆以 `count` 累积置信。

**数据与身份**
- 一个用户 = 一个材料目录：登录用户用用户名，未登录用 `guest-<会话编号>`；登录后仍能看到登录前访客目录中的材料（`tests/smoke.py::test_login_does_not_hide_materials_created_in_guest_session`）。
- 一个「用户 + 教程」= 一个聊天会话，会话号确定性生成（见 [ADR-003](decisions/ADR-003-deterministic-chat-session-id.md)）。
- 记忆与聊天历史在服务端 MySQL；学习偏好只在浏览器本地。

**内容信任**
- 第三方来源（上传/导入）的课件只当数据，其 `teacher_notes` 与 `command_guide` 不进入系统提示词（`material_manifest.py`、[security.md](security.md)）。

## 8. 成功指标

仓库中没有埋点、指标计算或监控代码，因此无「已实现的成功指标」。历史上唯一量化过的实测结论是：模型对课件操作指令的遵从率约 50%（[material-protocol.md](material-protocol.md) 第 9 节），据此要求「能本地确定性做到的事不依赖模型」。

待确认：产品上线后打算用哪些指标衡量效果（对话轮次？完课率？主动提示命中率？）。

## 9. 待确认问题

1. 目标用户是否包含机构/特教学校场景，需要班级或多学生管理？
2. 是否计划开放非中文课堂（`src/i18n/` 目前只服务账户模块）？
3. 访客 → 登录账号的记忆与材料合并策略。
4. 商业边界：是否有配额、付费或并发上限的产品计划（当前只有技术限制）。
5. 开源许可证选择（根目录无 `LICENSE`）。
