# AI Teacher

一个能感知学习内容的 AI 陪练课堂：左侧是支持文字、录音转写与真人语音的老师，右侧是可交互的学习内容（内置教程、AI 生成的 HTML 课件、导入的网页快照或上传的文档）。每一轮对话都会把当前课程、屏幕可见文字、学生刚才的操作和学习偏好一并送给模型，老师因此能承接屏幕上正在发生的事。

## 项目状态

- 已可独立运行：Flask 单应用 + MySQL + Redis（Redis 缺失时回退签名 Cookie Session）。
- 内置示范课《把想法说出来（语言障碍恢复）》与《新概念英语 Lesson 1》。产品定位是**学习陪练工具，不用于诊断、治疗或替代专业支持**。
- 生产部署为一台**与其他站点共享的服务器**（多站点共用 gunicorn），运维改动有连带风险，见 [AGENTS.md](AGENTS.md) 与 [docs/deployment.md](docs/deployment.md)。
- 仓库未预设开源许可证；正式开源前需按授权意图补 `LICENSE`。

## 核心能力（均可在代码中定位）

- 上下文感知对话：`src/apps/aiteacher/routes.py::_chat_messages`，SSE 流式返回
- 三层记忆（用户 / 教材 / 产品）自动提炼与注入：`src/apps/aiteacher/memory.py`、`src/prompts/memory_extractor.py`
- 聊天历史按「用户 + 教程」持久化并可恢复：`src/apps/aiteacher/chat_store.py`
- 课件生成、网页导入（含 SSRF 校验）、文件上传与本地落盘：`src/apps/aiteacher/materials.py`
- 课件与聊天区双向联动（高亮、提示、公布答案、跳关）：[docs/material-protocol.md](docs/material-protocol.md)
- 服务端语音识别与语音合成（多音色、失败回落并如实告知）：`src/apps/aiteacher/voice.py`
- 主动等待判定：孩子沉默时由模型决定该不该开口、要不要继续等：`POST /aiteacher/api/nudge`
- 账户注册/登录（MySQL `sys_user`）与访客隔离目录：`src/account/`

## 技术栈

Python 3.9+ · Flask（Blueprint）+ Flask-Cors + Flask-Session · Redis（可选）· MySQL（PyMySQL）· Gunicorn + gevent · DeepSeek / 阿里云百炼 Qwen（对话）、DashScope（ASR/TTS）、ModelBest VoxCPM2（可选真人音色）。依赖清单见 `requirements.txt`。

## 快速开始

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config/config_local.example.py config/config_local.py   # 填入 API Key
python app.py                                              # http://localhost:5058/
```

宣传首页 `http://localhost:5058/`，课堂 `http://localhost:5058/study`。不配置密钥也能浏览和操作课程；文字对话需要模型 Key，语音需要 `DASHSCOPE_API_KEY`。完整环境要求、配置项、测试命令与常见开发问题见 [docs/development.md](docs/development.md)。

## 文档

| 文件 | 内容 |
|---|---|
| [AGENTS.md](AGENTS.md) | 编码 Agent 的仓库工作合同：命令、权限边界、禁止操作 |
| [docs/README.md](docs/README.md) | 文档索引与阅读顺序 |
| [docs/product.md](docs/product.md) | 产品定位、目标用户、核心功能与业务规则 |
| [docs/architecture.md](docs/architecture.md) | 组件、数据流、外部依赖、存储与技术约束 |
| [docs/development.md](docs/development.md) | 已验证的本地开发、配置与测试命令 |
| [docs/deployment.md](docs/deployment.md) | 环境划分、发布流程、探活与生产边界 |
| [docs/api.md](docs/api.md) | HTTP 接口与对话请求/响应约定 |
| [docs/database.md](docs/database.md) | 数据表、文件落盘结构与建表方式 |
| [docs/security.md](docs/security.md) | 信任边界、CSP 沙箱、SSRF、密钥与 PII |
| [docs/material-protocol.md](docs/material-protocol.md) | 课件交互协议（唯一接口规范） |
| [docs/decisions/](docs/decisions/README.md) | 架构决策记录（ADR） |
| [tasks/](tasks/README.md) | 任务记录与 Mac ↔ 服务器 Agent 交接模板 |
