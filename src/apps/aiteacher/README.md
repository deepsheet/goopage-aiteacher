# A教师（aiteacher）

A教师是 goodpage 的独立子产品。页面由左侧 AI 对话区与右侧学习区组成；每次对话都会把右侧当前课程、可见文字、孩子刚才的操作、已拼表达和学习偏好一并传给 AI，因此老师能持续承接屏幕上的教学变化。

## 路由

- `GET /aiteacher/`：课堂页面
- `GET /aiteacher/api/course`：当前体验课结构
- `POST /aiteacher/api/chat`：SSE 流式 AI 对话
- `POST /aiteacher/api/asr`：浏览器录音转文字

## 目录

- `course.py`：课程内容和教师系统规则
- `routes.py`：页面、对话和语音接口
- `voice.py`：服务端 ASR 客户端
- `templates/aiteacher/index.html`：课堂结构
- `static/app.css`：响应式视觉样式
- `static/app.js`：课程状态、上下文联动、录音和流式对话

## 首个体验课

“把想法说出来”以功能性沟通为目标，包含选择、请求、拒绝/求助和轮流四站。设计默认接受口语、发声、手势、点选和图片沟通，不强迫对视或复述，也不把产品描述为自闭症治疗或治愈工具。

学习进度和偏好仅在当前浏览器的 `localStorage` 中持久化；偏好会在对话时作为课堂上下文发送给服务端和模型，但服务端不另行保存。聊天历史目前仅保留在页面内存中，刷新后不会恢复。后续接入账号课程库时，可以保持 `page_context` 协议不变，将课程来源替换为数据库或外部接口。

## 配置

文字对话复用 goodpage 的 `LLMClient`。语音识别优先使用 `DASHSCOPE_API_KEY` 和 `DASHSCOPE_BASE_URL`；未配置时会回退到非 token-plan 的 Qwen 公共端点配置。老师发声使用浏览器原生 `speechSynthesis`，避免再增加一条服务端 TTS 依赖。
