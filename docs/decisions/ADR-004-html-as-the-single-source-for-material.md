# ADR-004：课件内容以 HTML 文件为唯一事实源，JSON 只存元数据

- 状态：已采用
- 记录日期：2026-09-27（补记，落盘逻辑与旧文档描述一致）

## 背景

一份学习材料同时需要两种表示：能在 iframe 里跑的**课件网页**，以及给模型看的**纯文本**与**能力清单**。如果三者各存一份，改一次课件就要同步三处，任何一处漏同步都会让 AI 讲的内容和屏幕上显示的内容不一致。

## 决策

磁盘上写一对文件：`<id>.html` 是**唯一的内容事实源**，`<id>.json` 只存标题、来源、`viewer_file`、`created_at` 等元数据。`text` 与 `manifest` 在 `load_material()` 读取时从 HTML 即时派生，**明确不落盘**。

## 依据

| 证据 | 说明 |
|---|---|
| `src/apps/aiteacher/materials.py::_persistable_metadata()` 文档串 | 「课件内容以 HTML 文件（viewer_file）为唯一事实源，JSON 只保留标题、来源与指向 html 文件的元数据；text 与 manifest 在读取时从 HTML 即时派生」 |
| `materials._write_material()` | 内存里的 metadata 含 `text`，写盘前经 `_persistable_metadata()` 剔除 `text` 与 `manifest`；创建响应才临时带回 `manifest`，注释说明是为了让前端刚拿到课件时不误判它不支持任何指令 |
| 本仓库旧版单页设计文档的第 5.2 节（已拆入本目录，内容并入 [database.md](../database.md) 第 6 节） | 「一份材料 = 一对文件……不再内嵌正文」 |
| `src/apps/aiteacher/material_manifest.py::parse_manifest()` | manifest 从 HTML 内的 `<script type="application/aiteacher+json">` 解析，派生而非存储 |
| `data/users/*/*.json`（本地实际数据） | 近期写入的 JSON 只有 `id/title/source_type/source_label/original_name/viewer_file/created_at`；早期文件仍残留 `text` 字段（改造前的历史数据，读取时不依赖它） |

## 放弃的方案

- **JSON 内嵌正文（早期形态）**：正文两份、必然漂移；且 AI 讲的可能是旧版本。已改为派生。
- **正文只存数据库**：材料天然就是可独立分发的 HTML，进库后要额外解决大字段、备份与迁移；当前也没有迁移工具。
- **只存 HTML 不存 JSON**：列表页需要标题/来源/时间，每次都解析整份 HTML 代价过高，故保留极小的元数据文件。

## 影响与代价

- 正面：不存在「屏幕与 AI 说法不一致」这类 bug；派生逻辑集中在读取路径，便于加缓存。
- 代价：读取路径比直读 JSON 重（要解析 HTML、跑 BeautifulSoup）；`data/users/` 是**未纳入版本控制的用户数据目录**，多实例部署需要共享磁盘，备份与迁移都得按文件处理（见 [deployment.md](../deployment.md) 第 7 节）。
