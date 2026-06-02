# 校园 AI 互助匹配平台 — 设计文档

## 概述

基于 AI 的校园互助匹配平台。用户通过自然语言描述创建技能画像，发布求助/组队/技能交换需求，AI 自动进行语义向量匹配 + LLM 精排，返回带推荐理由的候选人列表。站内消息完成对接。

**定位：** 校园场景优先，架构可扩展到社区场景。

**约束：** 两天开发，可演示 MVP。

---

## 技术栈

| 层 | 技术 | 理由 |
|---|---|---|
| 前端 | Vue 3 + Vite + 简单 UI 库 | 开发者熟悉，响应式适配评委手机/电脑 |
| 后端 | Python FastAPI | 对接 AI API 丝滑，开发快 |
| 数据库 | SQLite | 零配置，两天够用 |
| AI Chat | DeepSeek Chat API | 标签提取、LLM 精排、推荐理由生成 |
| AI Embedding | DeepSeek Embedding API | 画像/需求向量化，语义相似度检索 |
| 向量检索 | NumPy 余弦相似度 | 轻量，无需额外向量数据库，两天内实现 |
| 认证 | JWT | 轻量无状态 |

---

## 核心匹配流程

```
用户发布需求（自然语言）
  → DeepSeek Chat 提取结构化需求标签
  → DeepSeek Embedding 生成需求向量
  → 与所有用户画像向量做余弦相似度 → Top 10 粗筛
  → DeepSeek Chat 对 Top 10 精排 + 生成每人推荐理由
  → 返回 Top 5 匹配结果（含分数 + AI 推荐语）
```

**路演亮点：** Embedding 语义检索 + LLM 精排 + 可解释推荐理由，三段式 pipeline 有技术深度可讲。

---

## 数据模型

### users
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | |
| username | VARCHAR | 唯一 |
| password_hash | VARCHAR | |
| bio | TEXT | 用户自由描述原文 |
| skill_tags | JSON | AI 提取的技能标签列表 |
| profile_embedding | JSON | 画像语义向量 (list[float]) |
| school | VARCHAR | 学校 |
| rating_score | FLOAT | 累计反馈评分，默认 5.0 |
| created_at | DATETIME | |

### needs
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | |
| user_id | FK → users | 发布者 |
| type | VARCHAR | 求助 / 组队 / 技能交换 |
| title | VARCHAR | |
| description | TEXT | 需求原文 |
| req_tags | JSON | AI 提取的需求标签 |
| need_embedding | JSON | 需求语义向量 |
| status | VARCHAR | 开放 / 已匹配 / 关闭 |
| created_at | DATETIME | |

### messages
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | |
| need_id | FK → needs | 关联需求 |
| sender_id | FK → users | |
| receiver_id | FK → users | |
| content | TEXT | |
| created_at | DATETIME | |

### matches（可选，存匹配记录用于反馈闭环）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | |
| need_id | FK → needs | |
| user_id | FK → users | 被匹配到的用户 |
| score | FLOAT | 匹配度 |
| ai_reason | TEXT | AI 推荐理由 |
| feedback | INT NULL | 互评打分 |

---

## API 设计

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/auth/register | 注册 + bio → 返回 token + AI 标签建议 |
| POST | /api/auth/login | 登录 → JWT |
| PUT | /api/profile | 更新画像、确认标签 → 重新生成 Embedding |
| POST | /api/needs | 发布需求 → AI 提取标签 + Embedding |
| GET | /api/needs | 需求广场列表（分页） |
| GET | /api/needs/:id/matches | 核心：获取 AI 匹配结果 |
| POST | /api/messages | 发送站内消息 |
| GET | /api/messages/:user_id | 获取对话记录 |

`/api/needs/:id/matches` 内部逻辑：
1. 从 needs 表取 need_embedding
2. 遍历 users 表计算余弦相似度（排除发布者自己）
3. 取 Top 10
4. 构造 prompt 发给 DeepSeek Chat：需求描述 + 10 个候选人画像 → 打分 + 推荐理由
5. 返回 Top 5，写入 matches 表

---

## 前端页面

| 页面 | 路由 | 说明 |
|---|---|---|
| 注册/登录 | /login | 含 bio 填写 |
| AI 画像创建 | /profile/setup | 自由描述 → AI 提取标签 → 用户确认修改 → 生成向量 |
| 需求广场 | / | 浏览所有开放需求，支持简单筛选 |
| 发布需求 | /needs/new | 写描述 → AI 提取标签 → 发布 |
| 匹配结果 | /needs/:id/matches | 核心演示页：匹配列表 + AI 推荐理由 + 联系按钮 |
| 我的消息 | /messages | 对话列表 + 聊天详情 |

---

## 差异化亮点

1. **AI 自解释匹配** — 不只是打分，AI 告诉你"为什么推荐这个人"
2. **向量语义匹配** — "会做网站"能匹配到"React + Node.js"
3. **轻量反馈闭环** — 互评数据回写权重，匹配质量越用越高（MVP 阶段实现评分，自进化逻辑路演画饼）
4. **可扩展架构** — 匹配引擎与场景解耦，扩展到社区/职场只需换数据

---

## 不在 MVP 范围内（路演画饼用）

- 实时聊天（WebSocket）
- 微信小程序
- AI Hermes 式自我进化 Agent
- 技能知识图谱
- 校外社区场景
- 消息推送通知
