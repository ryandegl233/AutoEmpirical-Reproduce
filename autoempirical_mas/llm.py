from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_seconds: float = 0.0


@dataclass
class ModelConfig:
    model: str
    backend: str = "openai"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: Optional[int] = None


def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def infer_base_url(model: str) -> Optional[str]:
    if "deepseek" in model:
        return os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    return os.getenv("OPENAI_BASE_URL")


def infer_api_key(model: str) -> Optional[str]:
    if "deepseek" in model:
        return os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if "claude" in model:
        return os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    return os.getenv("OPENAI_API_KEY")


class BaseLLMClient:
    model: str

    def complete(self, agent_name: str, system_prompt: str, user_prompt: str) -> LLMResponse:
        raise NotImplementedError


class OpenAICompatibleClient(BaseLLMClient):
    def __init__(self, config: ModelConfig):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the openai package to use the openai backend.") from exc

        self.model = config.model
        self.max_tokens = config.max_tokens
        api_key = config.api_key or infer_api_key(config.model)
        if not api_key:
            raise RuntimeError(
                "No API key found. Set OPENAI_API_KEY, DEEPSEEK_API_KEY, or ANTHROPIC_API_KEY."
            )
        base_url = config.base_url or infer_base_url(config.model)
        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)

    def complete(self, agent_name: str, system_prompt: str, user_prompt: str) -> LLMResponse:
        start = time.perf_counter()
        request: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "stream": False,
        }
        if self.max_tokens:
            request["max_tokens"] = self.max_tokens
        response = self.client.chat.completions.create(**request)
        latency = time.perf_counter() - start
        usage = getattr(response, "usage", None)
        return LLMResponse(
            content=response.choices[0].message.content or "",
            prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            total_tokens=getattr(usage, "total_tokens", 0) if usage else 0,
            latency_seconds=latency,
        )


class CamelClient(BaseLLMClient):
    """Thin CAMEL-AI ChatAgent backend.

    The deterministic MAS orchestration lives in this repository so ablations are
    reproducible; CAMEL supplies the role agents when installed.
    """

    def __init__(self, config: ModelConfig):
        try:
            from camel.agents import ChatAgent
        except ImportError as exc:
            raise RuntimeError("Install camel-ai to use --backend camel.") from exc
        self.model = config.model
        self._chat_agent_cls = ChatAgent

    def complete(self, agent_name: str, system_prompt: str, user_prompt: str) -> LLMResponse:
        start = time.perf_counter()
        agent = self._chat_agent_cls(system_message=system_prompt, model=self.model)
        response = agent.step(user_prompt)
        latency = time.perf_counter() - start
        message = getattr(response, "msg", None)
        if message is None:
            messages = getattr(response, "msgs", [])
            message = messages[0] if messages else None
        content = getattr(message, "content", None) if message is not None else str(response)
        return LLMResponse(content=content or "", latency_seconds=latency)


class MockLLMClient(BaseLLMClient):
    """Offline backend for smoke tests and schema validation."""

    def __init__(self, model: str = "mock"):
        self.model = model

    def complete(self, agent_name: str, system_prompt: str, user_prompt: str) -> LLMResponse:
        lower = user_prompt.lower()
        system_lower = system_prompt.lower()
        agent_lower = agent_name.lower()
        if "evidence" in agent_lower:
            content = '{"evidence":["mock issue evidence"],"missing_context":[],"ambiguity_notes":[]}'
        elif "critic" in agent_lower:
            content = '{"is_consistent":true,"concerns":[],"suggested_fix":null,"confidence":0.7}'
        elif "accepted" in system_lower or "filter" in agent_lower or "filtering" in system_lower:
            label = "Accepted" if any(k in lower for k in ["error", "bug", "fail", "crash", "memory"]) else "Rejected"
            content = (
                '{"label":"%s","confidence":0.62,"evidence":["mock keyword evidence"],'
                '"rationale":"Mock backend heuristic."}' % label
            )
        else:
            content = (
                '{"bug_symptom":{"primary_category":"[A]Crash","subcategory":"[A.1]Reference Error",'
                '"specific_type":"[A.1.1]DL Operator Exception"},"root_cause":'
                '{"primary_category":"[A]Incorrect Programming","subcategory":"[A.1]Unimplemented Operator"},'
                '"confidence":0.55,"evidence":["mock taxonomy evidence"],"rationale":"Mock backend heuristic."}'
            )
        return LLMResponse(content=content, latency_seconds=0.0)


def build_llm_client(config: ModelConfig) -> BaseLLMClient:
    if config.backend == "mock":
        return MockLLMClient(config.model)
    if config.backend == "camel":
        return CamelClient(config)
    if config.backend == "openai":
        return OpenAICompatibleClient(config)
    raise ValueError(f"Unsupported backend: {config.backend}")
