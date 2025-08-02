#!/usr/bin/env python3
"""
Test script for the new getCleanStarterConfig tool.
Tests various option combinations to ensure proper functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add the parent directory to the path so we can import the server
sys.path.insert(0, str(Path(__file__).parent))

from amplify_docs_server import handle_call_tool

async def test_clean_starter_config():
    """Test the getCleanStarterConfig tool with various options."""
    
    print("Testing getCleanStarterConfig Tool")
    print("=" * 60)
    
    # Test 1: Default configuration (auth only)
    print("\n1. Testing Default Configuration (auth only)...")
    try:
        result = await handle_call_tool("getCleanStarterConfig", {})
        content = result[0].text if result else ""
        
        # Check for expected content
        try:
            assert "Create Your Amplify Gen 2 + Next.js App (Clean Start)" in content
        except:
            print("   - Missing title")
            raise
        
        assert "amplify/auth/resource.ts" in content
        assert "import { defineAuth }" in content
        assert "Authentication**: Email/password auth ready to use" in content
        assert "amplify/data/resource.ts" not in content  # Should not include data by default
        assert "amplify/storage/resource.ts" not in content  # Should not include storage by default
        assert "export const backend = defineBackend({" in content
        assert "import { auth } from './auth/resource';" in content
        print("✓ Default configuration works correctly")
    except AssertionError as e:
        print(f"✗ Failed default configuration test")
        # Debug: Find what's in the backend config  
        backend_idx = content.find("defineBackend({")
        backend_end_idx = content.find("});", backend_idx)
        if backend_idx > -1:
            backend_section = content[backend_idx:backend_end_idx]
            print(f"   Backend section: {backend_section}")
            print(f"   Auth in section? {'auth' in backend_section}")
        print(f"   Error: {str(e) if str(e) else 'Assertion failed'}")
    except Exception as e:
        print(f"✗ Failed default configuration test: {e}")
    
    # Test 2: All features enabled
    print("\n2. Testing All Features Enabled...")
    try:
        result = await handle_call_tool("getCleanStarterConfig", {
            "includeAuth": True,
            "includeStorage": True,
            "includeData": True,
            "styling": "tailwind"
        })
        content = result[0].text if result else ""
        
        # Check for all components
        assert "amplify/auth/resource.ts" in content
        assert "amplify/data/resource.ts" in content
        assert "amplify/storage/resource.ts" in content
        assert "@tailwind base" in content
        assert "tailwind.config.js" in content
        assert "defineStorage" in content
        assert "defineData" in content
        assert "Authentication**: Email/password auth ready to use" in content
        assert "Data Layer**: Schema-based data modeling with real-time" in content
        assert "File Storage**: S3 storage with access controls" in content
        print("✓ All features configuration works correctly")
    except Exception as e:
        print(f"✗ Failed all features test: {e}")
    
    # Test 3: Minimal configuration (no auth)
    print("\n3. Testing Minimal Configuration (no auth)...")
    try:
        result = await handle_call_tool("getCleanStarterConfig", {
            "includeAuth": False,
            "includeStorage": False,
            "includeData": False,
            "styling": "none"
        })
        content = result[0].text if result else ""
        
        # Check for minimal setup
        assert "### 🔐 amplify/auth/resource.ts" not in content  # Auth resource file section should not exist
        assert "amplify/data/resource.ts" not in content
        assert "amplify/storage/resource.ts" not in content
        assert "Authenticator" not in content  # Home page should not have auth
        assert "/* Add your custom styles here */" in content
        assert "@tailwind" not in content
        # Check backend has empty config
        backend_start_idx = content.find("export const backend")
        if backend_start_idx > -1:
            backend_end_idx = content.find("});", backend_start_idx) + 3
            backend_section = content[backend_start_idx:backend_end_idx]
            # Should have defineBackend but no auth, data, or storage
            assert "defineBackend({" in backend_section
            # For minimal config, backend should be empty
            assert "import { auth }" not in content
            assert "import { data }" not in content  
            assert "import { storage }" not in content
        print("✓ Minimal configuration works correctly")
    except AssertionError as e:
        print(f"✗ Failed minimal configuration test")
        # Debug: Find what's in the backend config
        backend_start = content.find("export const backend")
        backend_end = content.find("});", backend_start) + 3
        if backend_start > -1:
            backend_full = content[backend_start:backend_end]
            print(f"   Found backend config: {backend_full}")
            braces_start = backend_full.find("{")
            braces_end = backend_full.find("}")
            braces_content = backend_full[braces_start+1:braces_end] if braces_start > -1 else ""
            print(f"   Braces content: '{braces_content.strip()}'")
            print(f"   Is empty? {braces_content.strip() == ''}")
        else:
            print("   No backend config found!")
        print(f"   Error: {str(e) if str(e) else 'Assertion failed'}")
    except Exception as e:
        print(f"✗ Failed minimal configuration test: {e}")
    
    # Test 4: Data and Storage without Auth
    print("\n4. Testing Data and Storage without Auth...")
    try:
        result = await handle_call_tool("getCleanStarterConfig", {
            "includeAuth": False,
            "includeStorage": True,
            "includeData": True,
            "styling": "css"
        })
        content = result[0].text if result else ""
        
        # Check configuration
        assert "### 🔐 amplify/auth/resource.ts" not in content  # Auth resource file section should not exist
        assert "amplify/data/resource.ts" in content
        assert "amplify/storage/resource.ts" in content
        assert "defineBackend" in content
        
        # Check backend imports and configuration
        assert "import { auth }" not in content  # Should not import auth
        assert "import { data }" in content
        assert "import { storage }" in content
        
        # Debug: print backend config
        backend_start = content.find("export const backend")
        backend_end = content.find("});", backend_start) + 3
        backend_config = content[backend_start:backend_end] if backend_start > -1 else "Not found"
        
        # Check backend config contains data and storage but not auth in the defineBackend call
        assert "data," in backend_config or "data\n" in backend_config
        assert "storage" in backend_config
        # Auth should not be in the defineBackend parameters
        defineBackend_start = backend_config.find("defineBackend({")
        defineBackend_end = backend_config.find("});")
        defineBackend_content = backend_config[defineBackend_start:defineBackend_end] if defineBackend_start > -1 else ""
        assert "auth" not in defineBackend_content
        print("✓ Data and Storage without Auth works correctly")
    except AssertionError as e:
        print(f"✗ Failed data/storage without auth test")
        print(f"   Backend config: {backend_config}")
        print(f"   Error: {str(e) if str(e) else 'Assertion failed'}")
    except Exception as e:
        print(f"✗ Failed data/storage without auth test: {e}")
    
    # Test 5: Check file structure instructions
    print("\n5. Testing File Structure Instructions...")
    try:
        result = await handle_call_tool("getCleanStarterConfig", {
            "includeData": True,
            "includeStorage": True
        })
        content = result[0].text if result else ""
        
        # Check mkdir commands
        assert "mkdir -p amplify/auth" in content
        assert "mkdir -p amplify/data" in content
        assert "mkdir -p amplify/storage" in content
        print("✓ File structure instructions are correct")
    except Exception as e:
        print(f"✗ Failed file structure test: {e}")
    
    # Test 6: CSS styling options
    print("\n6. Testing CSS Styling Options...")
    try:
        # Test CSS (default)
        result_css = await handle_call_tool("getCleanStarterConfig", {"styling": "css"})
        content_css = result_css[0].text if result_css else ""
        
        assert "box-sizing: border-box" in content_css
        assert "font-family: -apple-system" in content_css
        assert "@tailwind" not in content_css
        
        # Test none
        result_none = await handle_call_tool("getCleanStarterConfig", {"styling": "none"})
        content_none = result_none[0].text if result_none else ""
        
        assert "/* Add your custom styles here */" in content_none
        assert "box-sizing" not in content_none
        
        print("✓ CSS styling options work correctly")
    except Exception as e:
        print(f"✗ Failed CSS styling test: {e}")
    
    # Test 7: Verify package.json is always the same
    print("\n7. Testing Package.json Consistency...")
    try:
        result1 = await handle_call_tool("getCleanStarterConfig", {})
        result2 = await handle_call_tool("getCleanStarterConfig", {
            "includeAuth": True,
            "includeStorage": True,
            "includeData": True
        })
        
        content1 = result1[0].text if result1 else ""
        content2 = result2[0].text if result2 else ""
        
        # Extract package.json sections
        pkg_start = '### 📦 package.json\n```json\n'
        pkg_end = '\n```\n\n###'
        
        if pkg_start in content1 and pkg_start in content2:
            pkg1_start_idx = content1.find(pkg_start) + len(pkg_start)
            pkg1_end_idx = content1.find(pkg_end, pkg1_start_idx)
            pkg1 = content1[pkg1_start_idx:pkg1_end_idx]
            
            pkg2_start_idx = content2.find(pkg_start) + len(pkg_start)
            pkg2_end_idx = content2.find(pkg_end, pkg2_start_idx)
            pkg2 = content2[pkg2_start_idx:pkg2_end_idx]
            
            assert pkg1 == pkg2, "package.json should be the same regardless of options"
            print("✓ Package.json is consistent across configurations")
        else:
            print("✗ Could not find package.json sections to compare")
    except Exception as e:
        print(f"✗ Failed package.json consistency test: {e}")
    
    print("\n" + "=" * 60)
    print("Clean Starter Configuration Testing Complete!")
    
    # Summary
    print("\nThe getCleanStarterConfig tool provides:")
    print("- Clean starter without sample code")
    print("- Compatible package versions")
    print("- Modular feature inclusion")
    print("- Multiple styling options")
    print("- Complete setup instructions")

if __name__ == "__main__":
    asyncio.run(test_clean_starter_config())