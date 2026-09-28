# 交接说明：<任务标题>

用于 Mac 侧 Agent 与服务器侧 Agent 之间移交工作。两台机器的权限边界不同：**Mac 改代码，服务器只负责跑与验证**，任何生产写操作都要在这里显式确认。

## 基本信息

- 发出方：`qoder@mac` / `agent@server`
- 接收方：<待填>
- 时间：YYYY-MM-DD
- 任务文件：<链接到 tasks/ 下的任务文件>
- 基准提交：`<git rev-parse --short HEAD>`
- 代码是否已推送：是（分支/提交）· 否（差异说明）

## 环境状态

| 项 | 值 |
|---|---|
| 站点目录 | 服务器 `/alidata/www/aiteacher` |
| 运行方式 | `./run_prod.sh`，双实例：5058 HTTPS（语音可用）、5059 HTTP |
| pidfile | `logs/aiteacher_5058.pid`、`logs/aiteacher_5059.pid` |
| 应用日志 | `logs/<日期>.log`；gunicorn `logs/gunicorn_access.log`、`logs/gunicorn_error.log` |
| 依赖是否变更 | 是（需把 `deploy-to-china.sh` 的 `UPDATE_DEPENDENCIES` 置 `true`）· 否 |

## 已完成

- <改了哪些文件、结论是什么>

## 未做 / 受阻

- <现象 + 已排除的可能 + 需要对方具备什么条件才能继续>

## 接收方要做的事

1. <具体动作，含命令>
2. <验证方式与期望结果>

## 验证方式

```bash
# 健康检查（必须看状态码）
curl -sk -o /dev/null -m 10 -w '%{http_code}' https://127.0.0.1:5058/health
curl -s  -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1:5059/health
```

- [ ] `/health` 返回 200
- [ ] <功能级验证步骤，例如：打开 `/study`，选内置教程，发一轮消息，确认 SSE 有逐字输出>
- [ ] 无新增 `ERROR` 级日志

## 风险与禁止事项

- ⚠️ 服务器上**不得**执行 `restart.sh` / `stop.sh` / `start_dev.sh`（含全局 `pkill -f gunicorn`，会杀掉同机其它站点）。
- ⚠️ 不要覆盖服务器上的 `config/config_local.py`、`.env`、`data/`、`userdata/`、`certs/`、`venv/`、`logs/`。
- ⚠️ 不要在本文件里粘贴密钥、Token、真实服务器公网地址或 `data/users/` 下的用户内容。
- 回滚方式：<代码回滚 / 数据备份位置>

## 交接结论（接收方回填）

| 日期 | 执行方 | 结果 |
|---|---|---|
| YYYY-MM-DD | <待填> | <待填> |
