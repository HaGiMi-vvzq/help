import logging

from app.adapters.deepseek_adapter import DeepSeekChatAdapter
from app.integrations.client import get_ai_client
from app.integrations.model_router import route
from app.skills.base import BaseSkill

logger = logging.getLogger(__name__)

# 常见技术关键词库 (API 不可用时使用)
_FALLBACK_KEYWORDS = [
    "Python", "Java", "JavaScript", "TypeScript", "Go", "Rust", "C++", "C#",
    "React", "Vue.js", "Vue", "Angular", "Node.js", "Spring Boot", "Django", "FastAPI",
    "机器学习", "深度学习", "PyTorch", "TensorFlow", "NLP", "计算机视觉",
    "数据分析", "数据可视化", "ECharts", "Pandas", "NumPy", "SQL", "数据库",
    "前端开发", "后端开发", "全栈开发", "DevOps", "Docker", "Kubernetes",
    "UI设计", "UX设计", "Figma", "品牌设计", "平面设计",
    "SEM分析", "XRD表征", "TEM分析", "材料测试",
    "算法优化", "数学建模", "ACM竞赛", "美赛",
    "商业计划书", "BP路演", "市场分析", "财务预测",
    "学术写作", "论文协作", "项目管理", "团队协作",
]


class TagSkill(BaseSkill):
    name = "tag_extraction"
    description = "从自然语言描述中提取结构化技能标签"
    version = "1.0.0"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string", "description": "用户的自由描述文本"}},
        "required": ["text"],
    }
    output_schema = {
        "type": "object",
        "properties": {"tags": {"type": "array", "items": {"type": "string"}}},
    }
    tags = ["nlp", "classification"]

    async def execute(self, input_data: dict) -> dict:
        text = input_data["text"]

        try:
            client = get_ai_client()
            cfg = route("tag_extraction")
            adapter = DeepSeekChatAdapter(client, model=cfg["model"])

            system_prompt = (
                "你是技能标签提取器。从自由描述中提取结构化技能标签。\n"
                "规则：① 技能名用业界通用名称 ② 同时提取软技能（沟通、领导力）\n"
                "③ 每个标签 ≤8 字 ④ 输出纯 JSON 数组"
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f'示例输入: "计算机大三，会写Python爬虫，做过几个Vue小项目"\n示例输出: ["Python", "Web爬虫", "Vue.js", "前端开发"]'},
                {"role": "user", "content": f'示例输入: "研二材料专业，会做SEM和XRD测试，想找人合作写论文"\n示例输出: ["SEM分析", "XRD表征", "材料测试", "学术写作", "论文协作"]'},
                {"role": "user", "content": f"现在处理: {text}"},
            ]

            tags = await adapter.chat_with_json(
                messages,
                temperature=cfg["temperature"],
                max_tokens=cfg["max_tokens"],
                timeout=8,
                max_retries=0,
            )
            if isinstance(tags, list):
                return {"tags": tags, "fallback": False}
            if isinstance(tags, dict) and "tags" in tags:
                return {"tags": tags["tags"], "fallback": False}
            return {"tags": [], "fallback": False}

        except Exception:
            # API 降级: 用关键词匹配提取标签
            logger.warning("Tag extraction API failed, using keyword fallback")
            return {"tags": self._keyword_fallback(text), "fallback": True}

    def _keyword_fallback(self, text: str) -> list[str]:
        tags = []
        text_lower = text.lower()
        for kw in _FALLBACK_KEYWORDS:
            if kw.lower() in text_lower:
                tags.append(kw)
        return tags[:10]
