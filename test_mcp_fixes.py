#!/usr/bin/env python3
"""Test script to verify MCP server fixes."""

import asyncio
import logging
from amplify_docs_server import AmplifyDocsDatabase, handle_call_tool

# Set up logging to see debug output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_fixes():
    print("Testing MCP Server Fixes...\n")
    
    db = AmplifyDocsDatabase()
    
    # Test 1: Category Search
    print("=" * 50)
    print("Test 1: Dynamic Category Search")
    print("=" * 50)
    categories = db.list_categories()
    print(f"Available categories from database: {sorted(categories)}")
    
    # Test search in each category
    print("\nTesting search in first 3 categories:")
    for cat in sorted(categories)[:3]:
        results = db.search_documents("test", category=cat, limit=2)
        print(f"  {cat}: {len(results)} results")
        if results:
            print(f"    - First result: {results[0]['title'][:50]}...")
    
    # Test invalid category
    print("\nTesting invalid category handling:")
    result = await handle_call_tool("searchDocs", {"query": "test", "category": "invalid-category"})
    print(f"  Response preview: {result[0].text[:200]}...")
    
    # Test 2: Pattern Search
    print("\n" + "=" * 50)
    print("Test 2: Pattern Type Filtering")
    print("=" * 50)
    
    # Test API patterns (should NOT return storage)
    print("\nTesting findPatterns('api') - should exclude storage:")
    result = await handle_call_tool("findPatterns", {"pattern_type": "api"})
    api_text = result[0].text
    if "storage" in api_text.lower() and "s3" in api_text.lower():
        print("  ❌ FAIL: Storage content found in API patterns!")
    else:
        print("  ✅ PASS: No storage content in API patterns")
    print(f"  First 200 chars: {api_text[:200]}...")
    
    # Test Data patterns (should focus on defineData)
    print("\nTesting findPatterns('data') - should return defineData examples:")
    result = await handle_call_tool("findPatterns", {"pattern_type": "data"})
    data_text = result[0].text
    if "defineData" in data_text or "model" in data_text or "schema" in data_text:
        print("  ✅ PASS: Data patterns include defineData/model/schema")
    else:
        print("  ❌ FAIL: Data patterns missing defineData content")
    print(f"  First 200 chars: {data_text[:200]}...")
    
    # Test Storage patterns (should be storage-specific)
    print("\nTesting findPatterns('storage') - should return storage content:")
    result = await handle_call_tool("findPatterns", {"pattern_type": "storage"})
    storage_text = result[0].text
    if "storage" in storage_text.lower() or "upload" in storage_text.lower():
        print("  ✅ PASS: Storage patterns include storage content")
    else:
        print("  ❌ FAIL: Storage patterns missing storage content")
    print(f"  First 200 chars: {storage_text[:200]}...")
    
    # Test 3: CRUD Forms
    print("\n" + "=" * 50)
    print("Test 3: CRUD Form Documentation")
    print("=" * 50)
    crud_results = db.search_documents("CRUD form generation formbuilder", limit=5)
    print(f"Found {len(crud_results)} CRUD form docs")
    for i, r in enumerate(crud_results[:3]):
        print(f"  {i+1}. {r['title']} (category: {r['category']})")
    
    # Test quickHelp for CRUD forms
    print("\nTesting quickHelp for CRUD forms:")
    result = await handle_call_tool("quickHelp", {"task": "generate-crud-forms"})
    if "npx ampx generate forms" in result[0].text:
        print("  ✅ PASS: quickHelp includes CRUD form generation command")
    else:
        print("  ❌ FAIL: quickHelp missing CRUD form generation command")
    
    # Test 4: Data Documentation
    print("\n" + "=" * 50)
    print("Test 4: Amplify Data Documentation")
    print("=" * 50)
    data_results = db.search_documents("defineData model schema", limit=5)
    print(f"Found {len(data_results)} data model docs")
    for i, r in enumerate(data_results[:3]):
        print(f"  {i+1}. {r['title']} (category: {r['category']})")
    
    # Check categories distribution
    categories_found = {}
    for r in data_results:
        cat = r['category']
        categories_found[cat] = categories_found.get(cat, 0) + 1
    print(f"\nCategories distribution: {categories_found}")
    
    print("\n" + "=" * 50)
    print("All tests completed!")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(test_fixes())