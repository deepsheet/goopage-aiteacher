# ADR-001：课件自己声明交互能力，公共层不认识具体课件

- 状态：已采用
- 记录日期：2026-09-27（决策本身早于此，本文是在代码与 `docs/material-protocol.md` 已成事实后补记）

## 背景

课堂右侧的学习区同时承载四类来源的内容：仓库内置教程、模型生成的 HTML 课件、导入的网页快照、用户上传的文档。它们支持的交互差别很大：内置教程可以高亮、揭示答案、跳环节；一份导入的课文网页只该被高亮，甚至什么都不支持。

如果把这些差异写进服务端提示词或前端逻辑（例如「如果是新概念英语就怎么做」），会带来两个后果：每加一份课件都要改公共代码；不可信来源的文本会顺着这条通道把指令塞进系统提示词。

## 决策

把「这份课件能做什么、老师该怎么带这一课」写进课件自己：课件 HTML 内放一段 `<script type="application/aiteacher+json">` 作为 manifest，服务端解析后按来源做信任分级，再决定哪些内容可以进入提示词。公共层（提示词、路由、前端）不保留任何具体课件的学科知识。

## 依据

| 证据 | 说明 |
|---|---|
| `src/apps/aiteacher/material_manifest.py` | 独立模块负责解析 manifest；`TRUSTED_NOTE_SOURCES = frozenset({'builtin', 'generated'})` |
| `material_manifest.manifest_bits()` 文档串 | 「不可信来源只保留 commands，自由文本一律丢弃」 |
| `src/prompts/teacher.py::MATERIAL_COMMANDS` | 指令名注册表（`hint`/`reveal`/`step`），是公共层与课件之间的**唯一**契约 |
| `src/apps/aiteacher/routes.py::_trusted_bits()` 文档串 | 「未注册的名字在此丢弃，模型就收不到该语法，也就不会输出课件执行不了的指令」 |
| `src/apps/aiteacher/routes.py::_hydrate_material_context()` | 先删掉前端提交的 `material_bits`，只信服务端从落盘文件派生的值 |
| `src/apps/aiteacher/material_bridge.py` | 服务端向课件注入桥接脚本，课件不需要引任何外部资源 |
| `docs/material-protocol.md` | 协议正文；其设计前提即「公共层不认识具体课件」 |
| `src/apps/aiteacher/builtin_materials/*.html` | 两份内置课件各自内嵌自己的 manifest，可作为写法样板 |

## 放弃的方案

- **在服务端按课件 id 分支写提示词**：改一份课件要动核心路由，且难以审计；放弃。
- **让前端把课件说明直接带上来**：等于把提示词注入面开放给不可信内容；已被 `_hydrate_material_context()` 的丢弃逻辑明确否定。
- **让课件自行调用模型**：会绕开服务端上下文组装与记忆，也需要把密钥暴露到浏览器；未采用。

## 影响与代价

- 正面：新增课件是纯内容工作，不触碰公共代码；提示注入面收敛为「指令名白名单 + 限长自由文本」。
- 代价：模型是否真的发出指令仍不稳定（`docs/material-protocol.md` 第 9 节记录的遵从率问题），因此交互不能只押在指令上；manifest 语法是自定义协议，需要文档与样板课件配合才能被正确写出。
