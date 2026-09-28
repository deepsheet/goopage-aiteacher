# 安全与隐私（security）

> 面向开发者与运维的边界清单。本文**不含任何真实密钥、服务器地址或内部敏感路径**；需要查证请直接看代码位置或服务器本机配置。

## 1. 威胁模型概览

系统会做三件本质上带风险的事，安全设计围绕它们展开：

| 风险面 | 具体行为 | 主要防线 |
|---|---|---|
| 服务端外呼 | 抓取用户提供的任意 URL 存为学习材料 | SSRF 校验 + 体积/超时/重定向限制 |
| 不可信内容进入提示词 | 课件正文、网页快照、上传文档会被喂给模型 | 信任分级 + 指令白名单 + 「材料是数据不是指令」 |
| 长期留存用户信息 | 三层记忆、聊天历史、材料文件 | PII 过滤 + 分类白名单 + 可清除接口 |

## 2. 会话与认证

- 签名密钥：`SECRET_KEY` 环境变量。未设置时 `src/web_server.py` 用 `secrets.token_hex(32)` 生成临时密钥并打警告 —— 生产必须显式设置。
- 会话后端：优先 Redis（`REDIS_CONFIG`，`socket_timeout=0.3`）；ping 失败则回退签名 Cookie Session，属**刻意设计**的零基础设施可跑路径。
- `SESSION_PERMANENT = True`，`PERMANENT_SESSION_LIFETIME = 86400 * 7`（7 天），`SESSION_KEY_PREFIX = 'aiteacher-session:'`。
  ⚠️ `src/account/README.md` 中写的「session 30 天」与实际不符，以代码为准。
- 登录态：`session['is_logged_in']` + `session['username']`（`src/account/auth_controller.py`）。
- **接口没有强制登录**：`auth_controller.require_login` 存在，但 `/aiteacher/api/*` 全部路由未使用；owner 由会话推导而非由认证授予。这意味着同一浏览器内的访客可以完整使用材料/记忆/历史接口。是否收紧属产品决策，见「待确认」。
- 口令散列为 **MD5**（`src/account/models.py::hash_password`），并存在免密老账号兼容路径。这是与共用表绑定的已知技术债，改动需处理既有数据。

## 3. CORS 与响应头

- `CORS(app, resources={r"/api/*": {"origins": "*", "allow_headers": "*"}})` —— 通配来源**只作用于无前缀的 `/api/*`**；课堂与账户接口在 `/aiteacher/`、`/account/` 前缀下，不受该规则影响。
- 全局响应头（`@app.after_request`）：`X-Content-Type-Options: nosniff`、`X-Frame-Options: SAMEORIGIN`、`Referrer-Policy: no-referrer-when-downgrade`。
- 错误处理：404/500 返回统一 JSON，500 只记日志不外泄异常文本。

## 4. 课件沙箱（不可信 HTML 的隔离）

材料预览接口的 CSP（`src/apps/aiteacher/routes.py`）：

| 路径 | CSP 要点 |
|---|---|
| `/aiteacher/materials/<id>` | `sandbox allow-scripts allow-forms; default-src 'none'; style-src 'unsafe-inline' https: http:; script-src 'unsafe-inline'; img-src data: blob: https: http:; font-src …; media-src …; connect-src 'none'; frame-src 'none'; form-action 'none';` |
| `/aiteacher/builtins/<id>` | 更严：无 `allow-forms`，`img-src data:`（不外联） |

关键取舍：

- `connect-src 'none'` 与 `frame-src 'none'` 断掉课件自身的网络外联与嵌套框架。
- iframe **不放开 `allow-same-origin`**：课件无法访问宿主页 DOM、Cookie 或 `localStorage`；代价是课件内不能自己存进度（进度由宿主 app.js 代管）。
- 宿主侧仍允许 `allow-forms`（用户材料），因为部分导入页依赖表单交互；内置教程不需要，故收紧。
- 缓存策略区分：用户材料 `private, no-store`，内置教程 `public, max-age=300`。

## 5. 提示词注入与信任分级

材料内容被明确定义为**参考数据、不是指令**。收敛链路：

1. `_hydrate_material_context()` **先删除**前端提交的 `material_bits`，再从落盘文件重新派生 —— 前端无法伪造课件能力或注入教学须知。
2. `material_manifest.manifest_bits()` 按 `source_type` 做信任分级：只有 `TRUSTED_NOTE_SOURCES = {'builtin', 'generated'}` 才保留 `teacher_notes` 与 `command_guide`；**导入网页 / 上传文档只保留 `commands`，自由文本一律丢弃**。
3. `routes._trusted_bits()` 再过一层：指令名必须在 `prompts.teacher.MATERIAL_COMMANDS` 注册表内（当前为 `hint`、`reveal`、`step`，另有 `[[highlight:…]]`），未注册的名字直接丢弃，模型收不到该语法就不会输出课件执行不了的指令；自由文本用 `_clean_text` 限长（`teacher_notes` 2000、`command_guide` 每项 200）。
4. 前端只从回复中剥离已约定的 `[[…]]` 指令再渲染，指令通过 `postMessage` 单向派发。协议细节见 [material-protocol.md](material-protocol.md)。

## 6. 外呼与 SSRF 防护

`src/apps/aiteacher/materials.py::_validate_fetch_url()`：

- 只允许 `http` / `https`，必须有 hostname，URL 中不得含用户名/密码。
- 解析全部 A/AAAA 记录后逐个判断：**拦截**链路本地（含常见云元数据地址）、组播、未指定、保留地址；**有意放行** loopback 与局域网，因为产品支持用本机/内网学习页做演示。
- 下载侧：`_download_url()` 自管重定向，手动逐级调用校验（最多 5 跳，`allow_redirects=False`），避免通过 302 绕过；超时 `(5, 20)`；`Content-Length` 与实际读取字节双重限制 5MB；固定 `User-Agent: AITeacher/1.0 (+local learning material reader)`。

上传侧：扩展名白名单 `.html/.htm/.md/.markdown/.txt`、5MB 上限；ASR 音频 12MB 上限（超出返回 413）。

## 7. 密钥与敏感信息处置

- 语音密钥**始终留在服务端**：TTS 由服务端拉取音频后以 base64 data URI 回传，不下发 Key，也规避音频 URL 的跨域/混合内容问题。
- 音色描述字段 `design` 是服务端内部提示词，`/api/tts/voices` 只下发 `code/name/gender/desc/unstable`。
- `.gitignore` 已忽略：`.env`、`/config/config_local.py`、`*.key`/`*.pem`、`/data/`、`userdata/`、`logs/*`、`*.log`。
- `config/config_local.example.py` 只提供键名与占位值，可安全入库。

🔴 **当前存在的具体风险（待用户处置）**：`config/config-server.py` 含有真实形态的 API Key 字面量，并且**已经被 `git add` 进索引**；全仓库检索未发现任何代码 import 该文件（代码只读取 `config.config` 与 `config.config_local`）。在提交或推送到远端之前应当：从索引移除（`git rm --cached config/config-server.py`）或加入 `.gitignore`，并**轮换其中所有密钥**。本文档不复述任何密钥值。

另需注意：`git-commit-push.sh` 使用 `git add -A`，会把工作区全部改动（含上表中的敏感文件、若它们处于未忽略状态）一并提交；`update-git.sh` 相对安全，它校验远程地址并对暂存新增行做密钥模式扫描。

## 8. 隐私与数据最小化

记忆写入前经 `src/prompts/memory_extractor.py::parse_deltas()` 多重校验：

| 校验 | 规则 |
|---|---|
| scope 白名单 | 仅 `user` / `material` / `product` |
| category 白名单 | 按层划分（`USER_CATEGORIES` 8 项 / `MATERIAL_CATEGORIES` 4 项 / `PRODUCT_CATEGORIES` 1 项），**分类必须落在所属 scope 的白名单内**，越界丢弃 |
| 置信度 | `confidence < MIN_CONFIDENCE (0.5)` 丢弃 |
| 长度 | 单条 ≤ `MAX_ITEM_CHARS` 160 字符，空白归一 |
| 敏感内容 | `SENSITIVE_PATTERNS` 命中即整条丢弃：手机号、身份证号、邮箱、医疗诊断词（确诊/诊断/自闭症/抑郁症/多动症/发育迟缓/医院/病历）、银行卡/住址/家庭地址/密码 |
| 数量 | 每轮最多 5 条，重复项去重 |

配套约束：

- 学习偏好（称呼、常用表达、兴趣、语速）只存在浏览器 `localStorage` 并随对话上传，**不写入服务端表**。
- 用户可查看（`GET /aiteacher/api/memory`）与清除（`DELETE /aiteacher/api/memory`）自己的 user 层记忆；聊天历史与材料文件**没有**删除接口，需运维侧处理（见 [database.md](database.md) 第 7 节）。
- 产品定位是学习陪练工具，**不做诊断、治疗或替代专业支持**；记忆层刻意不记录诊断类信息，正是为了不把敏感健康信息留在库里。
- `data/users/` 下是真实学习记录，属于用户数据：不得入库、不得复制到文档/代码/日志。

## 9. 日志

`src/logger.py` 输出到 `logs/<日期>.log` 与控制台；`logs/` 与 `*.log` 已被忽略。日志中会出现异常文本与用户 id 上下文，因此：不得把日志文件提交或贴进公开 Issue；排查问题时优先摘录时间戳与函数名而不是整段响应体。

## 10. 上线前检查清单

1. `SECRET_KEY` 已在 `.env` 中设置，且与会话 Cookie 中的旧值不冲突。
2. 服务器上的 `config/config_local.py`、`certs/`、`.env`、`data/`、`userdata/`、`logs/`、`venv/` 均未被部署脚本覆盖（`deploy-to-china.sh` 已显式排除）。
3. 确认没有任何密钥文件被 Git 跟踪：`git ls-files | grep -iE 'env|key|pem|config_local|config-server'`。
4. 若准备公开仓库：补充 `LICENSE`（当前**无许可证**，根 README 亦已注明），并复核 `data/users/`、`logs/` 未进入历史提交。
5. 依赖版本仍满足服务器环境（`urllib3<2`、`gevent==23.9.1`），见 [deployment.md](deployment.md)。

## 11. 待确认

- `/aiteacher/api/*` 是否需要强制登录（当前依赖会话推导 owner，访客可完整使用）。
- 访客 → 登录用户的记忆/历史归属合并策略（换浏览器或清 Cookie 会换 owner，历史与材料都不跟随）。
- MD5 口令散列的迁移方案（与共用 `sys_user` 表的其它站点相互制约）。
- `config/config-server.py` 的处置：删除 / 忽略 / 保留但脱敏，以及密钥轮换（见第 7 节）。
- 是否需要收紧 SSRF 放行范围（当前有意允许 loopback 与内网，公网部署时是否仍保留）。
