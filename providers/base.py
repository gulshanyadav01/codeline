
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any


class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the provider.
        
        Args:
            config: Configuration dictionary containing provider-specific settings
        """
        self.config = config
    
    @abstractmethod
    async def stream_message(
        self, 
        conversation_history: list, 
        working_dir: str = None, 
        mode: str = "ACT"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream a message from the AI provider.
        
        Args:
            conversation_history: List of previous messages
            working_dir: Working directory path
            mode: Execution mode (ACT or PLAN)
            
        Yields:
            Dict with 'type' and content (text or tool_use)
        """
        pass
    
    @abstractmethod
    def _get_system_prompt(self, working_dir: str = None, mode: str = "ACT") -> str:
        """
        Generate mode-specific system prompt.
        
        Args:
            working_dir: Working directory path
            mode: Execution mode (ACT or PLAN)
            
        Returns:
            System prompt string
        """
        pass
