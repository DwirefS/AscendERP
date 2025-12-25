"""
LLM Client - Unified interface for language model inference

Supports multiple providers through Azure AI Foundry:
- Azure OpenAI
- NVIDIA NIM (via Azure)
- GitHub Models
- Ollama (local)

Integrates with ANTS observability and policy engine.
"""

import logging
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from src.core.observability import tracer, trace_llm_call

logger = logging.getLogger(__name__)


class ModelProvider(Enum):
    """Supported LLM providers."""
    AZURE_OPENAI = "azure_openai"
    NVIDIA_NIM = "nvidia_nim"
    GITHUB_MODELS = "github_models"
    OLLAMA = "ollama"


@dataclass
class LLMResponse:
    """Response from LLM inference."""
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    finish_reason: str
    metadata: Dict[str, Any]


class LLMClient(ABC):
    """
    Abstract base class for LLM clients.

    All LLM providers must implement this interface.
    """

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> LLMResponse:
        """
        Generate chat completion.

        Args:
            messages: Chat messages in OpenAI format
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific parameters

        Returns:
            LLMResponse
        """
        pass


class AzureAIFoundryLLMClient(LLMClient):
    """
    LLM client using Azure AI Foundry unified API.

    Supports all Azure AI Foundry model providers.
    """

    def __init__(
        self,
        model: str = "gpt-4",
        provider: ModelProvider = ModelProvider.AZURE_OPENAI,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Azure AI Foundry LLM client.

        Args:
            model: Model deployment name
            provider: Model provider
            config: Optional configuration overrides
        """
        self.model = model
        self.provider = provider
        self.config = config or {}

        # Initialize Foundry client
        try:
            from src.integrations.azure_ai_foundry import get_foundry_client
            self.foundry = get_foundry_client()
            logger.info(
                "Azure AI Foundry LLM client initialized",
                model=model,
                provider=provider.value
            )
        except Exception as e:
            logger.error(f"Failed to initialize Azure AI Foundry client: {e}")
            raise

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> LLMResponse:
        """Generate chat completion via Azure AI Foundry."""
        with tracer.start_as_current_span("llm.chat_completion") as span:
            span.set_attribute("model", self.model)
            span.set_attribute("provider", self.provider.value)
            span.set_attribute("messages_count", len(messages))
            span.set_attribute("temperature", temperature)
            span.set_attribute("max_tokens", max_tokens)

            try:
                response = await self.foundry.get_chat_completion(
                    messages=messages,
                    model=self.model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )

                # Record token usage in observability
                trace_llm_call(
                    model=self.model,
                    prompt_tokens=response['usage']['prompt_tokens'],
                    completion_tokens=response['usage']['completion_tokens'],
                    total_tokens=response['usage']['total_tokens']
                )

                # Set span attributes
                span.set_attribute("tokens.prompt", response['usage']['prompt_tokens'])
                span.set_attribute("tokens.completion", response['usage']['completion_tokens'])
                span.set_attribute("tokens.total", response['usage']['total_tokens'])

                return LLMResponse(
                    content=response['content'],
                    model=response['model'],
                    prompt_tokens=response['usage']['prompt_tokens'],
                    completion_tokens=response['usage']['completion_tokens'],
                    total_tokens=response['usage']['total_tokens'],
                    finish_reason=response['finish_reason'],
                    metadata={}
                )

            except Exception as e:
                span.record_exception(e)
                logger.error(f"Chat completion failed: {e}")
                raise


class NVIDIANIMLLMClient(LLMClient):
    """
    LLM client for NVIDIA NIM microservices.

    Runs models locally or via Azure deployment.
    2.6x faster inference with optimized containers.
    """

    def __init__(
        self,
        model: str = "llama-3.1-nemotron-nano-8b",
        nim_endpoint: Optional[str] = None
    ):
        """
        Initialize NVIDIA NIM client.

        Args:
            model: NIM model name
            nim_endpoint: NIM endpoint URL (defaults to Azure deployment)
        """
        self.model = model
        self.nim_endpoint = nim_endpoint

        logger.info(
            "NVIDIA NIM LLM client initialized",
            model=model,
            endpoint=nim_endpoint or "azure_deployment"
        )

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> LLMResponse:
        """Generate chat completion via NVIDIA NIM."""
        with tracer.start_as_current_span("llm.nim_completion") as span:
            span.set_attribute("model", self.model)
            span.set_attribute("endpoint", self.nim_endpoint or "azure")

            try:
                # Use Azure AI Foundry if no direct endpoint
                if not self.nim_endpoint:
                    from src.integrations.azure_ai_foundry import get_foundry_client
                    foundry = get_foundry_client()

                    response = await foundry.get_chat_completion(
                        messages=messages,
                        model=self.model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        **kwargs
                    )

                    trace_llm_call(
                        model=self.model,
                        prompt_tokens=response['usage']['prompt_tokens'],
                        completion_tokens=response['usage']['completion_tokens'],
                        total_tokens=response['usage']['total_tokens']
                    )

                    return LLMResponse(
                        content=response['content'],
                        model=self.model,
                        prompt_tokens=response['usage']['prompt_tokens'],
                        completion_tokens=response['usage']['completion_tokens'],
                        total_tokens=response['usage']['total_tokens'],
                        finish_reason=response['finish_reason'],
                        metadata={"provider": "nvidia_nim_azure"}
                    )
                else:
                    # Direct NIM endpoint call
                    # Implementation would go here for local NIM containers
                    raise NotImplementedError("Direct NIM endpoint not yet implemented")

            except Exception as e:
                span.record_exception(e)
                logger.error(f"NIM completion failed: {e}")
                raise


class OllamaLLMClient(LLMClient):
    """
    LLM client for Ollama (local development).

    Useful for development/testing without cloud dependencies.
    """

    def __init__(
        self,
        model: str = "llama3.1",
        ollama_host: str = "http://localhost:11434"
    ):
        """
        Initialize Ollama client.

        Args:
            model: Ollama model name
            ollama_host: Ollama server URL
        """
        self.model = model
        self.ollama_host = ollama_host

        logger.info("Ollama LLM client initialized", model=model, host=ollama_host)

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> LLMResponse:
        """Generate chat completion via Ollama."""
        with tracer.start_as_current_span("llm.ollama_completion") as span:
            span.set_attribute("model", self.model)

            try:
                import httpx

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.ollama_host}/api/chat",
                        json={
                            "model": self.model,
                            "messages": messages,
                            "temperature": temperature,
                            "options": {
                                "num_predict": max_tokens
                            },
                            **kwargs
                        }
                    )

                    response.raise_for_status()
                    data = response.json()

                    # Ollama doesn't return token counts, estimate
                    content = data["message"]["content"]
                    estimated_tokens = len(content.split()) * 1.3  # Rough estimate

                    return LLMResponse(
                        content=content,
                        model=self.model,
                        prompt_tokens=0,  # Ollama doesn't report this
                        completion_tokens=int(estimated_tokens),
                        total_tokens=int(estimated_tokens),
                        finish_reason="stop",
                        metadata={"provider": "ollama"}
                    )

            except Exception as e:
                span.record_exception(e)
                logger.error(f"Ollama completion failed: {e}")
                raise


def create_llm_client(
    provider: str = "azure_openai",
    model: Optional[str] = None,
    **kwargs
) -> LLMClient:
    """
    Factory function to create LLM client.

    Args:
        provider: Provider name (azure_openai, nvidia_nim, ollama)
        model: Optional model override
        **kwargs: Provider-specific arguments

    Returns:
        LLMClient instance

    Examples:
        # Azure OpenAI
        llm = create_llm_client("azure_openai", model="gpt-4")

        # NVIDIA NIM via Azure
        llm = create_llm_client("nvidia_nim", model="llama-3.1-nemotron-nano-8b")

        # Ollama for local development
        llm = create_llm_client("ollama", model="llama3.1")
    """
    provider = provider.lower()

    if provider == "azure_openai":
        return AzureAIFoundryLLMClient(
            model=model or "gpt-4",
            provider=ModelProvider.AZURE_OPENAI,
            **kwargs
        )
    elif provider == "nvidia_nim":
        return NVIDIANIMLLMClient(
            model=model or "llama-3.1-nemotron-nano-8b",
            **kwargs
        )
    elif provider == "ollama":
        return OllamaLLMClient(
            model=model or "llama3.1",
            **kwargs
        )
    else:
        raise ValueError(
            f"Unknown provider: {provider}. "
            f"Supported: azure_openai, nvidia_nim, ollama"
        )


async def test_llm_client():
    """Test LLM client."""
    print("Testing LLM Client")
    print("=" * 50)

    try:
        # Test Azure OpenAI
        print("\n1. Testing Azure OpenAI...")
        llm = create_llm_client("azure_openai")

        response = await llm.chat_completion([
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello!"}
        ])

        print(f"Response: {response.content}")
        print(f"Tokens: {response.total_tokens}")
        print(f"Model: {response.model}")
        print("✓ Azure OpenAI working!")

    except Exception as e:
        print(f"✗ Azure OpenAI failed: {e}")

    try:
        # Test Ollama (if running)
        print("\n2. Testing Ollama...")
        llm = create_llm_client("ollama", model="llama3.1")

        response = await llm.chat_completion([
            {"role": "user", "content": "Say hello!"}
        ])

        print(f"Response: {response.content}")
        print(f"Model: {response.model}")
        print("✓ Ollama working!")

    except Exception as e:
        print(f"✗ Ollama failed: {e}")
        print("   Make sure Ollama is running: ollama serve")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_llm_client())
