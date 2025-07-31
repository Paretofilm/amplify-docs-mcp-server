#!/usr/bin/env python3
"""Quick test to verify the fetchLatestDocs functionality."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def test_fetch():
    """Test fetching a few documents."""
    from amplify_docs_server import AmplifyDocsScraper, AmplifyDocsDatabase
    
    print("Testing document fetching with 5 pages...")
    
    db = AmplifyDocsDatabase()
    scraped_count = 0
    errors = 0
    
    async with AmplifyDocsScraper() as scraper:
        # Discover URLs with shallow depth
        discovered_urls = await scraper.discover_urls(scraper.base_url, max_depth=1)
        discovered_urls = discovered_urls[:5]  # Only test with 5 pages
        
        print(f"Found {len(discovered_urls)} URLs to test")
        
        # Scrape each URL
        for i, url in enumerate(discovered_urls):
            print(f"  [{i+1}/5] Fetching: {url}")
            doc_data = await scraper.fetch_page(url)
            if doc_data:
                if db.save_document(doc_data):
                    scraped_count += 1
                    print(f"    ✓ Saved: {doc_data['title']}")
                else:
                    errors += 1
                    print(f"    ✗ Failed to save")
            else:
                errors += 1
                print(f"    ✗ Failed to fetch")
    
    print(f"\nTest completed! Scraped {scraped_count} documents, {errors} errors.")
    
    # Show stats
    stats = db.get_stats()
    print(f"\nDatabase stats:")
    print(f"  Total documents: {stats.get('total_documents', 0)}")
    print(f"  Categories: {stats.get('categories', {})}")

if __name__ == "__main__":
    asyncio.run(test_fetch())