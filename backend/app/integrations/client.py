import asyncio
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

V4_ENDPOINT = "/chat/completions"
LOCAL_PROXY_URL = "http://127.0.0.1:7897"

# Concurrent DeepSeek API request limiter
_deepseek_semaphore = asyncio.Semaphore(10)


def _is_network_error(exc: Exception) -> bool:
    if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException, httpx.NetworkError, httpx.ProxyError)):
        return True
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "all connection attempts failed",
            "could not connect",
            "connection refused",
            "connection reset",
            "network is unreachable",
        )
    )


class AIClient:
    """DeepSeek API client with automatic local-proxy fallback and connection pooling."""

    _http: httpx.AsyncClient | None = None

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        chat_model: str | None = None,
        flash_model: str | None = None,
    ):
        self.base = (base_url or settings.DEEPSEEK_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.DEEPSEEK_API_KEY
        self.chat_model = chat_model or settings.DEEPSEEK_PRO_MODEL
        self.flash_model = flash_model or settings.DEEPSEEK_FLASH_MODEL
        self.last_connection_path = "default"

    @property
    def http(self) -> httpx.AsyncClient:
        # Reuse the global client for connection pooling across all AIClient instances
        if AIClient._http is None:
            AIClient._http = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return AIClient._http

    @classmethod
    async def close_http(cls):
        if cls._http is not None:
            await cls._http.aclose()
            cls._http = None

    def _build_chat_body(
        self,
        messages: list[dict],
        model: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
    ) -> dict:
        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if "v4" in model:
            body["thinking"] = {"type": "disabled"}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    def _connection_paths(self) -> list[tuple[str, str | None]]:
        paths: list[tuple[str, str | None]] = [
            ("default", None),
            ("local_proxy", LOCAL_PROXY_URL),
        ]
        if self.last_connection_path == "local_proxy":
            return [paths[1], paths[0]]
        return paths

    async def _post_chat(self, body: dict, timeout: float, proxy_url: str | None = None) -> dict:
        url = f"{self.base}{V4_ENDPOINT}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        async with _deepseek_semaphore:
            if proxy_url is not None:
                resp = await self.http.post(url, headers=headers, json=body, timeout=timeout, proxy=proxy_url)
            else:
                resp = await self.http.post(url, headers=headers, json=body, timeout=timeout)
            resp.raise_for_status()
            return resp.json()

    async def _chat_with_network_fallback(self, body: dict, timeout: float) -> dict:
        last_exc: Exception | None = None
        for label, proxy_url in self._connection_paths():
            try:
                data = await asyncio.wait_for(
                    self._post_chat(body, timeout=timeout, proxy_url=proxy_url),
                    timeout=timeout + 10,
                )
                self.last_connection_path = label
                return data
            except httpx.HTTPStatusError:
                raise
            except Exception as exc:
                last_exc = exc
                if label == "default" and _is_network_error(exc):
                    logger.warning("Default DeepSeek connection failed, trying local proxy %s: %s", LOCAL_PROXY_URL, exc)
                    continue
                raise
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No DeepSeek connection path available")

    async def _chat_raw(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        timeout: float = 60.0,
    ) -> dict:
        body = self._build_chat_body(messages, model, temperature, max_tokens)
        return await self._chat_with_network_fallback(body, timeout)

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        timeout: float = 60.0,
        max_retries: int = 2,
        json_mode: bool = False,
    ) -> str:
        model = model or self.chat_model
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                body = self._build_chat_body(messages, model, temperature, max_tokens, json_mode=json_mode)
                data = await self._chat_with_network_fallback(body, timeout)

                msg = data["choices"][0]["message"]
                content = msg.get("content") or ""
                if not content:
                    content = msg.get("reasoning_content") or ""
                return content

            except asyncio.TimeoutError:
                last_error = "AI request timed out"
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (400, 401, 402, 403):
                    raise RuntimeError(f"API error {e.response.status_code}: {e.response.text[:200]}")
                last_error = str(e)
            except Exception as e:
                last_error = str(e)

            wait = 2 ** attempt
            if attempt < max_retries:
                logger.warning("Chat error (attempt %d/%d): %s, retrying in %ds", attempt + 1, max_retries + 1, last_error, wait)
                await asyncio.sleep(wait)

        raise RuntimeError(f"AI chat failed after {max_retries + 1} attempts: {last_error}")


_ai_client: AIClient | None = None


def apply_runtime_config(*, deepseek_api_key: str | None = None) -> None:
    """Apply settings changed from the UI to new AI client instances."""
    global _ai_client
    if deepseek_api_key is not None:
        settings.DEEPSEEK_API_KEY = deepseek_api_key
    _ai_client = None


def get_ai_client() -> AIClient:
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient()
    return _ai_client
