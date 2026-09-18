# 账户模块 (Account Module)

## 概述

账户模块提供用户注册、登录、登出等认证功能，采用模块化设计，所有相关文件集中在 `src/account/` 目录下。

## 目录结构

```
src/account/
├── __init__.py              # 模块初始化，导出 Blueprint
├── models.py                # 用户模型和数据库操作
├── auth_controller.py       # 认证控制器（业务逻辑）
├── routes.py                # Flask Blueprint 路由定义
├── templates/               # 模块专属模板
│   ├── login.html          # 登录页面
│   └── register.html       # 注册页面
├── static/                  # 模块专属静态资源
│   ├── css/
│   │   └── account.css     # 账户模块样式
│   ├── js/
│   │   └── account.js      # 账户模块JavaScript
│   └── images/             # 图像资源（可选）
└── README.md               # 本文档
```

## 功能特性

### 1. 用户注册
- **API**: `POST /account/api/register`
- **参数**:
  - `email`: 邮箱地址（必填）
  - `username`: 用户名（必填）
  - `password`: 密码（可选）
- **返回**: JSON 格式响应

### 2. 用户登录
- **API**: `POST /account/api/login`
- **参数**:
  - `username`: 用户名或邮箱（必填）
  - `password`: 密码（必填）
- **返回**: JSON 格式响应 + Session

### 3. 用户登出
- **API**: `GET /account/api/logout`
- **功能**: 清除 Session

### 4. 检查登录状态
- **API**: `GET /account/api/check_login`
- **返回**:
  ```json
  {
    "isLoggedIn": true/false,
    "user": {
      "id": "user_id",
      "username": "username",
      "email": "email"
    }
  }
  ```

## 页面路由

- `/account/login` - 登录页面
- `/account/register` - 注册页面

## 数据库表结构

```sql
CREATE TABLE sys_user (
    id VARCHAR(8) PRIMARY KEY,           -- 用户ID（8位随机字符）
    name VARCHAR(100) NOT NULL,          -- 用户名
    email VARCHAR(100),                  -- 邮箱
    psw VARCHAR(32),                     -- 密码（MD5加密）
    registsrc VARCHAR(20),               -- 注册来源
    server VARCHAR(100),                 -- 服务器域名
    SYS_ADDUSER VARCHAR(50),             -- 添加用户
    SYS_ADDTIME DATETIME,                -- 注册时间
    lastlogintime DATETIME,              -- 最后登录时间
    wechat_unionid VARCHAR(100),         -- 微信UnionID（预留）
    wechat_nickname VARCHAR(100),        -- 微信昵称（预留）
    google_id VARCHAR(100)               -- Google ID（预留）
);
```

## 使用方法

### 1. 在 Flask 应用中注册

```python
from src.account import account_bp

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # 必须设置
app.register_blueprint(account_bp, url_prefix='/account')
```

### 2. 前端集成

在 HTML 模板中添加登录状态检查：

```html
<!-- 显示登录/注册按钮或用户信息 -->
<div id="authButtons">
    <a href="/account/login">登录</a>
    <a href="/account/register">注册</a>
</div>
<div id="userInfo" style="display: none;">
    <span id="usernameDisplay"></span>
    <button onclick="handleLogout()">登出</button>
</div>

<script src="/account/static/js/account.js"></script>
<script>
    // 页面加载时检查登录状态
    window.addEventListener('DOMContentLoaded', () => {
        checkLoginStatusAndUpdateUI();
    });
</script>
```

### 3. 使用装饰器保护路由

```python
from src.account.auth_controller import require_login

@app.route('/protected-page')
@require_login
def protected_page():
    return "只有登录用户才能访问"
```

## 安全说明

1. **密码加密**: 当前使用 MD5 加密，建议升级为 bcrypt 或 argon2
2. **Session 配置**: 必须在 Flask 应用中设置 `SECRET_KEY`
3. **SQL 注入防护**: 使用参数化查询，防止 SQL 注入
4. **XSS 防护**: 前端输入需要验证和转义

## 扩展方向

1. **社交登录**: 已预留微信、Google OAuth 接口
2. **找回密码**: 可通过邮箱重置密码
3. **双因素认证**: 增加短信/邮箱验证码
4. **权限管理**: 添加角色和权限系统
5. **登录日志**: 记录用户登录历史

## 注意事项

1. 确保数据库中已创建 `sys_user` 表
2. Session 默认有效期为 30 天
3. 支持用户名或邮箱登录
4. 密码为可选字段（用于社交登录场景）

## 测试

启动应用后访问：
- 注册页面: `http://localhost:5000/account/register`
- 登录页面: `http://localhost:5000/account/login`

测试 API:
```bash
# 注册用户
curl -X POST http://localhost:5000/account/api/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","username":"testuser","password":"123456"}'

# 登录
curl -X POST http://localhost:5000/account/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"123456"}'

# 检查登录状态
curl http://localhost:5000/account/api/check_login
```

## 维护者

深表 AI 工作室

## 许可证

MIT License
