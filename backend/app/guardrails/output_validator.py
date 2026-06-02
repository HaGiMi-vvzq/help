import re
import json


class OutputValidator:
    @staticmethod
    async def validate_json(text: str, expected_schema: dict | None = None) -> tuple[dict | None, str]:
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()

        bracket = text.find("[")
        brace = text.find("{")
        start = min(
            bracket if bracket >= 0 else len(text),
            brace if brace >= 0 else len(text),
        )
        if start < len(text):
            text = text[start:]

        try:
            result = json.loads(text)
        except json.JSONDecodeError as e:
            return None, f"JSON解析失败: {e}"

        return result, ""
