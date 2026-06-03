# 更新日志 (CHANGELOG)

## [第二轮] — 2026-06-03：部署完善与健壮性加固

### 脚本补全 (Scripts)

- **`seed.py`** — 新增演示数据初始化脚本，幂等创建 11 个用户 + 8 条需求，含技能标签和完整画像
- **`download_models.py`** — 新增 Qwen3 模型下载工具，支持 sentence-transformers / huggingface_hub 双通道下载
- **`reset_db.py`** — 新增数据库安全重置脚本，需输入 YES 确认

### 容器化 (Containerization)

- **`backend/Dockerfile`** — Python 3.12-slim，非 root 用户，Uvicorn 多 worker 生产模式，Healthcheck
- **`frontend/Dockerfile`** — 多阶段构建：Node 20 构建 + Nginx 1.27-alpine 托管
- **`frontend/nginx.conf`** — Gzip 压缩、安全响应头、API 反向代理、SPA 路由回退
- **`docker-compose.yml`** — 前后端一键编排，环境变量驱动，数据卷持久化

### CI/CD

- **`.github/workflows/ci.yml`** — 后端 Lint → 测试 → 前端构建 → Docker 镜像检查全流水线

### 安全 (Security)

- **SECRET_KEY 强制配置** — 默认值从 `"dev-secret-key"` 改为空字符串，启动时为空则 `sys.exit(1)` 拒绝启动
- **密码强度验证** — 新增 `validate_password_strength()`：≥6 位、≤128 位、禁止空格
- **用户名校验** — 新增 `validate_username()`：2-20 字符、仅允许字母数字下划线连字符
- **API Key 检测限流** — `/api/settings/test-api-key` 端点新增 10 次/分限流保护

### 运维 (Operations)

- **文件日志持久化** — `RotatingFileHandler` 正式启用，日志写入 `backend/logs/app.log`，10MB × 10 文件轮转
- **`.gitignore`** — 新增 `logs/` 目录排除
- **`.env.example`** — 新增 `LOG_LEVEL` 配置项，完善部署注释

---

## [第一轮] — 2026-06-02：代码健壮性与安全加固

### 安全 (Security)

- **更换 SECRET_KEY** — 从占位符替换为随机生成的真实密钥
- **登录接口限流** — 新增限流保护（5次/分，20次/时）
- **Token 存储升级** — localStorage → sessionStorage
- **SSE Token 安全** — 从 URL 参数改为 Cookie
- **全局异常处理** — HTTPException / RequestValidationError / Exception 三级处理
- **API 错误格式统一** — `{"error": "...", "detail": "..."}`
- **CORS 环境变量化** — 从 `.env` 读取
- **生产环境 API 文档隐藏** — `DEBUG=false` 关闭 /docs
- **头像上传限制** — MIME 白名单 + 2MB 限制
- **Agent 文件上传前端校验** — 扩展名 + MIME 双重校验 + 10MB
- **`.gitignore` 加固** — 新增 `*.log`、`model_cache/`、`dist/` 等
- **401 竞态修复** — `isLoggingOut` 防抖标记

### 变更 (Changed)

- **日志系统重构** — DEBUG=true 可读格式，DEBUG=false JSON 格式
- **httpx 连接池复用** — 模块级单例 AsyncClient
- **DeepSeek 并发控制** — asyncio.Semaphore(10)
- **DeepSeek 超时差异化** — 按任务类型 10-45s
- **限流器算法优化** — 游标清理策略

### 新增 (Added)

- **Alembic 迁移框架**
- **统一错误 Schema**
- **前端 404 页面**
- **前端环境变量体系**
