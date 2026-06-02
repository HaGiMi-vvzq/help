from app.adapters.deepseek_adapter import DeepSeekChatAdapter
from app.integrations.client import get_ai_client
from app.integrations.model_router import route
from app.skills.base import BaseSkill


class TaskPlannerSkill(BaseSkill):
    name = "task_planner"
    description = "将用户目标分解为可执行的子任务链"
    version = "1.0.0"

    async def execute(self, input_data: dict) -> dict:
        goal = input_data["goal"]
        context = input_data.get("context", "")

        client = get_ai_client()
        cfg = route("agent_planner")
        adapter = DeepSeekChatAdapter(client, model=cfg["model"])

        system = (
            "你是任务规划器。将用户目标分解为可执行的任务链。\n"
            "可用Agent: FileReaderAgent(读文件提取信息), IntentAnalyzerAgent(分析意图), "
            "NeedCreatorAgent(创建需求), MatchWatcherAgent(等待匹配结果)。\n"
            "输出JSON数组，每个任务: {goal, assigned_agent, depends_on(可选)}。\n"
            "典型链: read_file -> analyze_intent -> confirm_with_user -> create_need -> wait_match -> report_results"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"上下文: {context}\n\n目标: {goal}"},
        ]

        try:
            result = await adapter.chat_with_json(messages, temperature=cfg["temperature"], max_tokens=cfg["max_tokens"])
            return {"tasks": result if isinstance(result, list) else [], "success": True}
        except Exception:
            return {"tasks": [
                {"goal": "分析用户意图", "assigned_agent": "IntentAnalyzerAgent"},
                {"goal": "与用户确认细节", "assigned_agent": "PlannerAgent"},
                {"goal": "创建并发布需求", "assigned_agent": "NeedCreatorAgent"},
            ], "success": False, "fallback": True}
