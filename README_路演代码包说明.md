# 校园 AI 互助撮合平台代码包说明

本包是路演用纯代码包，不包含 Qwen 本地模型、前端 `node_modules`、构建产物、隐私 `.env`、日志、脚本目录、Word 文档和视频。

## 包内包含

- `backend/`：FastAPI 后端源码、测试、演示数据库 `app.db`、`app.db-wal`、`app.db-shm`、`.env.example`。
- `frontend/`：Vue 3 + Vite 前端源码、`package.json`、`package-lock.json`。
- `docs/`：Markdown 文档和 Agent 文件测试素材。
- `README.md`、`README_部署使用指南.md`：项目说明和部署说明。

## 需要自行准备的内容

### 1. Python 环境

建议使用已有 Conda 环境 `ark`。如果是新机器：

```powershell
cd backend
pip install -r requirements.txt
```

### 2. 前端依赖

本包不带 `node_modules`，新机器需要安装：

```powershell
cd frontend
npm install
```

### 3. Qwen 本地模型

本包不带模型。需要把模型放到：

```text
backend/model_cache/Qwen3-Embedding-0.6B
backend/model_cache/Qwen3-Reranker-0.6B
```

如果没有模型，部分 embedding / rerank 能力会降级或不可用，演示智能匹配时建议提前放好模型。

### 4. DeepSeek API Key

本包不带 `.env`。可以复制示例：

```powershell
cd backend
copy .env.example .env
```

然后在 `.env` 中填写：

```text
DEEPSEEK_API_KEY=你的 API Key
```

也可以在系统的 API 设置页面填写，并用“检测”按钮确认可用。

## 启动方式

后端：

```powershell
cd backend
conda run -n ark python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

浏览器访问：

```text
http://127.0.0.1:5173/login
```

## 演示账号

演示数据在 `backend/app.db` 中。常用账号：

```text
alice / 123456
bob / 123456
```

## 本次更新已包含

- Agent 平台定位回复优化，避免只罗列工具能力。
- 语义路由 Skill，用于区分发布需求、寻找已有需求、查看匹配、上传文件和普通聊天。
- API Key 检测和 DeepSeek 默认网络 / 本地代理自动切换。
- 匹配页 AI 起草私信后可一键发送。
- 刷新匹配时，新候选人如果还没有画像向量，会现场补 embedding 后参与匹配。
- Agent 文件上传测试素材：`docs/agent_file_test_cases/`。

