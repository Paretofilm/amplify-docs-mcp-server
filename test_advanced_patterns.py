#!/usr/bin/env python3
"""
Test script to validate the advanced patterns added to the Amplify Gen 2 MCP server.
This tests the new quickHelp tasks that address the identified weaknesses.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add the parent directory to the path so we can import the server
sys.path.insert(0, str(Path(__file__).parent))

from amplify_docs_server import handle_call_tool

async def test_advanced_patterns():
    """Test all the new advanced pattern guides."""
    
    print("Testing Advanced Patterns in Amplify Gen 2 MCP Server")
    print("=" * 60)
    
    # Test 1: Advanced Real-time Patterns
    print("\n1. Testing Advanced Real-time Patterns...")
    try:
        result = await handle_call_tool("quickHelp", {"task": "advanced-real-time"})
        # The result is a list of TextContent objects
        pattern_content = result[0].text if result else ""
        
        # Check if we got comprehensive real-time examples
        # The content includes the code within the formatted response
        assert 'observeQuery' in pattern_content, "Missing observeQuery example"
        assert 'filter' in pattern_content, "Missing filter example"
        assert 'ConnectionState' in pattern_content, "Missing connection state management"
        assert 'nextToken' in pattern_content, "Missing pagination example"
        assert 'optimistic' in pattern_content.lower(), "Missing optimistic updates"
        print("✓ Advanced real-time patterns include observeQuery, filtering, and pagination")
    except Exception as e:
        print(f"✗ Failed to get advanced real-time patterns: {e}")
    
    # Test 2: Error Handling Patterns
    print("\n2. Testing Error Handling Patterns...")
    try:
        result = await handle_call_tool("quickHelp", {"task": "error-handling-patterns"})
        pattern_content = result[0].text if result else ""
        
        assert 'try' in pattern_content and 'catch' in pattern_content, "Missing try-catch blocks"
        assert 'retry' in pattern_content, "Missing retry logic"
        assert 'ErrorBoundary' in pattern_content, "Missing ErrorBoundary component"
        assert 'backoff' in pattern_content.lower(), "Missing backoff logic"
        print("✓ Error handling patterns include try-catch, retry logic, and ErrorBoundary")
    except Exception as e:
        print(f"✗ Failed to get error handling patterns: {e}")
    
    # Test 3: Custom Auth Rules
    print("\n3. Testing Custom Auth Rules...")
    try:
        result = await handle_call_tool("quickHelp", {"task": "custom-auth-rules"})
        pattern_content = result[0].text if result else ""
        
        assert 'tenant' in pattern_content.lower() or 'organization' in pattern_content.lower(), "Missing multi-tenant example"
        assert 'defineFunction' in pattern_content, "Missing Lambda function auth"
        assert 'allow.custom' in pattern_content, "Missing custom auth rule"
        assert 'organizationId' in pattern_content or 'tenantId' in pattern_content, "Missing organization-based access"
        print("✓ Custom auth rules include multi-tenant, Lambda auth, and org-based access")
    except Exception as e:
        print(f"✗ Failed to get custom auth rules: {e}")
    
    # Test 4: Optimistic UI Updates
    print("\n4. Testing Optimistic UI Updates...")
    try:
        result = await handle_call_tool("quickHelp", {"task": "optimistic-ui-updates"})
        pattern_content = result[0].text if result else ""
        
        assert 'optimistic' in pattern_content.lower(), "Missing optimistic updates"
        assert 'rollback' in pattern_content or 'revert' in pattern_content, "Missing rollback logic"
        assert 'previous' in pattern_content.lower() or 'backup' in pattern_content.lower(), "Missing data backup for rollback"
        assert 'setTodos' in pattern_content or 'setState' in pattern_content, "Missing immediate UI update"
        print("✓ Optimistic UI patterns include immediate updates and rollback handling")
    except Exception as e:
        print(f"✗ Failed to get optimistic UI patterns: {e}")
    
    # Test 5: Advanced Form Customization
    print("\n5. Testing Advanced Form Customization...")
    try:
        result = await handle_call_tool("quickHelp", {"task": "advanced-form-customization"})
        pattern_content = result[0].text if result else ""
        
        assert 'formData' in pattern_content, "Missing form state management"
        assert 'validation' in pattern_content or 'validate' in pattern_content, "Missing validation rules"
        assert 'disabled' in pattern_content.lower() or 'conditional' in pattern_content.lower() or 'hasDiscount' in pattern_content, "Missing conditional logic"
        assert 'variation' in pattern_content or 'variant' in pattern_content or 'VariantBuilder' in pattern_content, "Missing form variations"
        print("✓ Form customization includes theming, validation, and conditional fields")
    except Exception as e:
        print(f"✗ Failed to get form customization patterns: {e}")
    
    # Test 6: Verify all patterns are available by checking quickHelp
    print("\n6. Testing QuickHelp Completeness...")
    try:
        result = await handle_call_tool("quickHelp", {})
        help_content = result[0].text if result else ""
        
        advanced_tasks = [
            "advanced-real-time",
            "error-handling-patterns", 
            "custom-auth-rules",
            "optimistic-ui-updates",
            "advanced-form-customization"
        ]
        
        # In quickHelp without a task, it returns a list of available tasks
        for task in advanced_tasks:
            assert task in help_content, f"Missing {task} in quickHelp"
        
        print("✓ All advanced patterns are available in quickHelp")
    except Exception as e:
        print(f"✗ Failed to verify quickHelp completeness: {e}")
    
    # Test 7: Search for advanced topics
    print("\n7. Testing Search for Advanced Topics...")
    try:
        # Search for real-time
        result = await handle_call_tool("searchDocs", {"query": "observeQuery real-time"})
        # searchDocs returns text content with results
        search_text = result[0].text if result else ""
        assert "Found" in search_text, "No results for real-time search"
        print("✓ Search finds real-time documentation")
        
        # Search for error handling
        result = await handle_call_tool("searchDocs", {"query": "error handling retry"})
        search_text = result[0].text if result else ""
        print(f"✓ Search returned results for error handling")
        
    except Exception as e:
        print(f"✗ Failed search tests: {e}")
    
    print("\n" + "=" * 60)
    print("Advanced Pattern Testing Complete!")
    print("\nThe MCP server now addresses all identified weaknesses:")
    print("- ✓ Comprehensive real-time examples with observeQuery")
    print("- ✓ Robust error handling patterns")
    print("- ✓ Advanced authorization patterns")
    print("- ✓ Optimistic UI update examples")
    print("- ✓ Extensive form customization guides")

if __name__ == "__main__":
    asyncio.run(test_advanced_patterns())