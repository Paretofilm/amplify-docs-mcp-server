#!/usr/bin/env python3
"""
Debug script to check the output of getCleanStarterConfig.
"""

import asyncio
import sys
from pathlib import Path

# Add the parent directory to the path so we can import the server
sys.path.insert(0, str(Path(__file__).parent))

from amplify_docs_server import handle_call_tool

async def debug_output():
    """Debug getCleanStarterConfig output."""
    
    print("Testing getCleanStarterConfig with includeAuth=False")
    print("=" * 60)
    
    result = await handle_call_tool("getCleanStarterConfig", {
        "includeAuth": False,
        "includeStorage": True,
        "includeData": True,
        "styling": "css"
    })
    
    content = result[0].text if result else ""
    
    # Save to file for inspection
    with open("debug_output.txt", "w") as f:
        f.write(content)
    
    print("Output saved to debug_output.txt")
    
    # Check for auth references
    auth_refs = []
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'auth' in line.lower():
            auth_refs.append((i+1, line.strip()))
    
    print(f"\nFound {len(auth_refs)} lines containing 'auth':")
    for line_num, line in auth_refs[:10]:  # Show first 10
        print(f"  Line {line_num}: {line[:80]}...")

if __name__ == "__main__":
    asyncio.run(debug_output())