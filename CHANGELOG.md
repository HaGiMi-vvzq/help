# 更新日志 (CHANGELOG)

## [Unreleased] — 第一轮：代码健壮性与安全加固

### 安全 (Security)

- **更换 SECRET_KEY** — 从占位符 `change-me-to-a-random-secret-key` 替换为随机生成的真实密钥
- **登录接口限流** — `/api/auth/login` 新增限流保护（5次/分，20次/时），防止暴力破解
- **Token 存储升级** — 前端 token 从 `localStorage` 迁移至 `sessionStorage`（关闭标签页自动清除），同时兼容旧 `localStorage` 迁移
- **SSE Token 安全** — 匹配流 (EventSource) 的 token 从 URL 查询参数移除，改为通过 Cookie (`auth_token`) 自动传递；后端同时支持 Cookie > Query String > Authorization Header 三种降级读取
- **全局异常处理** — 添加 `HTTPException`、`RequestValidationError`、通用 `Exception` 三级全局异常处理器，生产环境不再暴露 traceback
- **API 错误格式统一** — 所有错误响应统一为 `{"error": "...", "detail": "..."}` 格式
- **CORS 环境变量化** — 允许来源从硬编码改为从 `.env` 的 `CORS_ALLOWED_ORIGINS` 读取
- **生产环境 API 文档隐藏** — `DEBUG=false` 时自动关闭 `/docs` 和 `/redoc`
- **头像上传限制** — 新增 MIME 类型白名单 (PNG/JPEG/GIF/WebP) 和 2MB 大小限制
- **Agent 文件上传前端校验** — 新增扩展名 + MIME 类型双重校验 + 10MB 限制
- **`.gitignore` 加固** — 新增 `*.log`、`model_cache/`、`dist/`、`.vscode/`、`.idea/` 等排除规则
- **401 竞态修复** — 前端 API 拦截器添加 `isLoggingOut` 防抖标记，防止并发 401 时重复登出
- **注册限流参数化** — 提取 `REGISTER_RATE_LIMIT_PER_MINUTE` 常量

### 变更 (Changed)

- **日志系统重构** — `DEBUG=true` 使用可读格式输出 stderr，`DEBUG=false` 使用 JSON 结构化格式；支持通过 `LOG_LEVEL` 环境变量控制级别；清理 root logger handlers 防止重复
- **httpx 连接池复用** — `AIClient` 从每次请求新建 `AsyncClient` 改为模块级单例复用（`max_keepalive_connections=10`）
- **DeepSeek 并发控制** — 新增 `asyncio.Semaphore(10)` 限制同时调用 DeepSeek API 的并发数
- **DeepSeek 超时差异化** — 按任务类型配置不同超时：标签提取/审核 10-15s，聊天 45s，推荐理由 30s，替代统一 60s
- **限流器算法优化** — `RateLimiter` 从列表重建改为游标清理（减少内存分配）；新增 `get_login_rate_limiter()` 独立实例
- **健康检查增强** — `/api/health` 新增 DeepSeek API 配置状态、Qwen Embed 模型加载状态的检查项

### 新增 (Added)

- **Alembic 迁移框架** — 引入 Alembic，配置异步 SQLAlchemy，生成初始迁移 `35e9f6eea385_initial.py`
- **统一错误 Schema** — 新增 `app/schemas/error.py` (`ErrorResponse`)
- **前端 404 页面** — 新增 `NotFoundView.vue`，路由 `/:pathMatch(.*)*` 兜底
- **前端环境变量体系** — 新增 `.env.development` 和 `.env.production`，`VITE_API_BASE_URL` 支持不同环境 API 路径切换
- **`CORS_ALLOWED_ORIGINS` 配置项** — `.env` 中新增逗号分隔的来源白名单

### 变更文件清单

| 文件 | 操作 |
|------|------|
| `backend/.env` | 修改 — 更换 SECRET_KEY，新增 CORS_ALLOWED_ORIGINS |
| `backend/.gitignore` | 修改 — 新增忽略规则 |
| `backend/app/core/config.py` | 修改 — 新增 LOG_LEVEL、CORS_ALLOWED_ORIGINS |
| `backend/app/core/security.py` | 未修改 |
| `backend/app/main.py` | 修改 — 全局异常处理、CORS 环境变量、结构化日志、增强健康检查 |
| `backend/app/routers/auth.py` | 修改 — 登录接口限流 |
| `backend/app/routers/profile.py` | 修改 — 头像上传校验 |
| `backend/app/routers/needs.py` | 修改 — SSE token 支持 Cookie 读取 |
| `backend/app/routers/agents.py` | 未修改 |
| `backend/app/guardrails/rate_limiter.py` | 修改 — 独立登录限流实例 + 游标清理优化 |
| `backend/app/integrations/client.py` | 修改 — httpx 连接池复用 + 并发信号量 |
| `backend/app/integrations/model_router.py` | 修改 — 按任务类型配置超时 |
| `backend/app/schemas/error.py` | **新增** |
| `backend/alembic/` | **新增** — Alembic 迁移框架 |
| `frontend/src/stores/auth.ts` | 修改 — sessionStorage + 兼容 localStorage 迁移 |
| `frontend/src/stores/needs.ts` | 修改 — SSE token 使用 Cookie |
| `frontend/src/api/client.ts` | 修改 — 401 竞态修复 + VITE_API_BASE_URL |
| `frontend/src/router/index.ts` | 修改 — 新增 404 兜底路由 |
| `frontend/src/views/NeedDetailView.vue` | 修改 — 添加 loading/empty 状态 |
| `frontend/src/views/MyApplicationsView.vue` | 修改 — 添加 v-loading |
| `frontend/src/views/AgentView.vue` | 修改 — 文件上传类型+大小校验 |
| `frontend/src/views/NotFoundView.vue` | **新增** |
| `frontend/.env.development` | **新增** |
| `frontend/.env.production` | **新增** |
