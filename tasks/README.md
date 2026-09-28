# 任务记录（tasks）

本目录记录**短期工作状态**：谁在做什么、做到哪、怎么验证、下一步是什么。它与长期文档的分工：

| 内容 | 归属 |
|---|---|
| 系统现在的结构 | [../docs/architecture.md](../docs/architecture.md) |
| 为什么这样选 | [../docs/decisions/README.md](../docs/decisions/README.md) |
| 执行规则与禁止事项 | [../AGENTS.md](../AGENTS.md) |
| 某件事此刻的进展 | 本目录 |

任务完成后，**结论要沉淀到长期文档**，任务文件本身留在目录里作为过程记录；不要把它当成第二份架构文档长期维护。

## 使用方式

1. 新任务：复制 [templates/task-template.md](templates/task-template.md)，命名 `YYYYMMDD-短横线英文名.md`（例：`20260926-tts-voice-pinning.md`）。
2. 一次任务只有一份权威文件；进度更新直接改原文件，不要另开副本。
3. 「基准提交」填创建任务时的 `git rev-parse --short HEAD`，用于日后判断代码是否已经走偏。
4. 需要交给另一台机器上的 Agent 继续时，用 [templates/handoff-template.md](templates/handoff-template.md) 写交接说明，并把它链接到任务文件的「交接」一节。
5. 状态取值统一为：`待开始` / `进行中` / `等待交接` / `阻塞` / `已完成` / `已废弃`。

## 硬性约定

- 「验证结果」只能写**实际执行过的命令与输出结论**，不写「应该可以」。
- 「已知问题」里无法确认的部分标 `待确认`，不要猜测成因。
- 任务文件里不写密钥、Token、真实服务器地址、用户数据内容（`data/users/` 下的材料一律不复制进来）。
- 不要在仓库里留下「当前正在进行」的虚构任务；本目录初始状态只有说明与模板。

## 索引

| 文件 | 状态 | 说明 |
|---|---|---|
| [templates/task-template.md](templates/task-template.md) | 模板 | 新任务从这里复制 |
| [templates/handoff-template.md](templates/handoff-template.md) | 模板 | Mac ↔ 服务器 Agent 交接格式 |

（暂无进行中的任务记录。）
