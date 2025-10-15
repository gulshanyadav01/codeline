"""AI Client factory for multi-provider support."""
import os
from typing import Dict, Any
from providers.base import AIProvider
from providers.openai_provider import OpenAIProvider
from providers.claude_code_provider import ClaudeCodeProvider


class AIClient:
    """Factory class for creating AI provider instances."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize AIClient with configuration.
        
        Args:
            config: Configuration dictionary. If None, loads from environment.
        """
        if config is None:
            config = self._load_config_from_env()
        
        self.provider = self._create_provider(config)
    
    def _load_config_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        provider_type = os.getenv("AI_PROVIDER", "openai").lower()
        
        config = {
            "provider": provider_type
        }
        
        if provider_type == "openai":
            config["api_key"] = os.getenv("OPENAI_API_KEY")
            config["model"] = os.getenv("OPENAI_MODEL", "gpt-4o")
        elif provider_type == "claude-code":
            print("")
            config["claude_code_path"] = os.getenv("CLAUDE_CODE_PATH", "claude")
            print("claude path", config["claude_code_path"])
            config["model"] = os.getenv("CLAUDE_CODE_MODEL", "claude-4-5-sonnet-20250929")
        
        return config
    
    def _create_provider(self, config: Dict[str, Any]) -> AIProvider:
        """
        Create the appropriate provider instance.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            AIProvider instance
            
        Raises:
            ValueError: If provider type is unknown
        """
        provider_type = config.get("provider", "openai").lower()
        
        if provider_type == "openai":
            return OpenAIProvider(config)
        elif provider_type == "claude-code":
            return ClaudeCodeProvider(config)
        else:
            raise ValueError(
                f"Unknown provider: {provider_type}. "
                f"Supported providers: openai, claude-code"
            )
    
    async def stream_message(self, conversation_history, working_dir: str = None, mode: str = "ACT"):
        """
        Stream a message from the configured AI provider.
        
        Args:
            conversation_history: List of previous messages
            working_dir: Working directory path
            mode: Execution mode (ACT or PLAN)
            
        Yields:
            Dict with 'type' and content (text or tool_use)
        """
        async for chunk in self.provider.stream_message(conversation_history, working_dir, mode):
            yield chunk
