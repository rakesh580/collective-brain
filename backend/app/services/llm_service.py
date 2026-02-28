import httpx
import logging
from app.config import Settings
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerError

logger = logging.getLogger("collective_brain.llm")


class LLMService:
    def __init__(self, settings: Settings):
        self.provider = settings.llm_provider

        # Circuit breaker: open after 3 failures, recover after 30s
        self.breaker = CircuitBreaker(
            name=f"llm_{self.provider}",
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=2,
        )

        if self.provider == "claude":
            import anthropic
            self.client = anthropic.AsyncAnthropic(api_key=settings.claude_api_key)
            self.model = settings.claude_model
        elif self.provider == "mistral":
            self.hf_api_key = settings.effective_mistral_api_key
            self.model = settings.mistral_model
            self.hf_base_url = "https://router.huggingface.co/v1"
            self.client = None
        else:
            self.ollama_url = settings.ollama_base_url
            self.model = settings.ollama_model
            self.client = None

    async def generate(self, messages: list[dict], max_tokens: int = 2048) -> str:
        """Generate LLM response with circuit breaker protection."""
        return await self.breaker.call(self._generate_impl, messages, max_tokens)

    async def _generate_impl(self, messages: list[dict], max_tokens: int = 2048) -> str:
        if self.provider == "claude":
            system_msg = ""
            chat_messages = []
            for m in messages:
                if m["role"] == "system":
                    system_msg = m["content"]
                else:
                    chat_messages.append(m)
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_msg,
                messages=chat_messages,
                timeout=120.0,
            )
            if not response.content:
                raise ValueError("Claude returned empty response content")
            return response.content[0].text
        elif self.provider == "mistral":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.hf_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.hf_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                    },
                    timeout=120.0,
                )
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    raise ValueError(f"Mistral returned no choices: {data}")
                return choices[0]["message"]["content"]
        else:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                    },
                    timeout=120.0,
                )
                resp.raise_for_status()
                data = resp.json()
                if "message" not in data or "content" not in data["message"]:
                    raise ValueError(f"Ollama returned unexpected format: {data}")
                return data["message"]["content"]

    async def is_available(self) -> bool:
        """Check if LLM is available (respects circuit breaker)."""
        if not self.breaker.is_available:
            return False
        try:
            if self.provider == "claude":
                return bool(self.client)
            elif self.provider == "mistral":
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{self.hf_base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.hf_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "messages": [{"role": "user", "content": "ping"}],
                            "max_tokens": 1,
                        },
                        timeout=10.0,
                    )
                    return resp.status_code == 200
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{self.ollama_url}/api/tags", timeout=5.0
                    )
                    return resp.status_code == 200
        except Exception:
            return False

    def get_circuit_status(self) -> dict:
        """Return circuit breaker status for health checks."""
        return self.breaker.get_status()
