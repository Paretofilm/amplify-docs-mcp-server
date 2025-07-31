#!/usr/bin/env python3
"""
Test MCP tools directly to ensure they work properly
"""

import asyncio
import json
from amplify_docs_server import server, handle_call_tool

async def test_mcp_tools():
    """Test all MCP tools."""
    print("🧪 Testing MCP Tools\n")
    print("="*60)
    
    # Test 1: getDocumentationOverview (summary format)
    print("\n📚 Testing getDocumentationOverview (summary):")
    try:
        result = await handle_call_tool("getDocumentationOverview", {"format": "summary"})
        if result and result[0].text:
            print("✅ Summary overview returned")
            print(f"   Length: {len(result[0].text)} characters")
            # Show first few lines
            lines = result[0].text.split('\n')[:5]
            for line in lines:
                print(f"   {line}")
        else:
            print("❌ No summary returned")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: getDocumentationOverview (full format)
    print("\n📚 Testing getDocumentationOverview (full):")
    try:
        result = await handle_call_tool("getDocumentationOverview", {"format": "full"})
        if result and result[0].text:
            print("✅ Full overview returned")
            print(f"   Length: {len(result[0].text)} characters")
        else:
            print("❌ No full overview returned")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: searchDocs
    print("\n🔍 Testing searchDocs:")
    search_tests = [
        {"query": "authentication", "category": None},
        {"query": "file upload", "category": "frontend"},
        {"query": "graphql api", "limit": 3}
    ]
    
    for test in search_tests:
        try:
            result = await handle_call_tool("searchDocs", test)
            if result and result[0].text:
                print(f"✅ Search '{test['query']}': Found results")
                # Count number of results
                text = result[0].text
                result_count = text.count("**") // 2  # Each result has title in **
                print(f"   {result_count} results returned")
            else:
                print(f"❌ Search '{test['query']}': No results")
        except Exception as e:
            print(f"❌ Search '{test['query']}' Error: {e}")
    
    # Test 4: getDocument
    print("\n📄 Testing getDocument:")
    test_url = "https://docs.amplify.aws/nextjs/build-ui/"
    try:
        result = await handle_call_tool("getDocument", {"url": test_url})
        if result and result[0].text:
            print("✅ Document retrieved")
            print(f"   Length: {len(result[0].text)} characters")
        else:
            print("❌ Document not found")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 5: listCategories
    print("\n📁 Testing listCategories:")
    try:
        result = await handle_call_tool("listCategories", {})
        if result and result[0].text:
            print("✅ Categories listed")
            # Count categories
            lines = result[0].text.split('\n')
            cat_count = sum(1 for line in lines if line.startswith('- '))
            print(f"   {cat_count} categories found")
        else:
            print("❌ No categories returned")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 6: getStats
    print("\n📊 Testing getStats:")
    try:
        result = await handle_call_tool("getStats", {})
        if result and result[0].text:
            print("✅ Stats retrieved")
            text = result[0].text
            if "Total Documents:" in text:
                # Extract total docs
                for line in text.split('\n'):
                    if "Total Documents:" in line:
                        print(f"   {line.strip()}")
                        break
        else:
            print("❌ No stats returned")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 7: findPatterns
    print("\n🔧 Testing findPatterns:")
    pattern_types = ["auth", "api", "storage"]
    
    for pattern_type in pattern_types:
        try:
            result = await handle_call_tool("findPatterns", {"pattern_type": pattern_type})
            if result and result[0].text:
                print(f"✅ Pattern '{pattern_type}': Found examples")
                # Count code blocks
                code_blocks = result[0].text.count("```")
                print(f"   {code_blocks // 2} code examples")
            else:
                print(f"❌ Pattern '{pattern_type}': No examples")
        except Exception as e:
            print(f"❌ Pattern '{pattern_type}' Error: {e}")
    
    # Test 8: getCreateCommand
    print("\n🚀 Testing getCreateCommand:")
    try:
        result = await handle_call_tool("getCreateCommand", {})
        if result and result[0].text:
            print("✅ Create command returned")
            # Check if correct command is present
            if "npx create-amplify@latest --template nextjs" in result[0].text:
                print("   ✅ Correct command found")
            else:
                print("   ❌ Incorrect command")
        else:
            print("❌ No command returned")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 9: getQuickStartPatterns
    print("\n🎯 Testing getQuickStartPatterns:")
    tasks = ["create-app", "add-auth", "file-upload", "deploy-app"]
    
    for task in tasks:
        try:
            result = await handle_call_tool("getQuickStartPatterns", {"task": task})
            if result and result[0].text:
                print(f"✅ Task '{task}': Pattern returned")
                # Count code blocks
                code_blocks = result[0].text.count("```")
                print(f"   {code_blocks // 2} code examples")
            else:
                print(f"❌ Task '{task}': No pattern")
        except Exception as e:
            print(f"❌ Task '{task}' Error: {e}")
    
    # Test edge cases
    print("\n🔥 Testing Edge Cases:")
    
    # Invalid tool name
    try:
        result = await handle_call_tool("invalidTool", {})
        if "Unknown tool" in result[0].text:
            print("✅ Invalid tool handled correctly")
        else:
            print("❌ Invalid tool not handled")
    except Exception as e:
        print(f"✅ Invalid tool raised error (expected): {e}")
    
    # Missing required parameters
    try:
        result = await handle_call_tool("searchDocs", {})  # Missing 'query'
        print("❌ Missing parameter not caught")
    except Exception as e:
        print(f"✅ Missing parameter caught: {type(e).__name__}")
    
    print("\n" + "="*60)
    print("✅ MCP Tools Testing Complete!")


if __name__ == "__main__":
    asyncio.run(test_mcp_tools())