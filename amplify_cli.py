#!/usr/bin/env python3
"""
CLI wrapper for AWS Amplify Documentation MCP Server
Allows command-line interaction with the MCP server tools
"""

import asyncio
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from amplify_docs_server import AmplifyDocsScraper, AmplifyDocsDatabase, init_database

LAST_UPDATED_FILE = Path(__file__).parent / "last_updated.json"

def get_last_update_info():
    """Get last update information from file."""
    if not LAST_UPDATED_FILE.exists():
        return None
    
    try:
        with open(LAST_UPDATED_FILE, 'r') as f:
            return json.load(f)
    except:
        return None

def save_last_update_info(updated=True):
    """Save last update information to file."""
    info = {
        "last_updated": datetime.now().isoformat() if updated else None,
        "last_prompted": datetime.now().isoformat(),
        "user_declined": not updated
    }
    
    with open(LAST_UPDATED_FILE, 'w') as f:
        json.dump(info, f, indent=2)

async def check_and_prompt_for_update():
    """Check if documentation needs updating and prompt user."""
    info = get_last_update_info()
    
    # First time running - create the file
    if not info:
        save_last_update_info(updated=True)
        return False
    
    # Check if we should prompt
    now = datetime.now()
    
    # Parse dates
    last_updated = datetime.fromisoformat(info.get("last_updated", now.isoformat())) if info.get("last_updated") else now
    last_prompted = datetime.fromisoformat(info.get("last_prompted", "2000-01-01T00:00:00"))
    
    # Check if it's been more than a month since last update
    one_month_ago = now - timedelta(days=30)
    if last_updated > one_month_ago:
        return False
    
    # Check if user declined and it's been less than a day
    if info.get("user_declined", False):
        one_day_ago = now - timedelta(days=1)
        if last_prompted > one_day_ago:
            return False
    
    # Prompt user
    print("\n📚 Documentation Update Available")
    print(f"Your documentation was last updated {(now - last_updated).days} days ago.")
    response = input("Would you like to update the documentation now? (y/n): ").strip().lower()
    
    if response == 'y':
        print("\n🔄 Updating documentation...")
        await fetch_docs(force_refresh=True)
        save_last_update_info(updated=True)
        return True
    else:
        print("📌 Skipping update. Will ask again tomorrow.")
        save_last_update_info(updated=False)
        return False

async def fetch_docs(force_refresh=False, save_markdown=False):
    """Fetch all documentation"""
    init_database()
    async with AmplifyDocsScraper() as scraper:
        await scraper.scrape_docs(force_refresh=force_refresh, save_markdown=save_markdown)
    
    # Update the last_updated file
    save_last_update_info(updated=True)
    
    print("✓ Fetched all available documentation")
    if save_markdown:
        print("✓ Markdown files saved to: amplify_docs_markdown/")

async def search_docs(query, category=None, limit=10):
    """Search documentation"""
    db = AmplifyDocsDatabase()
    results = db.search_documents(query, category, limit)
    
    if not results:
        print("No results found")
        return
    
    for doc in results:
        print(f"\n📄 {doc['title']}")
        print(f"   URL: {doc['url']}")
        print(f"   Category: {doc['category']}")
        print(f"   Preview: {doc['content'][:200]}...")

async def list_categories():
    """List all categories"""
    db = AmplifyDocsDatabase()
    categories = db.list_categories()
    print("Categories:")
    for cat in categories:
        print(f"  - {cat}")

async def get_stats():
    """Get database statistics"""
    db = AmplifyDocsDatabase()
    stats = db.get_stats()
    
    if not stats:
        print("No statistics available")
        return
        
    print(f"Total documents: {stats.get('total_documents', 0)}")
    
    categories = stats.get('categories', {})
    if categories:
        print(f"Categories: {len(categories)}")
        for cat, count in categories.items():
            print(f"  - {cat}: {count} docs")
    
    if stats.get('last_update'):
        print(f"Last update: {stats['last_update']}")

async def get_document(url):
    """Get full document content by URL"""
    db = AmplifyDocsDatabase()
    doc = db.get_document_by_url(url)
    
    if not doc:
        print(f"Document not found: {url}")
        return
    
    print(f"\n{'='*80}")
    print(f"📄 {doc['title']}")
    print(f"URL: {doc['url']}")
    print(f"Category: {doc['category']}")
    print(f"Last Updated: {doc['last_scraped']}")
    print(f"{'='*80}\n")
    print(doc['markdown_content'])

async def find_patterns(pattern_type):
    """Find code patterns"""
    db = AmplifyDocsDatabase()
    # For now, just search for pattern keywords
    results = db.search_documents(pattern_type, limit=20)
    
    if not results:
        print(f"No {pattern_type} patterns found")
        return
    
    print(f"\n{pattern_type.upper()} Patterns Found:")
    for doc in results:
        print(f"\n📄 {doc['title']}")
        print(f"   URL: {doc['url']}")
        print(f"   Preview: {doc['content'][:300]}...")

async def export_markdown():
    """Export all documents to markdown files"""
    db = AmplifyDocsDatabase()
    scraper = AmplifyDocsScraper()
    output_dir = Path("amplify_docs_markdown")
    output_dir.mkdir(exist_ok=True)
    
    # Get all documents
    all_docs = db.get_all_documents()
    
    if not all_docs:
        print("No documents found to export")
        return
    
    print(f"Exporting {len(all_docs)} documents to markdown...")
    exported_count = 0
    
    for doc in all_docs:
        doc_data = {
            'url': doc['url'],
            'title': doc['title'],
            'category': doc['category'],
            'markdown_content': doc['markdown_content'],
            'last_scraped': doc['last_scraped']
        }
        if scraper.save_markdown_file(doc_data, output_dir):
            exported_count += 1
    
    print(f"✓ Exported {exported_count} documents to: {output_dir}/")
    print(f"📁 Documents organized by category:")
    for category_dir in sorted(output_dir.iterdir()):
        if category_dir.is_dir():
            file_count = len(list(category_dir.glob("*.md")))
            print(f"   - {category_dir.name}: {file_count} files")

async def check_versions():
    """Check Amplify and Next.js version compatibility"""
    import subprocess
    import re
    
    print("🔍 Checking Amplify Gen 2 and Next.js compatibility...\n")
    
    # Get latest Amplify backend version from npm
    try:
        result = subprocess.run(
            ["npm", "view", "@aws-amplify/backend", "version"],
            capture_output=True,
            text=True,
            check=True
        )
        amplify_version = result.stdout.strip()
        print(f"📦 Latest Amplify Backend version: {amplify_version}")
    except:
        print("❌ Could not fetch Amplify version from npm")
        amplify_version = "Unknown"
    
    # Check local project for Next.js version if package.json exists
    package_json_path = Path.cwd() / "package.json"
    local_nextjs_version = None
    
    if package_json_path.exists():
        try:
            with open(package_json_path, 'r') as f:
                package_data = json.load(f)
                deps = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}
                if 'next' in deps:
                    local_nextjs_version = deps['next']
                    print(f"📦 Local Next.js version: {local_nextjs_version}")
        except:
            pass
    
    # Get latest Next.js version
    try:
        result = subprocess.run(
            ["npm", "view", "next", "version"],
            capture_output=True,
            text=True,
            check=True
        )
        latest_nextjs = result.stdout.strip()
        print(f"📦 Latest Next.js version: {latest_nextjs}")
    except:
        print("❌ Could not fetch Next.js version from npm")
        latest_nextjs = "Unknown"
    
    print("\n✅ Compatibility Information:")
    print("Amplify Gen 2 is compatible with Next.js 14.x and 15.x")
    print("Both App Router and Pages Router are supported")
    
    # Parse major version from latest Next.js
    if latest_nextjs != "Unknown":
        major_version = latest_nextjs.split('.')[0]
        if int(major_version) >= 14:
            print(f"\n✅ Latest Next.js {latest_nextjs} is compatible with Amplify Gen 2")
        else:
            print(f"\n⚠️  Next.js {latest_nextjs} may have compatibility issues")
    
    if local_nextjs_version:
        # Clean version string (remove ^, ~, etc.)
        clean_version = re.sub(r'[^\d.]', '', local_nextjs_version)
        if clean_version:
            major = int(clean_version.split('.')[0])
            if major >= 14:
                print(f"✅ Your local Next.js {local_nextjs_version} is compatible")
            else:
                print(f"⚠️  Your local Next.js {local_nextjs_version} should be upgraded to 14.x or higher")
    
    print("\n📚 Recommended versions:")
    print("- Next.js: 14.x or 15.x")
    print("- @aws-amplify/backend: latest")
    print("- TypeScript: 5.0 or higher (optional but recommended)")
    
    print("\n🚀 Quick Start Commands:")
    print("For new projects with compatible versions:")
    print("  npx create-amplify@latest --template nextjs")
    print("\nFor existing Next.js projects:")
    print("  npx create-amplify@latest")
    print("  npm install aws-amplify@latest")

def main():
    parser = argparse.ArgumentParser(description='AWS Amplify Docs CLI')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Fetch command
    fetch_parser = subparsers.add_parser('fetch', help='Fetch all documentation')
    fetch_parser.add_argument('--force', action='store_true', help='Force refresh')
    fetch_parser.add_argument('--save-markdown', action='store_true', help='Save documents as markdown files')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search docs')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--category', help='Filter by category')
    search_parser.add_argument('--limit', type=int, default=10, help='Max results')
    
    # Categories command
    subparsers.add_parser('categories', help='List categories')
    
    # Stats command
    subparsers.add_parser('stats', help='Show statistics')
    
    # Get document command
    get_doc_parser = subparsers.add_parser('get-document', help='Get full document content')
    get_doc_parser.add_argument('url', help='Document URL')
    
    # Patterns command
    patterns_parser = subparsers.add_parser('patterns', help='Find patterns')
    patterns_parser.add_argument('type', choices=['auth', 'api', 'storage', 'deployment', 'configuration', 'database', 'functions'])
    
    # Export markdown command
    subparsers.add_parser('export-markdown', help='Export all documents to markdown files')
    
    # Check versions command
    subparsers.add_parser('check-versions', help='Check Amplify and Next.js version compatibility')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Check for updates before running commands (except for fetch itself)
    if args.command != 'fetch':
        asyncio.run(check_and_prompt_for_update())
    
    # Run the appropriate command
    if args.command == 'fetch':
        asyncio.run(fetch_docs(args.force, args.save_markdown))
    elif args.command == 'search':
        asyncio.run(search_docs(args.query, args.category, args.limit))
    elif args.command == 'categories':
        asyncio.run(list_categories())
    elif args.command == 'stats':
        asyncio.run(get_stats())
    elif args.command == 'get-document':
        asyncio.run(get_document(args.url))
    elif args.command == 'patterns':
        asyncio.run(find_patterns(args.type))
    elif args.command == 'export-markdown':
        asyncio.run(export_markdown())
    elif args.command == 'check-versions':
        asyncio.run(check_versions())

if __name__ == '__main__':
    main()