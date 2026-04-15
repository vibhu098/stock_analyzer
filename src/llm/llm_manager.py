"""LangChain LLM integration - supports both OpenAI and Claude/Anthropic."""

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from src.common import settings
from typing import List
import sys


class LLMManager:
    """Manager for LangChain LLM operations with support for multiple providers."""
    
    def __init__(self, provider: str = None):
        """Initialize LLM manager with specified or configured provider.
        
        Args:
            provider: Optional provider override ('openai' or 'claude'). 
                     If not provided, uses LLM_PROVIDER env var (default: 'claude')
        """
        # Use provided provider or fall back to settings
        self.provider = (provider or settings.llm_provider).lower()
        
        if self.provider == "openai":
            self._init_openai()
        elif self.provider == "claude":
            self._init_claude()
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}. Use 'openai' or 'claude'")
        
        print(f"✓ Initialized {self.provider.upper()} LLM provider")
    
    def _init_openai(self):
        """Initialize OpenAI LLM."""
        try:
            from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        except ImportError:
            print("ERROR: langchain-openai not installed. Install with: pip install langchain-openai")
            sys.exit(1)
        
        if not settings.openai_api_key:
            print("ERROR: OPENAI_API_KEY not set in environment variables")
            sys.exit(1)
        
        self.llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            model_name=settings.openai_model,
            temperature=0.7,
            max_tokens=2048
        )
        self.embeddings = OpenAIEmbeddings(
            api_key=settings.openai_api_key,
            model="text-embedding-3-small"
        )
    
    def _init_claude(self):
        """Initialize Claude/Anthropic LLM."""
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            print("ERROR: langchain-anthropic not installed. Install with: pip install langchain-anthropic")
            sys.exit(1)
        
        if not settings.claude_api_key:
            print("ERROR: ANTHROPIC_API_KEY not set in environment variables")
            sys.exit(1)
        
        self.llm = ChatAnthropic(
            api_key=settings.claude_api_key,
            model=settings.claude_model,
            temperature=0.7,
            max_tokens=4096
        )
        self.embeddings = None  # Claude API does not provide embeddings
    
    def get_llm(self):
        """Get the LangChain LLM instance."""
        return self.llm
    
    def get_embeddings(self):
        """Get embeddings instance.
        
        Returns:
            Embeddings instance if using OpenAI, None if using Claude
            (Claude API does not provide embeddings)
        """
        if self.provider == "openai" and self.embeddings:
            return self.embeddings
        elif self.provider == "claude":
            print("Note: Claude API does not provide embeddings. Use alternative embedding service or OpenAI provider.")
            return None
        return None
    
    def embed_text(self, text: str) -> List[float]:
        """Embed a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector (OpenAI only)
            
        Raises:
            NotImplementedError: If using Claude provider without embeddings
        """
        if self.provider == "openai":
            if self.embeddings:
                return self.embeddings.embed_query(text)
            else:
                raise RuntimeError("OpenAI embeddings not initialized")
        else:
            raise NotImplementedError(f"{self.provider.upper()} provider does not support embeddings. Use 'openai' provider for embeddings.")
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors (OpenAI only)
            
        Raises:
            NotImplementedError: If using Claude provider without embeddings
        """
        if self.provider == "openai":
            if self.embeddings:
                return self.embeddings.embed_documents(texts)
            else:
                raise RuntimeError("OpenAI embeddings not initialized")
        else:
            raise NotImplementedError(f"{self.provider.upper()} provider does not support embeddings. Use 'openai' provider for embeddings.")
    
    def create_chain(self, prompt_template: str, input_variables: List[str]):
        """Create a LangChain chain with a prompt template.
        
        Args:
            prompt_template: Template string for the prompt
            input_variables: Variables to fill in the template
            
        Returns:
            Runnable chain instance
        """
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=input_variables
        )
        # Create a simple chain using the pipe operator
        chain = prompt | self.llm
        return chain
    
    def generate_response(self, prompt: str) -> str:
        """Generate a response from the LLM.
        
        Args:
            prompt: Input prompt
            
        Returns:
            LLM response
        """
        response = self.llm.invoke(prompt)
        return response.content
