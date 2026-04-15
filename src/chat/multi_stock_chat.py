"""Multi-stock chat handler - handles cross-stock and analysis-based queries."""

import logging
from typing import Dict, List, Optional, Tuple
from src.llm import LLMManager
from src.embeddings import ScreenerEmbeddingStore, AnalysisEmbeddingStore

logger = logging.getLogger(__name__)


class MultiStockChat:
    """Chat interface for querying across multiple stocks using embeddings."""
    
    def __init__(self, llm_provider: str = None):
        """
        Initialize multi-stock chat.
        
        Args:
            llm_provider: LLM provider ('claude' or 'openai')
        """
        self.llm_manager = LLMManager(provider=llm_provider)
        self.llm = self.llm_manager.get_llm()
        
        # Initialize both embedding stores
        self.screener_store = ScreenerEmbeddingStore()
        self.analysis_store = AnalysisEmbeddingStore()
        
        logger.info("Initialized MultiStockChat")
    
    def answer_screener_query(
        self,
        query: str,
        stocks: Optional[List[str]] = None,
        top_k: int = 10
    ) -> Dict:
        """
        Answer a cross-stock query using screener data embeddings.
        
        Example queries:
        - "Which stocks have price less than 200?"
        - "Show me stocks with P/E > 30"
        - "Which companies have highest ROE?"
        
        Args:
            query: User's query about financial metrics
            stocks: List of stocks to search. If None, searches all.
            top_k: Number of results to retrieve
            
        Returns:
            Dict with answer, sources, confidence
        """
        logger.info(f"Screener query: {query}")
        
        # Search screener embeddings
        search_results = self.screener_store.search_stocks(query, top_k=top_k, stocks=stocks)
        
        if not search_results:
            return {
                'answer': 'No matching financial data found for your query.',
                'sources': [],
                'confidence': 0,
                'query_type': 'screener'
            }
        
        # Build context from results
        context_parts = []
        stocks_mentioned = set()
        
        for stock, chunk, data_type, similarity in search_results:
            context_parts.append(f"[{stock}] {chunk}")
            stocks_mentioned.add(stock)
        
        context = "\n\n".join(context_parts)
        
        # Generate answer using LLM with focused, concise prompt
        prompt = f"""You are a financial analyst answering a specific question about stocks.

USER QUERY: {query}

FINANCIAL DATA:
{context}

INSTRUCTIONS:
1. Answer ONLY the question asked - do NOT add extra analysis unless requested
2. Focus on the specific metric(s) mentioned in the query
3. List stocks that match the criteria with their relevant metrics
4. Keep the response concise and organized
5. Use a simple table format for multiple stocks
6. Include only the metrics relevant to the query

If the query asks about P/E, show P/E ratios. Do NOT add information about ROE, ROCE, debt, or cash flows unless specifically asked.

Answer:"""
        
        try:
            response = self.llm.invoke(prompt)
            answer = response.content if hasattr(response, 'content') else str(response)
            
            return {
                'answer': answer,
                'sources': list(stocks_mentioned),
                'confidence': min(1.0, len(search_results) / top_k),
                'query_type': 'screener'
            }
        except Exception as e:
            logger.error(f"Error generating screener answer: {e}")
            return {
                'answer': f"Error: Could not generate answer. {str(e)}",
                'sources': list(stocks_mentioned),
                'confidence': 0,
                'query_type': 'screener'
            }

    def answer_question(
        self,
        query: str,
        stock: Optional[str] = None,
        stocks: Optional[List[str]] = None
    ) -> Dict:
        """
        Answer a question about stocks using screener data.
        
        Args:
            query: User's question
            stock: Deprecated - not used
            stocks: List of stocks to search/compare
            
        Returns:
            Dict with answer, sources, confidence
        """
        logger.info(f"Answering multi-stock question: {query}")
        
        # Delegate to screener query handler
        return self.answer_screener_query(query, stocks=stocks, top_k=10)
