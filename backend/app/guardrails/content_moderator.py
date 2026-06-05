"""Content moderation — sensitive word filter for needs, messages, and profiles."""

import re
import logging

logger = logging.getLogger(__name__)

# Category-based keyword lists — extend based on real-world needs
_SENSITIVE_PATTERNS: dict[str, list[str]] = {
    "adult": [
        r"(?i)\b(色情|淫秽|裸聊|cam\s*girl|only\s*fans|escort)\b",
    ],
    "gambling": [
        r"(?i)\b(赌博|赌场|博彩|bet\s*\d|casino|老虎机|六合彩)\b",
    ],
    "fraud": [
        r"(?i)\b(刷单|兼职.*日结|返利.*佣金|代充|刷信誉|快速.*赚钱|日入.*万)\b",
    ],
    "spam": [
        r"(?i)\b(加微信|扫码.*加|私聊.*优惠|点击.*链接|免费.*领取|v信|薇信)\b",
    ],
    "hate": [
        r"(?i)\b(傻逼|sb|fuck|操你|cnm|去死|废物)\b",
    ],
    "personal_info": [
        r"\b1[3-9]\d{9}\b",     # phone numbers
        r"\b\d{6}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b",  # Chinese ID
        r"\b\d{17}[\dXx]\b",    # Chinese ID (18 digits)
    ],
}

_WARNING_PATTERNS: dict[str, list[str]] = {
    "self_harm": [
        r"(?i)\b(自杀|自残|不想活|抑郁.*求助|焦虑.*发作)\b",
    ],
    "minor_safety": [
        r"(?i)\b(未成年.*约|学生.*陪|找.*大学生.*陪)\b",
    ],
}


class ModerationResult:
    def __init__(self):
        self.blocked: bool = False
        self.flagged: bool = False
        self.reasons: list[str] = []
        self.redacted_text: str = ""

    def __repr__(self):
        return f"ModerationResult(blocked={self.blocked}, flagged={self.flagged}, reasons={self.reasons})"


def moderate_text(text: str) -> ModerationResult:
    result = ModerationResult()

    for category, patterns in _SENSITIVE_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                result.blocked = True
                result.reasons.append(category)
                break  # one match per category is enough

    for category, patterns in _WARNING_PATTERNS.items():
        if category in result.reasons:
            continue
        for pattern in patterns:
            if re.search(pattern, text):
                result.flagged = True
                result.reasons.append(category)
                break

    if not result.blocked:
        result.redacted_text = _redact_pii(text)
    else:
        result.redacted_text = text

    return result


def _redact_pii(text: str) -> str:
    text = re.sub(r"\b1[3-9]\d{9}\b", "[手机号已隐藏]", text)
    text = re.sub(r"\b\d{6}(19|20)\d{8}\d{3}[\dXx]?\b", "[身份证已隐藏]", text)
    return text


def moderate_need(title: str, description: str) -> ModerationResult:
    combined = f"{title}\n{description}"
    return moderate_text(combined)


def moderate_message(content: str) -> ModerationResult:
    return moderate_text(content)


def moderate_bio(text: str) -> ModerationResult:
    return moderate_text(text)
