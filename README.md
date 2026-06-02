# 校园AI互助匹配平台

基于 AI 的校园技能匹配与互助平台，面向绵阳市安州区。通过 DeepSeek 大模型 + Qwen3 本地嵌入/重排实现智能化队友匹配。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), SQLite |
| 前端 | Vue 3, Element Plus, Pinia, Vue Router, Vite, TypeScript |
| AI | DeepSeek v4-pro / v4-flash, Qwen3-Embedding-0.6B, Qwen3-Reranker-0.6B |
| 本地模型 | sentence-transformers, PyTorch (CPU/CUDA) |

## 快速开始

### 1. 环境准备

```bash
# Python 3.12+
pip install -r backend/requirements.txt

# Node.js 18+
cd frontend && npm install
```

### 2. 配置 API Key

复制环境变量模板并填入你的 DeepSeek API Key：

```bash
cd backend
cp .env.example .env
# 编辑 .env，将 DEEPSEEK_API_KEY 替换为你的真实 Key
```

获取 Key: https://platform.deepseek.com/api_keys

也可以在启动后通过网页「系统设置」页面配置（需重启服务）。

### 3. 下载本地模型（可选但推荐）

匹配精度依赖 Qwen3 本地模型。不下载也能运行（使用哈希降级方案），但匹配效果会差很多。

```bash
cd backend
python download_models.py   # 一键下载 ~1.5GB
```

或手动下载到 `backend/model_cache/`：
- [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- [Qwen3-Reranker-0.6B](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)

### 4. 初始化数据库

```bash
cd backend
python seed.py    # 首次运行灌入演示数据（后续运行不会删数据）
```

### 5. 启动服务

```bash
# 后端 (端口 8000)
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 前端 (端口 5174)
cd frontend
npx vite --port 5174
```

默认演示账号密码均为 `123456`：alice / bob / carol / dave / eve

### 5. 下载本地模型 (可选)

匹配和重排需要 Qwen3 本地模型：

```bash
# 从 HuggingFace 下载到 backend/model_cache/
# Qwen3-Embedding-0.6B: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B
# Qwen3-Reranker-0.6B: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
```

## 功能特性

- AI 智能匹配：标签提取 → 语义搜索 → 精排 → 推荐理由
- 需求广场：发布求助、组队、技能交换
- AI 辅助写作：润色描述、根据标题生成需求
- AI 追问对话：匹配顾问帮用户细化需求
- 智能 Agent：文件上传分析、自动发布需求、多轮规划
- 个人画像：技能标签、学校院系、年级性别
- 站内消息：实时对话、系统通知
- 需求管理：单选/多选匹配、关闭/重开/删除

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── agents/         # 7 个智能体
│   │   ├── adapters/       # DeepSeek + Qwen3 适配器
│   │   ├── integrations/   # API 客户端 + 模型路由
│   │   ├── knowledge/      # 技能图谱 + 匹配记忆
│   │   ├── models/         # 13 张数据表
│   │   ├── prompts/        # 7 个 Prompt 模板
│   │   ├── routers/        # 6 个路由模块
│   │   ├── services/       # 9 个服务模块
│   │   └── skills/         # 8 个可注册技能
│   ├── seed.py             # 演示数据种子
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── api/            # 6 个 API 客户端
│       ├── components/     # 11 个组件
│       ├── stores/         # 4 个 Pinia Store
│       ├── views/          # 8 个页面
│       └── types/
├── docs/                   # 开发进度文档
└── README.md
```

## 数据存储

SQLite 单文件 `backend/app.db`，WAL 模式 + 启动自动备份（`backend/db_backups/`）。

重置数据库：`python backend/reset_db.py`（需输入 YES 确认）
