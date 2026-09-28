# 文档索引
12
本目录是 AI Teacher 的**长期事实文档**。每类信息只在一处权威维护，其它地方只做摘要并链接过来。写作与维护规则见根目录 [AGENTS.md](../AGENTS.md)，项目入口见 [README.md](../README.md)。

## 阅读顺序

| 文档 | 回答什么问题 | 谁最该读 |
|---|---|---|
| [product.md](product.md) | 做什么、为谁做、业务规则、非目标 | 所有人，改功能前先读 |
| [architecture.md](architecture.md) | 系统现在由哪些部件组成、数据怎么流、有什么约束与技术债 | 改动跨模块代码前 |
| [development.md](development.md) | 环境、配置项、启动、测试命令、常见开发问题 | 每次搭环境、提交前 |
| [deployment.md](deployment.md) | 发布流程、运行时配置、迁移、验证、回滚、生产限制 | 碰部署脚本与服务器前 |
| [api.md](api.md) | HTTP 接口清单与请求/响应契约 | 前后端联调 |
| [database.md](database.md) | 表结构、文件模型、命名约定、数据生命周期 | 改数据读写 |
| [security.md](security.md) | 威胁模型、沙箱与注入防线、密钥与隐私处置、上线检查 | 改认证/外呼/存储/日志 |
| [material-protocol.md](material-protocol.md) | 课件与聊天区的交互协议（自定义协议正文） | 写或改课件 HTML |
| [decisions/README.md](decisions/README.md) | 重要技术选择的原因与代价（ADR） | 想「为什么不用 X」时 |

任务级短期状态不在本目录，在 [../tasks/README.md](../tasks/README.md)。

## 职责边界（避免写重复）

| 类型 | 权威位置 | 其它位置如何处理 |
|---|---|---|
| 项目一句话介绍、能力清单、快速开始 | 根 `README.md` | 只链接 |
| Agent 可做什么/禁止什么 | 根 `AGENTS.md` | 只链接 |
| 业务规则与产品边界 | `product.md` | 摘要 + 链接 |
| 组件、数据流、约束、技术债 | `architecture.md` | 摘要 + 链接 |
| 可执行命令与配置项 | `development.md` | 只写用到的那条 |
| HTTP 契约 | `api.md` | 不复述字段表 |
| 表结构与文件模型 | `database.md` | 只写归属 |
| 决策论证 | `decisions/ADR-*.md` | 正文只写结论 |

## 为什么没有 testing / troubleshooting / operations 单独成文

测试命令与实测结论在 [development.md](development.md) 第 5 节，常见问题在其第 8 节，发布后验证与回滚在 [deployment.md](deployment.md) 第 6-7 节。当前内容规模不需要再拆分；等某块内容明显超出宿主文档的可读性时再拆，并在本页登记。

## 维护规则

1. 一项事实只在一处维护；发现重复就以本表的归属为准删减并改成链接。
2. 命令、配置项、接口、表结构必须来自真实代码或已执行验证；凭经验写的改为「待确认」。
3. 代码与文档冲突时**先改文档**；无法判定谁对时，在对应文档标「待确认」，不要静默选一个。
4. 移动或重命名文档前先搜引用，用 `git mv`，随后修全部链接并跑校验。
5. 新增文档要在本页索引表登记，否则视为孤儿文档。
6. 不写入密钥、Token、真实服务器地址、`data/users/` 下的用户内容。

## 校验

```bash
python3 ~/.qoder/skills/project-docs-architect/scripts/validate_docs.py .
```

检查必需文档是否存在、相对链接与引用的本地路径是否有效、是否残留脚手架占位符、以及从 `README.md` 出发是否可达主要文档。退出码非 0 表示有 error 级问题。
