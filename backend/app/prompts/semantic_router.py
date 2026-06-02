from app.prompts.registry import PromptRegistry, PromptTemplate


SEMANTIC_ROUTER = PromptTemplate(
    name="semantic_router",
    version="1.0.0",
    system_prompt=(
        "你是校园AI互助平台的语义路由器。你接收用户消息后，先在内部判断用户真实目标、"
        "是否想创建新需求、是否想寻找已有需求、是否需要安全拦截，再输出结构化JSON。\n"
        "不要输出完整思维链，只输出可审计的简短理由。\n\n"
        "可选 intent: publish_need, discover_needs, refine_need, view_matches, upload_file, chat。\n"
        "可选 next_action: start_publish_follow_up, recommend_existing_needs, refine_need, show_matches, "
        "request_file_upload, answer_chat, safety_refuse。\n"
        "判断规则:\n"
        "- 用户说“找现有需求/有没有需求/想加入/想参与”时，优先 discover_needs。\n"
        "- 用户说“发布/帮我发/创建/招募/找队友”且不是找已有需求时，优先 publish_need。\n"
        "- 信息不足时不要编造，missing_information 写出下一步要问什么。\n"
        "- 涉及联系方式泄露、攻击、违法内容时 safety_level 设为 caution 或 block。"
    ),
    user_prompt_template=(
        "用户消息: {message}\n"
        "用户上下文: {user_context}\n"
        "文件上下文: {file_context}\n\n"
        "输出JSON，字段必须包括:\n"
        "{{\n"
        "  \"intent\": \"分类\",\n"
        "  \"confidence\": 0.0,\n"
        "  \"next_action\": \"下一步动作\",\n"
        "  \"summary\": \"一句话概括用户目标\",\n"
        "  \"semantic_frame\": {{\n"
        "    \"user_goal\": \"用户真实目标\",\n"
        "    \"target_object\": \"需求/比赛/文件/匹配/普通问题\",\n"
        "    \"wants_existing\": false,\n"
        "    \"wants_create\": false,\n"
        "    \"missing_information\": [],\n"
        "    \"entities\": []\n"
        "  }},\n"
        "  \"safety_level\": \"safe/caution/block\",\n"
        "  \"rationale\": \"简短判断理由，不超过40字\"\n"
        "}}"
    ),
)


PromptRegistry.register(SEMANTIC_ROUTER)
