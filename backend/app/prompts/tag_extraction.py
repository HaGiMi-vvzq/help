from app.prompts.registry import PromptRegistry, PromptTemplate

TAG_EXTRACTION = PromptTemplate(
    name="tag_extraction",
    version="1.0.0",
    system_prompt=(
        "你是技能标签提取器。从自由描述中提取结构化技能标签。\n"
        "规则：① 技能名用业界通用名称（如 Vue.js 而非 Vue）"
        "② 同时提取软技能（沟通、领导力）\n"
        "③ 每个标签 ≤8 字 ④ 输出纯 JSON 数组"
    ),
    few_shot_examples=[
        {
            "input": "计算机大三，会写Python爬虫，做过几个Vue小项目",
            "output": '["Python", "Web爬虫", "Vue.js", "前端开发"]',
        },
        {
            "input": "研二材料专业，会做SEM和XRD测试，想找人合作写论文",
            "output": '["SEM分析", "XRD表征", "材料测试", "学术写作", "论文协作"]',
        },
    ],
    user_prompt_template="现在处理: {text}",
    output_schema={"type": "array", "items": {"type": "string"}},
)

PromptRegistry.register(TAG_EXTRACTION)
