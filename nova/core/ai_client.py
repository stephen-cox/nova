"""AI client abstraction layer supporting multiple providers"""

import asyncio
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
import logging

from nova.models.config import AIModelConfig
from nova.models.message import Message, MessageRole

logger = logging.getLogger(__name__)


class AIError(Exception):
    """Base exception for AI-related errors"""
    pass


class AIRateLimitError(AIError):
    """Raised when API rate limit is exceeded"""
    pass


class AIAuthenticationError(AIError):
    """Raised when API authentication fails"""
    pass


class AIModelNotFoundError(AIError):
    """Raised when requested model is not available"""
    pass


class BaseAIClient(ABC):
    """Abstract base class for AI clients"""
    
    def __init__(self, config: AIModelConfig):
        self.config = config
    
    @abstractmethod
    async def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Generate a response from the AI model"""
        pass
    
    @abstractmethod
    async def generate_response_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """Generate a streaming response from the AI model"""
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """Validate that the client configuration is correct"""
        pass
    
    @abstractmethod
    async def list_models(self) -> List[str]:
        """List available models for this provider"""
        pass


class OpenAIClient(BaseAIClient):
    """OpenAI API client"""
    
    def __init__(self, config: AIModelConfig):
        super().__init__(config)
        
        try:
            import openai
            self.client = openai.AsyncOpenAI(
                api_key=config.api_key,
                base_url=config.base_url
            )
        except ImportError:
            raise AIError("OpenAI library not installed. Install with: uv add openai")
    
    def validate_config(self) -> bool:
        """Validate OpenAI configuration"""
        if not self.config.api_key:
            logger.warning("OpenAI API key not provided")
            return False
        return True
    
    async def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Generate response using OpenAI API"""
        try:
            response = await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                **kwargs
            )
            return response.choices[0].message.content
            
        except Exception as e:
            self._handle_api_error(e)
    
    async def generate_response_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """Generate streaming response using OpenAI API"""
        try:
            stream = await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                stream=True,
                **kwargs
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            self._handle_api_error(e)
    
    async def list_models(self) -> List[str]:
        """List available OpenAI models"""
        try:
            models = await self.client.models.list()
            return [model.id for model in models.data]
        except Exception as e:
            self._handle_api_error(e)
    
    def _handle_api_error(self, error: Exception) -> None:
        """Convert OpenAI errors to our standard errors"""
        import openai
        
        if isinstance(error, openai.RateLimitError):
            raise AIRateLimitError(f"OpenAI rate limit exceeded: {error}")
        elif isinstance(error, openai.AuthenticationError):
            raise AIAuthenticationError(f"OpenAI authentication failed: {error}")
        elif isinstance(error, openai.NotFoundError):
            raise AIModelNotFoundError(f"OpenAI model not found: {error}")
        else:
            raise AIError(f"OpenAI API error: {error}")


class AnthropicClient(BaseAIClient):
    """Anthropic API client"""
    
    def __init__(self, config: AIModelConfig):
        super().__init__(config)
        
        try:
            import anthropic
            self.client = anthropic.AsyncAnthropic(
                api_key=config.api_key,
                base_url=config.base_url
            )
        except ImportError:
            raise AIError("Anthropic library not installed. Install with: uv add anthropic")
    
    def validate_config(self) -> bool:
        """Validate Anthropic configuration"""
        if not self.config.api_key:
            logger.warning("Anthropic API key not provided")
            return False
        return True
    
    async def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Generate response using Anthropic API"""
        try:
            # Convert messages to Anthropic format
            anthropic_messages = self._convert_messages(messages)
            
            response = await self.client.messages.create(
                model=self.config.model_name,
                messages=anthropic_messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                **kwargs
            )
            return response.content[0].text
            
        except Exception as e:
            self._handle_api_error(e)
    
    async def generate_response_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """Generate streaming response using Anthropic API"""
        try:
            anthropic_messages = self._convert_messages(messages)
            
            async with self.client.messages.stream(
                model=self.config.model_name,
                messages=anthropic_messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                **kwargs
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                    
        except Exception as e:
            self._handle_api_error(e)
    
    async def list_models(self) -> List[str]:
        """List available Anthropic models"""
        # Anthropic doesn't have a models endpoint, return common models
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022", 
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307"
        ]
    
    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Convert OpenAI-style messages to Anthropic format"""
        converted = []
        for msg in messages:
            if msg["role"] == "system":
                # Anthropic handles system messages differently
                continue
            converted.append({
                "role": "user" if msg["role"] == "user" else "assistant",
                "content": msg["content"]
            })
        return converted
    
    def _handle_api_error(self, error: Exception) -> None:
        """Convert Anthropic errors to our standard errors"""
        import anthropic
        
        if isinstance(error, anthropic.RateLimitError):
            raise AIRateLimitError(f"Anthropic rate limit exceeded: {error}")
        elif isinstance(error, anthropic.AuthenticationError):
            raise AIAuthenticationError(f"Anthropic authentication failed: {error}")
        elif isinstance(error, anthropic.NotFoundError):
            raise AIModelNotFoundError(f"Anthropic model not found: {error}")
        else:
            raise AIError(f"Anthropic API error: {error}")


class OllamaClient(BaseAIClient):
    """Ollama API client for local models"""
    
    def __init__(self, config: AIModelConfig):
        super().__init__(config)
        
        try:
            import ollama
            self.client = ollama.AsyncClient(
                host=config.base_url or "http://localhost:11434"
            )
        except ImportError:
            raise AIError("Ollama library not installed. Install with: uv add ollama")
    
    def validate_config(self) -> bool:
        """Validate Ollama configuration"""
        # Ollama doesn't require API key, just check if server is reachable
        return True
    
    async def generate_response(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Generate response using Ollama API"""
        try:
            response = await self.client.chat(
                model=self.config.model_name,
                messages=messages,
                options={
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens,
                },
                **kwargs
            )
            return response['message']['content']
            
        except Exception as e:
            self._handle_api_error(e)
    
    async def generate_response_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """Generate streaming response using Ollama API"""
        try:
            stream = await self.client.chat(
                model=self.config.model_name,
                messages=messages,
                options={
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens,
                },
                stream=True,
                **kwargs
            )
            
            async for chunk in stream:
                if 'message' in chunk and 'content' in chunk['message']:
                    yield chunk['message']['content']
                    
        except Exception as e:
            self._handle_api_error(e)
    
    async def list_models(self) -> List[str]:
        """List available Ollama models"""
        try:
            models = await self.client.list()
            return [model['name'] for model in models['models']]
        except Exception as e:
            self._handle_api_error(e)
    
    def _handle_api_error(self, error: Exception) -> None:
        """Convert Ollama errors to our standard errors"""
        if "connection" in str(error).lower():
            raise AIError(f"Cannot connect to Ollama server. Make sure Ollama is running: {error}")
        elif "not found" in str(error).lower():
            raise AIModelNotFoundError(f"Ollama model not found: {error}")
        else:
            raise AIError(f"Ollama API error: {error}")


def create_ai_client(config: AIModelConfig) -> BaseAIClient:
    """Factory function to create appropriate AI client"""
    
    if config.provider == "openai":
        return OpenAIClient(config)
    elif config.provider == "anthropic":
        return AnthropicClient(config)
    elif config.provider == "ollama":
        return OllamaClient(config)
    else:
        raise AIError(f"Unsupported provider: {config.provider}")


# Synchronous wrapper for easier integration
def generate_sync_response(config: AIModelConfig, messages: List[Dict[str, str]], **kwargs) -> str:
    """Synchronous wrapper for AI response generation"""
    
    async def _generate():
        client = create_ai_client(config)
        return await client.generate_response(messages, **kwargs)
    
    try:
        # Get or create event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, we need to handle this differently
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _generate())
                return future.result()
        else:
            return loop.run_until_complete(_generate())
    except RuntimeError:
        # No event loop exists, create a new one
        return asyncio.run(_generate())