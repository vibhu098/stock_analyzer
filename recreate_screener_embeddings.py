#!/usr/bin/env python
"""Script to recreate screener embeddings with updated embedding model."""

import logging
import shutil
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

print("\n" + "="*80)
print("RECREATING SCREENER EMBEDDINGS")
print("="*80 + "\n")

try:
    from src.embeddings import ScreenerEmbeddingStore
    
    # Remove old screener embeddings
    old_emb_dir = Path('embeddings/screener')
    if old_emb_dir.exists():
        print("[1] Removing old screener embeddings...")
        shutil.rmtree(old_emb_dir)
        print("    ✓ Old embeddings removed\n")
    
    # Create new store and embed all stocks
    print("[2] Creating new screener embedding store...")
    store = ScreenerEmbeddingStore()
    
    # Get available stocks
    stocks = []
    static_dir = Path('static')
    if static_dir.exists():
        stocks = [item.name for item in static_dir.iterdir() if item.is_dir() and not item.name.startswith('.')]
    
    print(f"    Found {len(stocks)} stocks: {sorted(stocks)[:5]}...\n")
    
    # Embed all stocks
    print("[3] Embedding all stocks...")
    success_count = 0
    for stock in sorted(stocks):
        try:
            success = store.embed_stock_data(stock)
            if success:
                print(f"    ✓ {stock}: Embedded successfully")
                success_count += 1
            else:
                print(f"    ✗ {stock}: Failed to embed")
        except Exception as e:
            print(f"    ✗ {stock}: Error - {e}")
    
    # Verify embeddings were created
    print(f"\n[4] Verifying embeddings...")
    emb_dir = Path('embeddings/screener')
    if emb_dir.exists():
        stock_dirs = [d for d in emb_dir.iterdir() if d.is_dir()]
        print(f"    ✓ Created embeddings for {len(stock_dirs)} stocks")
        for stock_dir in sorted(stock_dirs)[:3]:
            files = list(stock_dir.glob('*'))
            print(f"      - {stock_dir.name}: {len(files)} files")
    else:
        print("    ✗ Embeddings directory not found")
    
    print("\n" + "="*80)
    print(f"✓ SCREENER EMBEDDINGS RECREATED ({success_count} stocks)")
    print("="*80 + "\n")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
