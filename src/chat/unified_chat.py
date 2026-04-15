#!/usr/bin/env python
"""
Unified chat API handler - single entry point for all chat queries.
Intelligently routes to analysis or screener embeddings based on context.
"""

import logging
import re
from typing import Dict, Optional, List
from src.chat import StockAnalysisChat, MultiStockChat

logger = logging.getLogger(__name__)


class UnifiedChatHandler:
    """Smart chat handler that detects context and routes appropriately."""
    
    def __init__(self, llm_provider: str = None):
        """Initialize with both chat interfaces."""
        self.analysis_chat = StockAnalysisChat(llm_provider=llm_provider)
        self.multi_stock_chat = MultiStockChat(llm_provider=llm_provider)
        logger.info("Initialized UnifiedChatHandler")
    
    def extract_stocks_from_query(self, query: str) -> List[str]:
        """
        Extract stock symbols mentioned in the query.
        Looks for uppercase text that looks like stock symbols (2-12 chars).
        """
        # Common stock symbol patterns
        stock_indicators = ['stock', 'ticker', 'symbol', 'company']
        
        # Extract potential stock symbols (uppercase words)
        words = query.split()
        candidates = []
        
        for word in words:
            # Clean word of punctuation
            clean_word = re.sub(r'[^\w]', '', word)
            # Check if it looks like a stock symbol (supports longer names like EICHERMOT, APOLLOHOSP)
            if 2 <= len(clean_word) <= 12 and clean_word.isupper():
                candidates.append(clean_word)
        
        # Remove duplicates while preserving order
        seen = set()
        stocks = []
        for stock in candidates:
            if stock not in seen:
                stocks.append(stock)
                seen.add(stock)
        
        return stocks
    
    def is_single_stock_query(self, query: str, stocks: List[str]) -> bool:
        """Determine if this is a single-stock analysis query."""
        query_lower = query.lower()
        
        # If asking about multiple stocks → not single stock
        if len(stocks) > 1:
            return False
        
        # If no stocks mentioned → not single stock
        if len(stocks) == 0:
            return False
        
        # If asking for comparison/list → not single stock
        if any(word in query_lower for word in ['compare', 'vs', 'versus', 'which', 'top', 'list', 'all']):
            return False
        
        # Single stock query patterns
        single_stock_indicators = [
            'target price', 'fair value', 'recommendation', 'rating',
            'investment', 'thesis', 'outlook', 'analysis',
            'business', 'overview', 'valuation', 'dividend',
            'roe', 'roce', 'pe', 'p/e', 'eps', 'growth',
            'margin', 'debt', 'cash flow'
        ]
        
        # If asking about analysis metrics → single stock query
        if any(indicator in query_lower for indicator in single_stock_indicators):
            return True
        
        # If asking about fundamental data → lean towards single stock
        if any(word in query_lower for word in ['what', 'how', 'tell', 'explain', 'describe']):
            return True
        
        return False
    
    def answer(self, query: str) -> Dict:
        """
        Answer a chat query - intelligently routes to analysis or screener.
        
        Args:
            query: User's question (can mention stock symbols)
            
        Returns:
            Dict with answer, sources, confidence, routing info
        """
        logger.info(f"Unified chat query: {query}")
        
        # Extract stocks mentioned in query
        stocks = self.extract_stocks_from_query(query)
        logger.info(f"Extracted stocks: {stocks}")
        
        # Determine routing
        if self.is_single_stock_query(query, stocks):
            # Single stock analysis query
            stock = stocks[0]
            logger.info(f"Routing to analysis chat for {stock}")
            
            result = self.analysis_chat.answer_question(query, stock, top_k=5, debug=False)
            result['routing'] = 'analysis_embeddings'
            return result
        
        elif stocks or any(word in query.lower() for word in ['stocks', 'companies', 'sectors', 'list', 'top', 'highest', 'lowest']):
            # Cross-stock screener query
            logger.info(f"Routing to screener chat with stocks: {stocks}")
            
            result = self.multi_stock_chat.answer_question(
                query=query,
                stock=None,
                stocks=stocks if stocks else None
            )
            result['routing'] = 'screener_embeddings'
            return result
        
        else:
            # No clear routing - treat as screener query
            logger.info("No clear routing detected - using screener")
            
            result = self.multi_stock_chat.answer_screener_query(query)
            result['routing'] = 'screener_embeddings'
            return result


# Global instance
_unified_handler = None


def get_unified_chat_handler(llm_provider: str = None) -> UnifiedChatHandler:
    """Get or create the unified chat handler."""
    global _unified_handler
    if _unified_handler is None:
        _unified_handler = UnifiedChatHandler(llm_provider=llm_provider)
    return _unified_handler
