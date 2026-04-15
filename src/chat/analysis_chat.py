"""Chat feature for asking questions about stock analysis reports using embeddings."""

import logging
from typing import Dict, List, Optional
from src.embeddings import AnalysisEmbeddingStore
from src.llm import LLMManager
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


class StockAnalysisChat:
    """Chat interface for Q&A on stock analysis reports using semantic search."""
    
    def __init__(self, llm_provider: str = None):
        """
        Initialize chat feature.
        
        Args:
            llm_provider: LLM provider ('claude' or 'openai'). Uses env var if not specified.
        """
        self.embedding_store = AnalysisEmbeddingStore()
        self.llm_manager = LLMManager(provider=llm_provider)
        self.llm = self.llm_manager.get_llm()
        
        logger.info("Initialized StockAnalysisChat")
    
    def answer_question(
        self,
        question: str,
        symbol: str,
        top_k: int = 5,
        debug: bool = False
    ) -> Dict[str, any]:
        """
        Answer a question about stock analysis using semantic search + LLM.
        
        This is a RAG (Retrieval-Augmented Generation) approach:
        1. Search embeddings for relevant analysis sections
        2. Pass retrieved content + question to LLM
        3. LLM synthesizes answer based on actual report
        
        Args:
            question: User's question about the stock
            symbol: Stock symbol to ask about
            top_k: Number of similar chunks to retrieve
            debug: Print debug info
        
        Returns:
            Dict with keys:
            - 'answer': LLM's answer to the question
            - 'sources': List of relevant sections found
            - 'confidence': How confident the answer is
            - 'debug_info': Retrieved chunks (if debug=True)
        """
        logger.info(f"Answering question about {symbol}: {question}")
        
        # Search for relevant content
        search_results = self.embedding_store.search_analysis(question, symbol, top_k=top_k)
        
        if not search_results:
            return {
                'answer': f"⚠️  No analysis found for {symbol}. Please run analysis first.",
                'sources': [],
                'confidence': 0,
                'debug_info': None
            }
        
        # Prepare context from search results
        context_parts = []
        sources = set()
        
        for chunk, section, distance in search_results:
            context_parts.append(f"[{section.upper()}]\n{chunk}\n")
            sources.add(section)
        
        context = "\n---\n".join(context_parts)
        
        # Build prompt for LLM
        prompt = f"""You are an expert stock analyst. A user has asked a question about a stock analysis report.

STOCK: {symbol}

USER QUESTION: {question}

RELEVANT ANALYSIS EXCERPTS:
{context}

Based on the analysis excerpts above, answer the user's question directly and concisely.
If the answer is not found in the analysis, say so clearly.
Cite which sections of the analysis support your answer."""
        
        if debug:
            print("\n" + "="*80)
            print("DEBUG: CHAT QUESTION")
            print("="*80)
            print(f"Symbol: {symbol}")
            print(f"Question: {question}")
            print(f"Retrieved {len(search_results)} chunks from sections: {', '.join(sources)}")
            print("\nContext sent to LLM:")
            print(context[:500] + "..." if len(context) > 500 else context)
            print("="*80 + "\n")
        
        try:
            # Get answer from LLM
            response = self.llm.invoke([
                HumanMessage(content="You are an expert stock analyst answering questions about detailed equity analysis reports."),
                HumanMessage(content=prompt)
            ])
            
            answer = response.content
            
            # Calculate confidence based on similarity scores
            avg_distance = sum(d for _, _, d in search_results) / len(search_results)
            # Normalize: lower distance = higher confidence (L2 distance)
            # Typical range is 0-2, so confidence = 1 - (distance/2)
            confidence = max(0, 1 - (avg_distance / 2))
            
            return {
                'answer': answer,
                'sources': list(sources),
                'confidence': float(confidence),
                'num_chunks_used': len(search_results),
                'debug_info': search_results if debug else None
            }
        
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return {
                'answer': f"Error generating answer: {str(e)}",
                'sources': list(sources),
                'confidence': 0,
                'debug_info': None
            }
