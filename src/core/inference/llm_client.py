"""
LLM Client for ANTS.
Supports NVIDIA NIM, Azure OpenAI, and local models.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, AsyncIterator
from enum import Enum
import httpx
import structlog

logger = structlog.get_logger()


class ModelProvider(Enum):
    """Supported LLM providers."""
    NVIDIA_NIM = "nvidia_nim"
    AZURE_OPENAI = "azure_openai"
    LOCAL = "local"


@dataclass
class LLMConfig:
    """Configuration for LLM client."""
    provider: ModelProvider
    model_name: str
    endpoint: str
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout_seconds: int = 30


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    tokens_used: int
    finish_reason: str
    model: str
    metadata: Dict[str, Any]


class BaseLLMClient(ABC):
    """Base class for LLM clients."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = httpx.AsyncClient(timeout=config.timeout_seconds)

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate completion from prompt."""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream generation from prompt."""
        pass

    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        pass

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()


class NIMClient(BaseLLMClient):
    """Client for NVIDIA NIM microservices."""

    async def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate completion using NIM."""
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        payload = {
            "model": self.config.model_name,
            "prompt": prompt,
            "temperature": temp,
            "max_tokens": tokens,
            "top_p": kwargs.get("top_p", 0.9),
            "frequency_penalty": kwargs.get("frequency_penalty", 0.0),
            "presence_penalty": kwargs.get("presence_penalty", 0.0)
        }

        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        try:
            response = await self._client.post(
                f"{self.config.endpoint}/v1/completions",
                json=payload,
                headers=headers
            )
            response.raise_for_status()

            data = response.json()
            choice = data["choices"][0]

            return LLMResponse(
                content=choice["text"],
                tokens_used=data["usage"]["total_tokens"],
                finish_reason=choice["finish_reason"],
                model=data["model"],
                metadata={
                    "prompt_tokens": data["usage"]["prompt_tokens"],
                    "completion_tokens": data["usage"]["completion_tokens"]
                }
            )

        except Exception as e:
            logger.error("nim_generation_failed", error=str(e))
            raise

    async def generate_stream(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream generation using NIM."""
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        payload = {
            "model": self.config.model_name,
            "prompt": prompt,
            "temperature": temp,
            "max_tokens": tokens,
            "stream": True
        }

        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        async with self._client.stream(
            "POST",
            f"{self.config.endpoint}/v1/completions",
            json=payload,
            headers=headers
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: " prefix
                    if data == "[DONE]":
                        break
                    import json
                    chunk = json.loads(data)
                    if "choices" in chunk and len(chunk["choices"]) > 0:
                        text = chunk["choices"][0].get("text", "")
                        if text:
                            yield text

    async def embed(self, text: str) -> List[float]:
        """Generate embedding using NIM embedding model."""
        # Use separate embedding endpoint
        embedding_endpoint = self.config.endpoint.replace(
            self.config.model_name,
            "nv-embedqa-e5-v5"
        )

        payload = {
            "model": "nv-embedqa-e5-v5",
            "input": text
        }

        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        try:
            response = await self._client.post(
                f"{embedding_endpoint}/v1/embeddings",
                json=payload,
                headers=headers
            )
            response.raise_for_status()

            data = response.json()
            return data["data"][0]["embedding"]

        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e))
            raise


class AzureOpenAIClient(BaseLLMClient):
    """Client for Azure OpenAI."""

    async def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate completion using Azure OpenAI."""
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        payload = {
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temp,
            "max_tokens": tokens,
            "top_p": kwargs.get("top_p", 0.9)
        }

        headers = {
            "api-key": self.config.api_key,
            "Content-Type": "application/json"
        }

        try:
            response = await self._client.post(
                f"{self.config.endpoint}/openai/deployments/{self.config.model_name}/chat/completions?api-version=2024-02-01",
                json=payload,
                headers=headers
            )
            response.raise_for_status()

            data = response.json()
            choice = data["choices"][0]

            return LLMResponse(
                content=choice["message"]["content"],
                tokens_used=data["usage"]["total_tokens"],
                finish_reason=choice["finish_reason"],
                model=data["model"],
                metadata={
                    "prompt_tokens": data["usage"]["prompt_tokens"],
                    "completion_tokens": data["usage"]["completion_tokens"]
                }
            )

        except Exception as e:
            logger.error("azure_openai_generation_failed", error=str(e))
            raise

    async def generate_stream(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream generation using Azure OpenAI."""
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        payload = {
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temp,
            "max_tokens": tokens,
            "stream": True
        }

        headers = {
            "api-key": self.config.api_key,
            "Content-Type": "application/json"
        }

        async with self._client.stream(
            "POST",
            f"{self.config.endpoint}/openai/deployments/{self.config.model_name}/chat/completions?api-version=2024-02-01",
            json=payload,
            headers=headers
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    import json
                    chunk = json.loads(data)
                    if "choices" in chunk and len(chunk["choices"]) > 0:
                        delta = chunk["choices"][0].get("delta", {})
                        text = delta.get("content", "")
                        if text:
                            yield text

    async def embed(self, text: str) -> List[float]:
        """Generate embedding using Azure OpenAI."""
        payload = {
            "input": text
        }

        headers = {
            "api-key": self.config.api_key,
            "Content-Type": "application/json"
        }

        embedding_deployment = "text-embedding-3-large"

        try:
            response = await self._client.post(
                f"{self.config.endpoint}/openai/deployments/{embedding_deployment}/embeddings?api-version=2024-02-01",
                json=payload,
                headers=headers
            )
            response.raise_for_status()

            data = response.json()
            return data["data"][0]["embedding"]

        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e))
            raise


def create_llm_client(config: LLMConfig) -> BaseLLMClient:
    """Factory function to create appropriate LLM client."""
    if config.provider == ModelProvider.NVIDIA_NIM:
        return NIMClient(config)
    elif config.provider == ModelProvider.AZURE_OPENAI:
        return AzureOpenAIClient(config)
    else:
        raise ValueError(f"Unsupported provider: {config.provider}")
