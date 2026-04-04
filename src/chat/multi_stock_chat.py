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
    
    def detect_query_type(self, query: str) -> str:
        """
        Detect what type of query this is.
        
        Returns:
            'screener' - cross-stock financial data query
            'single_analysis' - question about one stock's analysis
            'comparison' - comparing multiple stocks
            'hybrid' - combination of above
        """
        query_lower = query.lower()
        
        # Check if it's comparing stocks
        if any(word in query_lower for word in ['compare', 'vs', 'versus', 'better', 'which']):
            return 'comparison'
        
        # Check if it mentions multiple stocks
        stock_count = sum(1 for word in query_lower.split() if len(word) <= 3 and word.isupper())
        if stock_count >= 2:
            return 'comparison'
        
        # Check if it's asking about aggregates/across stocks
        if any(word in query_lower for word in ['stocks', 'companies', 'sectors', 'all', 'list', 'top', 'highest', 'lowest', 'most']):
            return 'screener'
        
        # Check if it's analysis-specific
        if any(word in query_lower for word in ['analysis', 'report', 'outlook', 'recommendation', 'valuation', 'thesis']):
            return 'single_analysis'
        
        # Default to hybrid - could be either
        return 'hybrid'
    
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
    
    def answer_analysis_query(
        self,
        query: str,
        stock: str,
        top_k: int = 5
    ) -> Dict:
        """
        Answer a query about a specific stock's analysis.
        
        Args:
            query: User's question about the stock
            stock: Stock symbol
            top_k: Number of relevant sections to retrieve
            
        Returns:
            Dict with answer, sources, confidence
        """
        logger.info(f"Analysis query for {stock}: {query}")
        
        # Search analysis embeddings
        search_results = self.analysis_store.search_analysis(query, stock, top_k=top_k)
        
        if not search_results:
            return {
                'answer': f"No analysis found for {stock}. Please run analysis first.",
                'sources': [],
                'confidence': 0,
                'query_type': 'single_analysis'
            }
        
        # Build context
        context_parts = []
        sources = set()
        
        for chunk, section, distance in search_results:
            context_parts.append(f"[{section.upper()}]\n{chunk}")
            sources.add(section)
        
        context = "\n---\n".join(context_parts)
        
        # Generate answer
        prompt = f"""You are an expert stock analyst reviewing a company analysis.

STOCK: {stock}
USER QUESTION: {query}

RELEVANT ANALYSIS EXCERPTS:
{context}

Based on the analysis excerpts above, answer the user's question directly and concisely.
Cite which sections of the analysis support your answer."""
        
        try:
            response = self.llm.invoke(prompt)
            answer = response.content if hasattr(response, 'content') else str(response)
            
            return {
                'answer': answer,
                'sources': list(sources),
                'confidence': min(1.0, 1 - (search_results[0][2] if search_results else 0.5)),
                'query_type': 'single_analysis'
            }
        except Exception as e:
            logger.error(f"Error generating analysis answer: {e}")
            return {
                'answer': f"Error: {str(e)}",
                'sources': list(sources),
                'confidence': 0,
                'query_type': 'single_analysis'
            }
    
    def answer_question(
        self,
        query: str,
        stock: Optional[str] = None,
        stocks: Optional[List[str]] = None
    ) -> Dict:
        """
        Answer a question about stocks - intelligently routes to screener or analysis.
        
        Args:
            query: User's question
            stock: Single stock (for analysis queries)
            stocks: Multiple stocks (for cross-stock queries)
            
        Returns:
            Dict with answer, sources, confidence, query_type
        """
        query_type = self.detect_query_type(query)
        
        logger.info(f"Detected query type: {query_type}")
        
        # Route to appropriate handler
        if stock and query_type in ['single_analysis', 'hybrid']:
            # Try analysis first if stock is specified
            return self.answer_analysis_query(query, stock, top_k=5)
        
        elif stocks or query_type in ['screener', 'comparison']:
            # Multi-stock query
            return self.answer_screener_query(query, stocks=stocks, top_k=10)
        
        else:
            # Default to screener for general queries
            return self.answer_screener_query(query, stocks=None, top_k=10)
