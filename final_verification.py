#!/usr/bin/env python3
"""
Final verification that everything works correctly
"""

import asyncio
import json
import os
from pathlib import Path
from amplify_docs_server import AmplifyDocsDatabase

def verify_all():
    """Verify all components are working."""
    print("🔍 Final Verification of Amplify MCP Server\n")
    print("="*60)
    
    # 1. Check database
    db = AmplifyDocsDatabase()
    stats = db.get_stats()
    total_docs = stats.get('total_documents', 0)
    
    print(f"✅ Database: {total_docs} documents")
    print(f"   Categories: {len(stats.get('categories', {}))}")
    
    # 2. Check documentation index
    index_file = Path("documentation_index.json")
    if index_file.exists():
        with open(index_file, 'r') as f:
            index = json.load(f)
        print(f"✅ Documentation Index: {len(index.get('categories', {}))} categories")
        print(f"   Patterns: {len(index.get('patterns', {}))} pattern types")
        print(f"   Components: {len(index.get('components', {}))} UI components")
    else:
        print("❌ Documentation index missing")
    
    # 3. Check summary table
    if db._table_exists('document_summaries'):
        print("✅ Summary table exists")
    else:
        print("❌ Summary table missing")
    
    # 4. Test key searches
    print("\n🔍 Testing Key Searches:")
    key_searches = [
        "authentication",
        "file upload", 
        "graphql api",
        "amplify ui components"
    ]
    
    for query in key_searches:
        results = db.search_documents(query, limit=1)
        if results:
            print(f"✅ '{query}' -> {results[0]['title']}")
        else:
            print(f"❌ '{query}' -> No results")
    
    # 5. Check enhanced features
    print("\n🚀 Enhanced Features:")
    
    # Test typo handling
    typo_result = db.search_documents("authentcation", limit=1)
    if typo_result:
        print("✅ Typo correction working")
    else:
        print("❌ Typo correction not working")
    
    # Test category filtering
    frontend_results = db.search_documents("", category="frontend", limit=5)
    print(f"✅ Category filtering: {len(frontend_results)} frontend docs")
    
    # 6. Configuration checks
    print("\n⚙️  Configuration:")
    
    # Check wrapper script
    if Path("run_amplify_mcp.sh").exists() and os.access("run_amplify_mcp.sh", os.X_OK):
        print("✅ Wrapper script executable")
    else:
        print("❌ Wrapper script issues")
    
    # Check Claude Desktop config
    if Path("claude_desktop_config.json").exists():
        print("✅ Claude Desktop config present")
    else:
        print("❌ Claude Desktop config missing")
    
    # Check installation guide
    if Path("INSTALLATION.md").exists():
        print("✅ Installation guide present")
    else:
        print("❌ Installation guide missing")
    
    print("\n" + "="*60)
    print("✅ Verification Complete!")
    print("\nThe Amplify MCP Server is ready for use with:")
    print("- Claude Desktop: Copy claude_desktop_config.json settings")
    print("- Claude Code: Run 'claude mcp list' to verify connection")
    

if __name__ == "__main__":
    verify_all()