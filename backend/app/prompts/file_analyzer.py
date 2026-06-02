from app.prompts.registry import PromptRegistry, PromptTemplate

FILE_ANALYZER = PromptTemplate(
    name="file_analyzer",
    version="1.0.0",
    system_prompt=(
        "你是文件分析助手。从用户上传的文件中提取关键信息，结构化输出。\n"
        "关注：活动/比赛名称、主题领域、所需技能、截止日期、合作要求、奖励/成果。"
    ),
    user_prompt_template=(
        "文件名: {filename}\n\n文件内容:\n{text}\n\n"
        "请提取关键信息，返回JSON。"
    ),
)
PromptRegistry.register(FILE_ANALYZER)
