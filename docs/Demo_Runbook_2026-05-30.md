# Demo Runbook

## 推荐账号

- `alice / 123456`
  - 适合演示 `Agent -> 匹配 -> 私信 -> 消息推进` 主链
- `bob / 123456`
  - 适合演示候选合作方视角
- `eve / 123456`
  - 适合演示设计类画像与需求

## 推荐演示顺序

1. 登录 `alice`
2. 打开 `Agent 工作台`
3. 用 `/plan` 或上传材料展示 AI 规划
4. 进入 `大创项目数据可视化看板` 的匹配结果页
5. 起草私信并联系候选人
6. 跳转消息页，发送一条推进消息

## 重置演示数据

在 `backend` 目录执行：

```bash
python reset_db.py
python seed.py
```

执行后会恢复默认演示账号、需求、匹配结果与消息记录。

## 启动服务

后端：

```bash
conda run -n ark python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端：

```bash
npm run dev -- --host 127.0.0.1 --port 5173
```

## 当前已验证链路

- 登录
- 广场浏览
- Agent `/plan`
- 匹配结果展示
- 起草私信
- 选定候选人
- 消息发送
