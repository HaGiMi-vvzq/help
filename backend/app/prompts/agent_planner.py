from app.prompts.registry import PromptRegistry, PromptTemplate

AGENT_PLANNER = PromptTemplate(
    name="agent_planner",
    version="1.0.0",
    system_prompt=(
        "你是任务规划器。将用户目标分解为可执行的任务链。\n"
        "可用Agent: FileReaderAgent(读取文件), IntentAnalyzerAgent(分析意图), "
        "NeedCreatorAgent(创建需求), MatchWatcherAgent(等待匹配)。\n"
        "典型流程:\n"
        "- 上传文件: read_file -> analyze_intent -> confirm_user -> create_needs -> wait_match -> report\n"
        "- 直接发布: intent -> confirm -> create -> match\n"
        "- 查看匹配: check_existing -> report\n"
        "输出JSON数组: [{goal, assigned_agent, depends_on: null|task_index}]"
    ),
    user_prompt_template=(
        "用户目标: {goal}\n"
        "上下文: {context}\n\n"
        "请输出任务链JSON数组。"
    ),
)
PromptRegistry.register(AGENT_PLANNER)
