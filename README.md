# AI Teacher

一个可感知学习内容的 AI 陪练课堂。左侧是支持文字、录音和语音播报的 AI 老师，右侧是可交互的学习内容；每轮对话都会携带当前课程、屏幕文字、学习操作和偏好，让老师能够承接学生正在做的事。

项目来自 GoodPage 的多子应用框架，核心代码位于 `src/apps/aiteacher`。当前首页内置“把想法说出来”功能性沟通体验课，用于演示选择、请求、拒绝/求助和轮流表达。它是学习陪练工具，不用于诊断、治疗或替代专业支持。

## 功能

- AI 对话会实时读取右侧学习区上下文
- 输入学习目标，由 AI 生成并保存独立 HTML 教学网页
- 导入公网或本机 HTTP/HTTPS 网页，并保存为可阅读的本地快照
- 上传 HTML、Markdown、TXT 学习材料（单文件最大 5MB）
- 支持 SSE 流式回复、浏览器语音播报和录音转文字
- 四阶段互动体验课，接受口语、手势、点选和图片沟通
- 安静模式、语速和表达偏好设置
- 桌面与移动端自适应
- Redis 未启动时自动使用 Cookie Session，首页可零基础设施运行

## 快速开始

要求 Python 3.9+。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config/config_local.example.py config/config_local.py
python app.py
```

打开 [http://localhost:5058/](http://localhost:5058/)。不配置 AI Key 也可以浏览和操作课程；文字对话和语音识别需要配置相应服务。

开发模式也可以运行：

```bash
./start_dev.sh
```

## 配置

`config/config.py` 保存可提交的公共默认配置。若存在 `config/config_local.py`，其中的同名变量会覆盖公共配置；这个本地文件已被 Git 忽略。

```python
# config/config_local.py
CURRENT_MODEL = 'deepseek'
DEEPSEEK_API_KEY = 'your-key'

# 使用 Qwen 时：
# CURRENT_MODEL = 'qwen'
# QWEN_API_KEY = 'your-key'
# DASHSCOPE_API_KEY = 'your-key'  # 录音转文字，可选
```

生产环境还应设置稳定的 `SECRET_KEY`：

```bash
export SECRET_KEY='replace-with-a-long-random-value'
```

学习材料默认保存在项目的 `data/users/<用户名>/` 下；未登录访客使用独立的 `guest-<会话编号>` 目录。可以用环境变量修改存储根目录：

```bash
export AITEACHER_DATA_ROOT='/path/to/data/users'
```

## 项目结构

```text
.
├── app.py                         # 开发启动入口，默认 5058
├── config/
│   ├── config.py                  # 可提交的公共配置
│   └── config_local.example.py    # 本机配置模板
├── src/
│   ├── web_server.py              # Flask 应用与蓝图注册
│   ├── account/                   # 通用账户模块
│   ├── services/                  # 文件存储与内容提取
│   └── apps/aiteacher/
│       ├── course.py              # 体验课内容与教学规则
│       ├── materials.py           # 学习材料生成、抓取、提取与落盘
│       ├── routes.py              # 页面、对话与 ASR 接口
│       ├── voice.py               # 录音转文字客户端
│       ├── static/                # 页面 CSS / JavaScript
│       └── templates/             # 课堂模板
└── requirements.txt
```

## HTTP 路由

| 路由 | 说明 |
|---|---|
| `GET /` | AI Teacher 首页 |
| `GET /health` | 无外部依赖的健康检查 |
| `GET /aiteacher/` | AI Teacher 子应用入口 |
| `GET /aiteacher/api/course` | 当前体验课数据 |
| `POST /aiteacher/api/material/generate` | 根据需求生成 HTML 课件 |
| `POST /aiteacher/api/material/url` | 导入公网或本机网页 |
| `POST /aiteacher/api/material/upload` | 上传 HTML、MD 或 TXT 文件 |
| `GET /aiteacher/materials/<id>` | 沙箱预览本地学习材料 |
| `POST /aiteacher/api/chat` | SSE 流式 AI 对话 |
| `POST /aiteacher/api/asr` | 浏览器录音转文字 |

## 测试

```bash
python -m unittest src.apps.aiteacher.tests.smoke -v
```

## 开源准备

提交前请确认 `config/config_local.py`、`.env`、日志和用户文件没有进入版本控制。仓库目前未预设开源许可证；正式发布前请根据你的授权意图添加 `LICENSE`（例如 MIT、Apache-2.0 或 GPL-3.0）。
