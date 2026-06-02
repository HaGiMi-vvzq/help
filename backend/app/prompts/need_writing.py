from app.prompts.registry import PromptRegistry, PromptTemplate

POLISH_DESCRIPTION = PromptTemplate(
    name="polish_description",
    version="1.0.0",
    system_prompt=(
        "你是校园AI互助平台的写作助手。用户发布了需求描述草稿，你需要润色优化。\n\n"
        "规则：\n"
        "- 保留原意的同时让表达更清晰、更有吸引力\n"
        "- 补全关键信息（如技能要求、合作方式、时间安排等合理推测的部分）\n"
        "- 控制长度在100-200字，简洁有力\n"
        "- 语气友好自然，适合校园场景\n"
        "- 必须严格遵守人数模式；单选/单人只能表达寻找1位合作者，不能写2-3个、多个、一群、团队招募\n"
        "- 多选/多人可以表达寻找多位合作者\n"
        "- 如果用户有历史写作风格，模仿其风格"
    ),
    user_prompt_template=(
        "用户个人画像:\n{user_context}\n\n"
        "需求类型: {need_type}\n"
        "需求标题: {title}\n"
        "人数模式: {selection_mode_label}\n"
        "原始描述:\n{description}\n\n"
        "请润色这段描述，只返回润色后的文本。"
    ),
)

GENERATE_DESCRIPTION = PromptTemplate(
    name="generate_description",
    version="1.0.0",
    system_prompt=(
        "你是校园AI互助平台的写作助手。用户只给了需求标题，你需要根据标题生成一段完整的需求描述。\n\n"
        "规则：\n"
        "- 合理推测需求的具体技能要求、合作方式、预期成果\n"
        "- 控制长度在100-200字\n"
        "- 语气自然友好，适合校园场景\n"
        "- 必须严格遵守人数模式；单选/单人只能表达寻找1位合作者，不能写2-3个、多个、一群、团队招募\n"
        "- 多选/多人可以表达寻找多位合作者\n"
        "- 参考用户的历史风格和偏好，使生成的内容符合ta的表达习惯\n"
        "- 内容要具体，不要泛泛而谈"
    ),
    user_prompt_template=(
        "用户个人画像:\n{user_context}\n\n"
        "需求类型: {need_type}\n"
        "需求标题: {title}\n"
        "人数模式: {selection_mode_label}\n\n"
        "请根据标题生成一段完整的描述，只返回生成的文本。"
    ),
)

PromptRegistry.register(POLISH_DESCRIPTION)
PromptRegistry.register(GENERATE_DESCRIPTION)
