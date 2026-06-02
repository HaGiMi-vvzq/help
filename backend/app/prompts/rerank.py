from app.prompts.registry import PromptRegistry, PromptTemplate

RERANK = PromptTemplate(
    name="rerank",
    version="1.0.0",
    system_prompt=(
        "你是校园技能匹配专家。基于需求与候选人画像的语义关联度、技能互补性和协作潜力，"
        "为每位候选人打分并给出推荐理由。\n"
        "分析步骤：① 对比需求标签与候选人技能的重合度 "
        "② 检查候选人的经验相关性 ③ 评估双方是否互补 ④ 综合打分（0-100）"
    ),
    user_prompt_template=(
        "需求描述: {need_description}\n"
        "需求标签: {need_tags}\n"
        "技能知识库上下文: {knowledge_context}\n"
        "历史相似成功案例: {match_memory_context}\n\n"
        "候选人列表:\n{candidates_formatted}\n\n"
        "请返回 JSON 数组（直接输出，不要 markdown 代码块）:\n"
        '[{{"user_id": <id>, "score": <0-100>, "reason": "<≤25字>", "complementarity": "<互补点>"}}]\n'
        "只输出 Top 5。"
    ),
    output_schema={"type": "array", "items": {"type": "object"}},
)

PromptRegistry.register(RERANK)
