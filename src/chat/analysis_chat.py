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
    
    def multi_stock_search(
        self,
        query: str,
        symbols: Optional[List[str]] = None,
        top_k: int = 3
    ) -> Dict[str, List[Dict]]:
        """
        Search across multiple stocks for similar analysis content.
        
        Useful for queries like: "which stocks have P/E greater than 30?"
        
        Args:
            query: Search query (e.g., "P/E greater than 30")
            symbols: List of symbols to search. If None, searches all available.
            top_k: Results per symbol
        
        Returns:
            Dict mapping symbol → list of (chunk, section, score)
        """
        if symbols is None:
            symbols = self.embedding_store.list_stored_analyses()
        
        results = {}
        
        for symbol in symbols:
            search_results = self.embedding_store.search_analysis(query, symbol, top_k=top_k)
            if search_results:
                results[symbol] = [
                    {
                        'chunk': chunk,
                        'section': section,
                        'score': float(distance)
                    }
                    for chunk, section, distance in search_results
                ]
        
        logger.info(f"Found results in {len(results)} stocks for: {query}")
        return results
    
    def get_comparative_answer(
        self,
        question: str,
        symbols: List[str],
        debug: bool = False
    ) -> str:
        """
        Answer a comparative question across multiple stocks.
        
        Example: "Which stock is better, ASIANPAINT or TCS?"
        
        Args:
            question: Comparative question
            symbols: List of symbols to compare
            debug: Print debug info
        
        Returns:
            LLM's comparative analysis
        """
        # Gather analysis for each symbol
        context_parts = []
        
        for symbol in symbols:
            results = self.embedding_store.search_analysis(question, symbol, top_k=3)
            if results:
                context_parts.append(f"\n## {symbol}\n")
                for chunk, section, _ in results:
                    context_parts.append(f"[{section}] {chunk[:200]}...")
        
        if not context_parts:
            return f"⚠️  No analysis found for stocks: {', '.join(symbols)}"
        
        context = "\n".join(context_parts)
        
        prompt = f"""You are an expert stock analyst comparing multiple stocks.

USER QUESTION: {question}

AVAILABLE ANALYSIS FOR COMPARISON:
{context}

Provide a comprehensive comparison answering the question.
Structure your answer by stock, highlighting key differences."""
        
        try:
            response = self.llm.invoke([
                HumanMessage(content="You are an expert stock analyst."),
                HumanMessage(content=prompt)
            ])
            return response.content
        
        except Exception as e:
            logger.error(f"Error generating comparative answer: {e}")
            return f"Error: {str(e)}"


def interactive_chat(symbol: str, llm_provider: str = None):
    """
    Interactive chat interface for asking questions about stock analysis.
    
    Usage:
        python -c "from src.utils.analysis_chat import interactive_chat; interactive_chat('ASIANPAINT')"
    """
    chat = StockAnalysisChat(llm_provider=llm_provider)
    
    print(f"\n{'='*80}")
    print(f"STOCK ANALYSIS CHAT: {symbol}")
    print(f"{'='*80}")
    print("Ask questions about the stock analysis report.")
    print("Type 'quit' to exit, 'help' for examples.\n")
    
    while True:
        try:
            question = input(f"You: ").strip()
            
            if question.lower() == 'quit':
                print("Goodbye!")
                break
            
            if question.lower() == 'help':
                print("""
Examples of questions you can ask:
1. "What is the P/E ratio and how does it compare to industry average?"
2. "What are the key investment thesis points?"
3. "What is the target price and valuation recommendation?"
4. "How has the stock performed over the last year?"
5. "What are the main risks identified in the analysis?"
6. "Is this a good time to buy?"
7. "What is the company's ROE and ROCE trend?"
                """)
                continue
            
            if not question:
                continue
            
            print(f"\nSearching analysis for: {question}")
            result = chat.answer_question(question, symbol, debug=False)
            
            print(f"\n{'='*80}")
            print(f"Answer (Confidence: {result['confidence']:.1%}, Sources: {', '.join(result['sources'])})")
            print(f"{'='*80}")
            print(result['answer'])
            print()
        
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Example usage
    chat = StockAnalysisChat(llm_provider='claude')
    
    # Question 1: Specific stock question
    result = chat.answer_question(
        "What is the investment thesis for this stock?",
        "ASIANPAINT",
        debug=True
    )
    
    print(f"Answer: {result['answer']}\n")
