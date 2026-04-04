#!/usr/bin/env python3
"""
Embed all screener CSV data for cross-stock search.

This script:
1. Loads all CSV files from static/ stock folders
2. Creates embeddings for each stock's financial data
3. Saves FAISS indices for fast semantic search
4. Enables cross-stock queries like "stocks with P/E < 20"

Usage:
    python embed_screener_data.py

The embeddings are stored in: embeddings/screener/{STOCK}/
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Embed all screener data."""
    
    try:
        from src.embeddings import ScreenerEmbeddingStore
        
        logger.info("="*80)
        logger.info("SCREENER DATA EMBEDDING")
        logger.info("="*80)
        
        # Initialize store
        store = ScreenerEmbeddingStore()
        
        logger.info(f"\n📂 CSV Folder: {store.csv_folder}")
        logger.info(f"💾 Embeddings Folder: {store.embedding_folder}\n")
        
        # Embed all stocks
        logger.info("🔄 Starting embedding process...\n")
        results = store.embed_all_stocks()
        
        # Show results
        logger.info("\n" + "="*80)
        logger.info("EMBEDDING RESULTS")
        logger.info("="*80)
        
        success_count = 0
        fail_count = 0
        
        for stock, success in sorted(results.items()):
            status = "✅" if success else "❌"
            outcome = "Embedded successfully" if success else "Failed to embed"
            logger.info(f"{status} {stock:15s} - {outcome}")
            
            if success:
                success_count += 1
            else:
                fail_count += 1
        
        logger.info("\n" + "="*80)
        logger.info(f"SUMMARY: {success_count} successful, {fail_count} failed out of {len(results)} stocks")
        logger.info("="*80)
        
        if success_count > 0:
            logger.info("\n✅ You can now use multi-stock chat queries!")
            logger.info("   Example: 'Which stocks have price less than 200?'")
            logger.info("   Example: 'Show me stocks with P/E > 30'")
        
        return 0 if fail_count == 0 else 1
        
    except Exception as e:
        logger.error(f"❌ Error during embedding: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
