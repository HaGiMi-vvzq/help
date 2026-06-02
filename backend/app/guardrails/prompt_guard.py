class PromptGuard:
    @staticmethod
    def sanitize(user_input: str) -> str:
        return user_input[:5000]

    @staticmethod
    def wrap_with_boundary(user_input: str) -> str:
        return f"<user_input>\n{user_input}\n</user_input>"
