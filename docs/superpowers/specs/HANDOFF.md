# 校园 AI 互助匹配平台 — 交接文档

## 项目目标

校园AI互助匹配平台。2天开发可演示MVP，用于黑客松比赛。

## 核心功能

用户用自然语言创建技能画像 → AI提取标签并向量化 → 发布需求（求助/组队/技能交换）→ AI通过Embedding语义检索+LLM精排匹配最合适的人 → 返回带推荐理由的候选人列表 → 站内消息联系。

## 技术栈

- 前端：Vue 3 + Vite + 响应式
- 后端：Python FastAPI
- 数据库：SQLite
- AI：DeepSeek Chat API（标签提取、精排、推荐理由） + DeepSeek Embedding API（语义向量）
- 向量检索：NumPy 余弦相似度（轻量，两天内够用）
- 认证：JWT

## 匹配流程（核心）

1. 需求发布 → DeepSeek Chat 提取结构化需求标签
2. DeepSeek Embedding 生成需求向量
3. 与所有用户画像向量做余弦相似度 → Top 10
4. DeepSeek Chat 对 Top 10 精排 + 每人一个推荐理由
5. 返回 Top 5 匹配结果

## 数据模型

4张表：users（含 skill_tags JSON + profile_embedding JSON）、needs（含 req_tags JSON + need_embedding JSON）、messages、matches（可选）

## API

8个接口：注册/登录、更新画像、发布需求、需求列表、获取匹配结果（核心）、发送消息、获取对话

## 前端页面

6页：登录注册、AI画像创建、需求广场、发布需求、匹配结果（核心演示页）、站内消息

## MVP 范围

做：上述全部
不做（路演画饼）：实时聊天WebSocket、微信小程序、AI自我进化Agent、技能知识图谱、消息推送

## 设计文档

详见 docs/superpowers/specs/2026-05-27-campus-ai-match-design.md
