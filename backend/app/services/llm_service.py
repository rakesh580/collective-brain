import time
import httpx
import logging
from app.config import Settings
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerError

logger = logging.getLogger("collective_brain.llm")


class LLMService:
    def __init__(self, settings: Settings):
        self.provider = settings.llm_provider

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
        from app.services.telemetry import get_tracer
        from app.services.metrics import LLM_REQUESTS_TOTAL, LLM_LATENCY, LLM_TOKENS_ESTIMATED

        tracer = get_tracer("collective_brain.llm")
        t0 = time.perf_counter()
        status = "success"

        # Rough token estimate: count chars / 4 across all messages
        total_chars = sum(len(m.get("content", "")) for m in messages)
        estimated_tokens = total_chars // 4

        with tracer.start_as_current_span(
            f"llm.generate.{self.provider}",
            attributes={
                "llm.provider": self.provider,
                "llm.model": self.model,
                "llm.max_tokens": max_tokens,
                "llm.estimated_input_tokens": estimated_tokens,
            },
        ) as span:
            try:
                result = await self._call_provider(messages, max_tokens)
                span.set_attribute("llm.status", "success")
                return result
            except Exception as e:
                status = "error"
                span.record_exception(e)
                span.set_attribute("llm.status", "error")
                raise
            finally:
                elapsed = time.perf_counter() - t0
                LLM_LATENCY.labels(provider=self.provider, model=self.model).observe(elapsed)
                LLM_REQUESTS_TOTAL.labels(
                    provider=self.provider, model=self.model, status=status
                ).inc()
                LLM_TOKENS_ESTIMATED.labels(provider=self.provider, org_id="-").inc(estimated_tokens)
                logger.debug(
                    "LLM generate: provider=%s model=%s elapsed=%.2fs status=%s",
                    self.provider, self.model, elapsed, status,
                )

    async def _call_provider(self, messages: list[dict], max_tokens: int) -> str:
        """Raw provider call — no metrics/tracing (handled by caller)."""
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

        else:  # ollama
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
        from app.services.metrics import CIRCUIT_BREAKER_STATE
        is_open = not self.breaker.is_available
        CIRCUIT_BREAKER_STATE.labels(service=f"llm_{self.provider}").set(1 if is_open else 0)

        if is_open:
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
        return self.breaker.get_status()
