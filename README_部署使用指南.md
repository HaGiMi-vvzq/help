# 校园 AI 互助撮合平台部署使用指南

本文档用于项目代码包交付后的本地部署、演示启动和问题排查。代码包默认不包含隐私文件和运行产物，例如 `.env`、数据库文件、备份、上传文件、日志、`node_modules`、前端构建产物和本地模型缓存。

## 1. 项目结构

```text
backend/                 FastAPI 后端服务
frontend/                Vue 3 前端项目
README.md                项目基础说明
README_部署使用指南.md   本部署使用指南
```

## 2. 环境要求

- Windows 10/11 或兼容的 Linux/macOS 环境
- Python 3.11 或已配置好的 Conda 环境
- Node.js 20+ 与 npm
- 可访问的大模型 API Key
- 推荐浏览器：Chrome、Edge 或 Firefox

当前演示环境使用 Conda 环境名 `ark`。如果本机没有该环境，可以自行创建 Python 3.11 环境后安装依赖。

## 3. 后端配置与启动

进入后端目录：

```bash
cd backend
```

安装依赖：

```bash
pip install -r requirements.txt
```

如果使用 Conda 演示环境：

```bash
conda run -n ark python -m pip install -r requirements.txt
```

创建环境配置文件：

```bash
copy .env.example .env
```

在 `.env` 中填写模型 API Key。提交代码包不会包含 `.env`，请不要把真实密钥提交到仓库或截图中。

启动后端：

```bash
conda run -n ark python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

如果不使用 Conda：

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

正常返回：

```json
{"status":"ok"}
```

## 4. 数据库与演示账号

后端使用 SQLite。本地第一次启动或需要初始化演示数据时，可在 `backend` 目录执行：

```bash
conda run -n ark python seed.py
```

常用演示账号密码均为 `123456`：

```text
alice / bob / carol / dave / eve / frank / grace / henry / iris / jack / test2
```

注意：代码包默认不包含 `app.db`、`app.db-wal`、`app.db-shm` 和 `db_backups/`，以避免携带本地隐私数据。部署后请按需重新初始化数据库。

## 5. 前端配置与启动

进入前端目录：

```bash
cd frontend
```

安装依赖：

```bash
npm install
```

启动前端开发服务：

```bash
npm run dev -- --host 127.0.0.1 --port 5173
```

访问：

```text
http://127.0.0.1:5173
```

构建生产包：

```bash
npm run build
```

当前项目通过 Vite proxy 将前端 `/api` 请求转发到后端，演示时请保持后端运行在 `127.0.0.1:8000`。

## 6. 推荐演示流程

1. 打开 `http://127.0.0.1:8000/api/health`，确认后端返回 `ok`。
2. 打开 `http://127.0.0.1:5173/login`。
3. 使用 `alice / 123456` 登录。
4. 进入智能助手，通过聊天或上传文件生成需求草稿。
5. 确认发布需求，进入匹配结果页。
6. 查看候选人卡片和对比表。
7. 起草私信并进入消息页沟通。
8. 切换 `iris` 或 `bob` 账号，验证被选中需求、主动申请和申请状态流转。

## 7. 赛前检查命令

后端测试：

```bash
cd backend
conda run -n ark python -m unittest tests.test_project_contracts
conda run -n ark python -m unittest tests.test_agent_smoke
conda run -n ark python -m compileall app tests
```

前端构建：

```bash
cd frontend
npm run build
```

已知非阻塞提示：

- 前端构建可能出现来自第三方依赖的 Rolldown 注释警告。
- `vendor-element` 可能出现 chunk size warning。
- 这些警告不影响演示主链路。

## 8. 常见问题

后端端口被占用：

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
```

找到进程后结束旧进程，再重新启动后端。

前端端口被占用：

```bash
npm run dev -- --host 127.0.0.1 --port 5174
```

AI 功能不可用：

- 检查 `backend/.env` 中 API Key 是否正确。
- 打开系统设置页，确认 API 设置已保存。
- 即使外部模型不可用，需求、匹配、申请和消息等业务主链路仍可继续演示。

数据库状态混乱：

- 优先使用新建测试需求现场演示。
- 不要在正式演示前临时重置数据库。
- 如需重置，请先确认已有备份和恢复方案。

## 9. 隐私与提交注意事项

提交或分享代码包前，请确认不要包含以下内容：

- `.env` 或任何真实 API Key
- `app.db`、`*.db-wal`、`*.db-shm`
- `backend/db_backups/`
- `backend/uploads/`
- `backend/model_cache/`
- `node_modules/`
- `frontend/dist/`
- 日志文件 `*.log`
- Office 临时文件 `~$*.docx`

项目代码包只包含运行源码与部署说明，项目说明书、技术架构文档、路演 PPT、演示视频等材料请按赛事要求作为独立文件提交。
