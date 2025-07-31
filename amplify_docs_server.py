#!/usr/bin/env python3
"""
AWS Amplify Documentation MCP Server

This MCP server provides tools for scraping, indexing, and searching AWS Amplify Gen 2 documentation.
It offers easy access to documentation patterns and examples for Claude Code and other agents.
"""

import asyncio
import json
import logging
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urljoin, urlparse

import aiohttp
import mcp.server.stdio
import mcp.types as types
from bs4 import BeautifulSoup
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from pydantic import AnyUrl

# Import the documentation indexer
try:
    from doc_indexer import DocumentationIndexer
except ImportError:
    DocumentationIndexer = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("amplify-docs-server")

# Database setup
DB_PATH = "amplify_docs.db"

def init_database():
    """Initialize the SQLite database for storing scraped documentation."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            markdown_content TEXT,
            category TEXT,
            last_scraped TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            embedding_vector TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scrape_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            base_url TEXT NOT NULL,
            total_pages INTEGER,
            last_full_scrape TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'in_progress'
        )
    """)
    
    # Create indexes for better search performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_url ON documents(url)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_title ON documents(title)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON documents(category)")
    
    conn.commit()
    conn.close()

class AmplifyDocsScraper:
    """Handles scraping of AWS Amplify documentation."""
    
    def __init__(self):
        self.base_url = "https://docs.amplify.aws/nextjs/"
        self.session = None
        self.scraped_urls = set()
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Amplify-Docs-MCP-Server/1.0 (Educational Tool)'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch and parse a single documentation page."""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    html_content = await response.text()
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # Extract title
                    title = "Untitled"
                    title_elem = soup.find('h1') or soup.find('title')
                    if title_elem:
                        title = title_elem.get_text().strip()
                    
                    # Extract main content
                    content_selectors = [
                        'main', '[role="main"]', '.content', '#content',
                        'article', '.documentation-content'
                    ]
                    
                    content_elem = None
                    for selector in content_selectors:
                        content_elem = soup.select_one(selector)
                        if content_elem:
                            break
                    
                    if not content_elem:
                        content_elem = soup.find('body')
                    
                    if content_elem:
                        # Convert to markdown-like format
                        markdown_content = self.html_to_markdown(content_elem)
                        raw_content = content_elem.get_text(separator='\n', strip=True)
                        
                        # Determine category from URL
                        category = self.categorize_url(url)
                        
                        return {
                            'url': url,
                            'title': title,
                            'content': raw_content,
                            'markdown_content': markdown_content,
                            'category': category
                        }
                        
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def html_to_markdown(self, soup) -> str:
        """Convert HTML content to markdown format."""
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        markdown_lines = []
        
        for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'pre', 'code', 'ul', 'ol', 'li']):
            if element.name.startswith('h'):
                level = int(element.name[1])
                markdown_lines.append(f"{'#' * level} {element.get_text().strip()}")
                markdown_lines.append("")
            elif element.name == 'p':
                text = element.get_text().strip()
                if text:
                    markdown_lines.append(text)
                    markdown_lines.append("")
            elif element.name == 'pre':
                code_content = element.get_text()
                markdown_lines.append("```")
                markdown_lines.append(code_content)
                markdown_lines.append("```")
                markdown_lines.append("")
            elif element.name == 'code' and element.parent.name != 'pre':
                text = element.get_text().strip()
                if text:
                    markdown_lines.append(f"`{text}`")
            elif element.name in ['ul', 'ol']:
                # Handle lists
                for li in element.find_all('li', recursive=False):
                    markdown_lines.append(f"- {li.get_text().strip()}")
                markdown_lines.append("")
        
        return '\n'.join(markdown_lines)
    
    def categorize_url(self, url: str) -> str:
        """Categorize documentation based on URL path."""
        path = urlparse(url).path.lower()
        
        if '/start/' in path:
            return 'getting-started'
        elif '/deploy/' in path:
            return 'deployment'
        elif '/build-a-backend/' in path:
            return 'backend'
        elif '/build-ui/' in path:
            return 'frontend'
        elif '/gen1/' in path:
            return 'gen1'
        elif '/reference/' in path:
            return 'reference'
        elif '/guides/' in path:
            return 'guides'
        else:
            return 'general'
    
    async def discover_urls(self, start_url: str, max_depth: int = 3) -> List[str]:
        """Discover all documentation URLs starting from a base URL."""
        discovered_urls = set()
        to_visit = [(start_url, 0)]
        visited = set()
        
        while to_visit:
            current_url, depth = to_visit.pop(0)
            
            if current_url in visited or depth > max_depth:
                continue
                
            visited.add(current_url)
            
            try:
                async with self.session.get(current_url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Find all links that are documentation pages
                        for link in soup.find_all('a', href=True):
                            href = link['href']
                            full_url = urljoin(current_url, href)
                            
                            # Only include Amplify NextJS documentation URLs
                            if (full_url.startswith(self.base_url) and 
                                full_url not in visited and
                                not any(skip in full_url for skip in ['#', 'javascript:', 'mailto:'])):
                                discovered_urls.add(full_url)
                                if depth < max_depth:
                                    to_visit.append((full_url, depth + 1))
                                    
            except Exception as e:
                logger.error(f"Error discovering URLs from {current_url}: {e}")
        
        return list(discovered_urls)
    
    def save_markdown_file(self, doc_data: Dict[str, Any], output_dir: Path):
        """Save a document as a markdown file."""
        try:
            # Create a safe filename from the URL
            url_path = urlparse(doc_data['url']).path
            # Remove leading/trailing slashes and replace remaining with underscores
            filename = url_path.strip('/').replace('/', '_')
            if not filename:
                filename = 'index'
            filename = f"{filename}.md"
            
            # Create category subdirectory
            category_dir = output_dir / doc_data['category']
            category_dir.mkdir(parents=True, exist_ok=True)
            
            # Write the markdown file
            file_path = category_dir / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                # Write metadata header
                f.write(f"---\n")
                f.write(f"title: {doc_data['title']}\n")
                f.write(f"url: {doc_data['url']}\n")
                f.write(f"category: {doc_data['category']}\n")
                f.write(f"last_scraped: {doc_data.get('last_scraped', datetime.now().isoformat())}\n")
                f.write(f"---\n\n")
                
                # Write content
                f.write(f"# {doc_data['title']}\n\n")
                f.write(f"Source: [{doc_data['url']}]({doc_data['url']})\n\n")
                f.write(doc_data['markdown_content'])
            
            logger.info(f"Saved markdown file: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving markdown file for {doc_data['url']}: {e}")
            return False
    
    async def scrape_docs(self, force_refresh=False, save_markdown=False, markdown_dir="amplify_docs_markdown"):
        """Scrape all documentation pages."""
        db = AmplifyDocsDatabase()
        
        # Check if we need to scrape
        if not force_refresh:
            stats = db.get_stats()
            if stats.get('total_documents', 0) > 0:
                logger.info(f"Documentation already indexed ({stats['total_documents']} documents). Use force_refresh=True to re-scrape.")
                return
        
        # Set up markdown output directory if requested
        output_dir = None
        if save_markdown:
            output_dir = Path(markdown_dir)
            output_dir.mkdir(exist_ok=True)
            logger.info(f"Markdown files will be saved to: {output_dir}")
        
        scraped_count = 0
        errors = 0
        
        # Discover URLs
        discovered_urls = await self.discover_urls(self.base_url, max_depth=3)
        
        logger.info(f"Found {len(discovered_urls)} URLs to scrape")
        
        # Scrape each URL
        for i, url in enumerate(discovered_urls, 1):
            logger.info(f"Scraping {i}/{len(discovered_urls)}: {url}")
            doc_data = await self.fetch_page(url)
            if doc_data:
                if db.save_document(doc_data):
                    scraped_count += 1
                    # Save as markdown if requested
                    if save_markdown and output_dir:
                        self.save_markdown_file(doc_data, output_dir)
                else:
                    errors += 1
            else:
                errors += 1
            
            # Small delay to be respectful
            await asyncio.sleep(0.5)
        
        logger.info(f"Scraping completed! Processed {scraped_count} documents successfully, {errors} errors.")
        if save_markdown:
            logger.info(f"Markdown files saved to: {output_dir}")

class AmplifyDocsDatabase:
    """Handles database operations for the documentation."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
    
    def save_document(self, doc_data: Dict[str, Any]) -> bool:
        """Save a document to the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO documents 
                (url, title, content, markdown_content, category, last_scraped)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                doc_data['url'],
                doc_data['title'],
                doc_data['content'],
                doc_data['markdown_content'],
                doc_data['category'],
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error saving document: {e}")
            return False
    
    def search_documents(self, query: str, category: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Enhanced search with fuzzy matching and better relevance scoring."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Normalize query
            query_lower = query.lower()
            query_words = query_lower.split()
            
            # Common synonyms and variations
            synonyms = {
                "auth": ["authentication", "auth", "signin", "signup", "login", "cognito"],
                "api": ["api", "graphql", "rest", "endpoint", "query", "mutation"],
                "ui": ["ui", "component", "frontend", "interface", "view"],
                "storage": ["storage", "s3", "file", "upload", "download"],
                "db": ["database", "data", "model", "schema", "dynamodb"],
                "deploy": ["deploy", "deployment", "hosting", "publish"]
            }
            
            # Expand query with synonyms
            expanded_words = set(query_words)
            for word in query_words:
                for key, values in synonyms.items():
                    if word in values or key == word:
                        expanded_words.update(values)
            
            # Build SQL with scoring
            conditions = []
            params = []
            
            # Create scoring SQL
            score_cases = []
            
            # Exact match in title (highest score)
            score_cases.append(f"WHEN LOWER(title) LIKE '%{query_lower}%' THEN 100")
            
            # Exact match in URL
            score_cases.append(f"WHEN LOWER(url) LIKE '%{query_lower}%' THEN 80")
            
            # Word matches in title
            for word in query_words:
                score_cases.append(f"WHEN LOWER(title) LIKE '%{word}%' THEN 50")
            
            # Expanded word matches
            for word in expanded_words:
                conditions.append("(LOWER(title) LIKE ? OR LOWER(content) LIKE ? OR LOWER(url) LIKE ?)")
                params.extend([f"%{word}%", f"%{word}%", f"%{word}%"])
                score_cases.append(f"WHEN LOWER(title) LIKE '%{word}%' THEN 30")
                score_cases.append(f"WHEN LOWER(content) LIKE '%{word}%' THEN 10")
            
            # Build the query
            score_sql = "CASE " + " ".join(score_cases) + " ELSE 1 END"
            
            sql = f"""
                SELECT DISTINCT url, title, content, markdown_content, category, last_scraped,
                       ({score_sql}) as relevance_score
                FROM documents 
                WHERE {' OR '.join(conditions)}
            """
            
            if category:
                sql += " AND category = ?"
                params.append(category)
            
            # Check if we have summaries table for better results
            if self._table_exists('document_summaries'):
                sql = f"""
                    SELECT DISTINCT d.url, d.title, d.content, d.markdown_content, d.category, d.last_scraped,
                           ({score_sql}) + 
                           (CASE WHEN s.summary LIKE ? THEN 20 ELSE 0 END) as relevance_score
                    FROM documents d
                    LEFT JOIN document_summaries s ON d.url = s.url
                    WHERE {' OR '.join(conditions)}
                """
                params.append(f"%{query_lower}%")
                
                if category:
                    sql += " AND d.category = ?"
                    params.append(category)
            
            sql += " ORDER BY relevance_score DESC, last_scraped DESC LIMIT ?"
            params.append(limit * 2)  # Get more results for filtering
            
            cursor.execute(sql, params)
            
            # Process results and remove duplicates
            seen_urls = set()
            results = []
            
            for row in cursor.fetchall():
                url = row[0]
                if url not in seen_urls and len(results) < limit:
                    seen_urls.add(url)
                    results.append({
                        'url': url,
                        'title': row[1],
                        'content': row[2],
                        'markdown_content': row[3],
                        'category': row[4],
                        'last_scraped': row[5],
                        'relevance': row[6] if len(row) > 6 else 0
                    })
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []
    
    def _table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table_name,))
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except:
            return False
    
    def get_document_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get a specific document by URL."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT url, title, content, markdown_content, category, last_scraped
                FROM documents WHERE url = ?
            """, (url,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'url': row[0],
                    'title': row[1],
                    'content': row[2],
                    'markdown_content': row[3],
                    'category': row[4],
                    'last_scraped': row[5]
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting document: {e}")
            return None
    
    def list_categories(self) -> List[str]:
        """List all available categories."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT DISTINCT category FROM documents ORDER BY category")
            categories = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            return categories
            
        except Exception as e:
            logger.error(f"Error listing categories: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM documents")
            total_docs = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT category, COUNT(*) 
                FROM documents 
                GROUP BY category 
                ORDER BY COUNT(*) DESC
            """)
            category_counts = dict(cursor.fetchall())
            
            cursor.execute("""
                SELECT MAX(last_scraped) FROM documents
            """)
            last_update = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_documents': total_docs,
                'categories': category_counts,
                'last_update': last_update
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    
    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Get all documents from the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT url, title, content, markdown_content, category, last_scraped
                FROM documents
                ORDER BY category, title
            """)
            
            documents = []
            for row in cursor.fetchall():
                documents.append(dict(row))
            
            conn.close()
            return documents
            
        except Exception as e:
            logger.error(f"Error getting all documents: {e}")
            return []

def get_version_compatibility():
    """Get Amplify Gen 2 and Next.js version compatibility information."""
    return {
        "amplify_gen2": {
            "latest": "@aws-amplify/backend@latest",
            "compatible_nextjs": ["14.x", "15.x"],
            "supports": ["App Router", "Pages Router"],
            "typescript": "5.0+ (recommended)"
        },
        "nextjs": {
            "recommended": "14.x or 15.x",
            "minimum": "14.0.0",
            "notes": "Both App Router and Pages Router are supported"
        },
        "CRITICAL_COMMAND": "npx create-amplify@latest --template nextjs",
        "WARNING": "NEVER create Amplify + Next.js apps without the --template nextjs flag!"
    }

# Initialize database
init_database()

# Create server
server = Server("amplify-gen-2-nextjs-docs")

@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="getDocumentationOverview",
            description="Get a comprehensive overview of all documentation with summaries and quick navigation",
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "description": "Output format: 'full' for complete overview, 'summary' for brief overview",
                        "enum": ["full", "summary"],
                        "default": "summary"
                    }
                }
            }
        ),
        types.Tool(
            name="searchDocs",
            description="Search through the indexed Amplify documentation",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (searches titles and content)"
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by category (optional)",
                        "enum": ["getting-started", "backend", "frontend", "deployment", "reference", "guides", "general"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="getDocument",
            description="Retrieve a specific document by URL",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL of the document to retrieve"
                    }
                },
                "required": ["url"]
            }
        ),
        types.Tool(
            name="listCategories",
            description="List all available documentation categories",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="getStats",
            description="Get statistics about the indexed documentation",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="findPatterns",
            description="Find common Amplify Gen 2 patterns and examples",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern_type": {
                        "type": "string",
                        "description": "Type of pattern to find",
                        "enum": ["auth", "api", "storage", "deployment", "configuration", "database", "functions"]
                    }
                },
                "required": ["pattern_type"]
            }
        ),
        types.Tool(
            name="getCreateCommand",
            description="Get the CORRECT command for creating a new Amplify Gen 2 + Next.js application",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="getQuickStartPatterns",
            description="Get ready-to-use code patterns for common Amplify tasks",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "The task you want to accomplish",
                        "enum": [
                            "create-app",
                            "add-auth",
                            "add-api",
                            "add-storage", 
                            "file-upload",
                            "user-profile",
                            "real-time-data",
                            "deploy-app",
                            "custom-auth-ui",
                            "data-relationships"
                        ]
                    }
                },
                "required": ["task"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Handle tool execution."""
    
    if name == "getDocumentationOverview":
        format_type = arguments.get("format", "summary")
        
        # Check if we have a cached index
        index_file = Path("documentation_index.json")
        
        if not index_file.exists() and DocumentationIndexer:
            # Generate index if it doesn't exist
            indexer = DocumentationIndexer()
            index = indexer.generate_index()
            indexer.save_index()
        elif not index_file.exists():
            # Fallback if indexer not available
            db = AmplifyDocsDatabase()
            stats = db.get_stats()
            
            return [types.TextContent(
                type="text",
                text=f"""# Amplify Gen 2 Documentation Overview
                
Total Documents: {stats.get('total_documents', 0)}
Last Updated: {stats.get('last_update', 'Unknown')}

Categories:
{chr(10).join(f"- {cat}: {count} documents" for cat, count in stats.get('categories', {}).items())}

Use searchDocs to find specific topics or getDocument to retrieve full documentation."""
            )]
        
        # Load the index
        with open(index_file, 'r', encoding='utf-8') as f:
            index = json.load(f)
        
        if format_type == "full":
            # Return full detailed overview
            return [types.TextContent(
                type="text",
                text=index["overview"]
            )]
        else:
            # Return summary overview
            summary = f"""# Amplify Gen 2 Documentation Summary

## Quick Access Commands
- Create new app: `npx create-amplify@latest --template nextjs`
- Search docs: Use searchDocs tool with your query
- Get patterns: Use findPatterns tool with pattern type

## Main Categories
"""
            for cat_id, cat_data in index["categories"].items():
                summary += f"\n**{cat_data['title']}** ({cat_data['doc_count']} docs)\n"
                summary += f"{cat_data['summary'][:150]}...\n"
            
            summary += "\n## Common Patterns Available\n"
            patterns = ["auth", "api", "storage", "data", "deployment"]
            summary += "- " + "\n- ".join(patterns)
            
            summary += "\n\n💡 Use getDocumentationOverview with format='full' for detailed information."
            
            return [types.TextContent(type="text", text=summary)]
    
    elif name == "searchDocs":
        query = arguments["query"]
        category = arguments.get("category")
        limit = arguments.get("limit", 10)
        
        db = AmplifyDocsDatabase()
        results = db.search_documents(query, category, limit)
        
        if not results:
            return [types.TextContent(
                type="text",
                text=f"No documents found matching '{query}'"
            )]
        
        response_text = f"Found {len(results)} documents matching '{query}':\n\n"
        
        for doc in results:
            response_text += f"**{doc['title']}** ({doc['category']})\n"
            response_text += f"URL: {doc['url']}\n"
            # Include a snippet of content
            content_snippet = doc['content'][:200] + "..." if len(doc['content']) > 200 else doc['content']
            response_text += f"Content: {content_snippet}\n\n"
        
        return [types.TextContent(type="text", text=response_text)]
    
    elif name == "getDocument":
        url = arguments["url"]
        
        db = AmplifyDocsDatabase()
        doc = db.get_document_by_url(url)
        
        if not doc:
            return [types.TextContent(
                type="text",
                text=f"Document not found: {url}"
            )]
        
        return [types.TextContent(
            type="text",
            text=f"# {doc['title']}\n\n**URL:** {doc['url']}\n**Category:** {doc['category']}\n**Last Updated:** {doc['last_scraped']}\n\n## Content\n\n{doc['markdown_content']}"
        )]
    
    elif name == "listCategories":
        db = AmplifyDocsDatabase()
        categories = db.list_categories()
        
        return [types.TextContent(
            type="text",
            text=f"Available categories:\n" + "\n".join(f"- {cat}" for cat in categories)
        )]
    
    elif name == "getStats":
        db = AmplifyDocsDatabase()
        stats = db.get_stats()
        
        response_text = "**Documentation Statistics:**\n\n"
        response_text += f"Total Documents: {stats.get('total_documents', 0)}\n"
        response_text += f"Last Update: {stats.get('last_update', 'Never')}\n\n"
        
        if stats.get('categories'):
            response_text += "**Documents by Category:**\n"
            for category, count in stats['categories'].items():
                response_text += f"- {category}: {count}\n"
        
        return [types.TextContent(type="text", text=response_text)]
    
    elif name == "findPatterns":
        pattern_type = arguments["pattern_type"]
        
        # Define search queries for different patterns
        pattern_queries = {
            "auth": "authentication signIn signUp cognito user authenticator",
            "api": "graphql rest api endpoint mutation query data model",
            "storage": "s3 storage upload download file fileuploader storageimage",
            "deployment": "deploy hosting amplify build npx",
            "configuration": "configure amplify_outputs.json setup backend",
            "database": "dynamodb database table data model schema",
            "functions": "lambda function serverless backend handler"
        }
        
        query = pattern_queries.get(pattern_type, pattern_type)
        
        db = AmplifyDocsDatabase()
        results = db.search_documents(query, limit=5)
        
        if not results:
            return [types.TextContent(
                type="text",
                text=f"No patterns found for '{pattern_type}'"
            )]
        
        response_text = f"**{pattern_type.title()} Patterns in Amplify Gen 2:**\n\n"
        
        for doc in results:
            response_text += f"## {doc['title']}\n"
            response_text += f"**URL:** {doc['url']}\n"
            response_text += f"**Category:** {doc['category']}\n\n"
            
            # Extract code blocks from markdown content
            lines = doc['markdown_content'].split('\n')
            in_code_block = False
            code_lines = []
            
            for line in lines:
                if line.strip() == '```':
                    if in_code_block:
                        if code_lines:
                            response_text += "```\n" + "\n".join(code_lines) + "\n```\n\n"
                            code_lines = []
                        in_code_block = False
                    else:
                        in_code_block = True
                elif in_code_block:
                    code_lines.append(line)
            
            response_text += "---\n\n"
        
        return [types.TextContent(type="text", text=response_text)]
    
    elif name == "getCreateCommand":
        response_text = """
# CRITICAL: Creating Amplify Gen 2 + Next.js Application

## The ONLY correct command:

```bash
npx create-amplify@latest --template nextjs
```

## ⚠️ WARNING:
- NEVER use `npm create amplify@latest` without the template flag
- NEVER manually install Next.js after running create-amplify
- ALWAYS include `--template nextjs`

## Why this matters:
1. Without `--template nextjs`, you get an incomplete setup
2. Manual package installation causes version conflicts
3. Only the template ensures compatible versions

## For AI Assistants:
When asked to create an Amplify app with Next.js, ALWAYS respond with:
```bash
npx create-amplify@latest --template nextjs
```

This is documented as the ONLY reliable way to create a working Amplify Gen 2 + Next.js application.
"""
        return [types.TextContent(type="text", text=response_text)]
    
    elif name == "getQuickStartPatterns":
        task = arguments["task"]
        
        patterns = {
            "create-app": """# Create New Amplify Gen 2 + Next.js App

```bash
npx create-amplify@latest --template nextjs my-app
cd my-app
npm run dev
```

## Project Structure:
```
my-app/
├── amplify/              # Backend configuration
│   ├── auth/            # Authentication setup
│   ├── data/            # Data models
│   └── backend.ts       # Main backend config
├── app/                 # Next.js App Router
└── amplify_outputs.json # Generated config
```""",

            "add-auth": """# Add Authentication to Your App

## 1. Backend Setup (amplify/auth/resource.ts):
```typescript
import { defineAuth } from '@aws-amplify/backend';

export const auth = defineAuth({
  loginWith: {
    email: true,
  },
  signUpAttributes: ['email', 'name'],
});
```

## 2. Frontend - Use Authenticator Component:
```tsx
// app/page.tsx
'use client';
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';

export default function App() {
  return (
    <Authenticator>
      {({ signOut, user }) => (
        <main>
          <h1>Hello {user?.username}</h1>
          <button onClick={signOut}>Sign out</button>
        </main>
      )}
    </Authenticator>
  );
}
```

## 3. Deploy:
```bash
npx ampx deploy
```""",

            "add-api": """# Add GraphQL API with Data Models

## 1. Define Data Model (amplify/data/resource.ts):
```typescript
import { type ClientSchema, a, defineData } from '@aws-amplify/backend';

const schema = a.schema({
  Todo: a
    .model({
      content: a.string(),
      isDone: a.boolean().default(false),
    })
    .authorization(allow => [allow.owner()]),
});

export type Schema = ClientSchema<typeof schema>;
export const data = defineData({
  schema,
  authorizationModes: {
    defaultAuthorizationMode: 'userPool',
  },
});
```

## 2. Use in Frontend:
```tsx
'use client';
import { generateClient } from 'aws-amplify/data';
import type { Schema } from '@/amplify/data/resource';

const client = generateClient<Schema>();

// Create
await client.models.Todo.create({
  content: 'Build an app',
  isDone: false,
});

// Query
const { data: todos } = await client.models.Todo.list();

// Real-time subscription
client.models.Todo.observeQuery().subscribe({
  next: ({ items }) => console.log(items),
});
```""",

            "add-storage": """# Add File Storage

## 1. Backend Setup (amplify/storage/resource.ts):
```typescript
import { defineStorage } from '@aws-amplify/backend';

export const storage = defineStorage({
  name: 'myProjectFiles',
  access: (allow) => ({
    'profile-pictures/*': [
      allow.authenticated.to(['read', 'write', 'delete']),
      allow.guest.to(['read'])
    ],
    'public/*': [
      allow.authenticated.to(['read', 'write']),
      allow.guest.to(['read'])
    ],
  })
});
```

## 2. Add to Backend (amplify/backend.ts):
```typescript
import { storage } from './storage/resource';

export const backend = defineBackend({
  auth,
  data,
  storage,
});
```

## 3. Upload Files in Frontend:
```tsx
import { uploadData } from 'aws-amplify/storage';

const file = event.target.files[0];
try {
  const result = await uploadData({
    path: `public/${file.name}`,
    data: file,
    options: {
      onProgress: ({ transferredBytes, totalBytes }) => {
        const progress = (transferredBytes / totalBytes) * 100;
        console.log(`Upload progress: ${progress}%`);
      }
    }
  }).result;
  console.log('Succeeded: ', result);
} catch (error) {
  console.log('Error : ', error);
}
```""",

            "file-upload": """# File Upload with UI Component

## Use FileUploader Component:
```tsx
'use client';
import { FileUploader } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';

export default function FileUploadPage() {
  return (
    <FileUploader
      acceptedFileTypes={['image/*', 'video/*']}
      path="public/"
      maxFileCount={3}
      isResumable
      onUploadSuccess={({ key }) => {
        console.log('File uploaded:', key);
      }}
      onUploadError={(error, { key }) => {
        console.error('Upload error:', error);
      }}
    />
  );
}
```

## Display Uploaded Images:
```tsx
import { StorageImage } from '@aws-amplify/ui-react';

<StorageImage
  alt="Profile picture"
  path="public/profile-pic.jpg"
  fallbackSrc="/placeholder.png"
/>
```""",

            "user-profile": """# User Profile Management

## Use AccountSettings Component:
```tsx
'use client';
import { AccountSettings } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';

export default function ProfilePage() {
  return (
    <AccountSettings.ChangePassword />
    <AccountSettings.DeleteUser />
  );
}
```

## Custom Profile with User Attributes:
```tsx
import { fetchUserAttributes, updateUserAttribute } from 'aws-amplify/auth';

// Get user attributes
const attributes = await fetchUserAttributes();
console.log(attributes.email, attributes.name);

// Update attribute
await updateUserAttribute({
  userAttribute: {
    attributeKey: 'name',
    value: 'New Name'
  }
});
```""",

            "real-time-data": """# Real-Time Data Synchronization

## 1. Define Model with Subscriptions:
```typescript
const schema = a.schema({
  Message: a
    .model({
      content: a.string().required(),
      username: a.string().required(),
      createdAt: a.datetime(),
    })
    .authorization(allow => [allow.publicApiKey()]),
});
```

## 2. Real-Time Chat Component:
```tsx
'use client';
import { useEffect, useState } from 'react';
import { generateClient } from 'aws-amplify/data';

const client = generateClient<Schema>();

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');

  useEffect(() => {
    // Subscribe to new messages
    const subscription = client.models.Message.observeQuery({
      sort: { createdAt: 'DESC' }
    }).subscribe({
      next: ({ items }) => setMessages(items),
    });

    return () => subscription.unsubscribe();
  }, []);

  const sendMessage = async () => {
    await client.models.Message.create({
      content: input,
      username: 'User',
      createdAt: new Date().toISOString(),
    });
    setInput('');
  };

  return (
    <div>
      {messages.map(msg => (
        <div key={msg.id}>
          <strong>{msg.username}:</strong> {msg.content}
        </div>
      ))}
      <input value={input} onChange={(e) => setInput(e.target.value)} />
      <button onClick={sendMessage}>Send</button>
    </div>
  );
}
```""",

            "deploy-app": """# Deploy Your Amplify App

## 1. Deploy Backend to AWS:
```bash
npx ampx deploy
```

## 2. Deploy to Amplify Hosting:

### Option A: Git-based Deployment
```bash
# Push to GitHub
git add .
git commit -m "Initial commit"
git push origin main

# In AWS Console:
# 1. Go to AWS Amplify
# 2. Connect your GitHub repo
# 3. Choose branch and deploy
```

### Option B: Manual Deployment
```bash
# Build the app
npm run build

# Deploy using Amplify CLI
npx ampx hosting publish
```

## 3. Environment Variables:
Add to Amplify Console:
- `NEXT_PUBLIC_API_URL`
- `DATABASE_URL`
- Any other env vars

## 4. Custom Domain:
1. Go to Domain management in Amplify Console
2. Add your domain
3. Follow DNS configuration steps""",

            "custom-auth-ui": """# Custom Authentication UI

## Custom Sign In Form:
```tsx
'use client';
import { signIn } from 'aws-amplify/auth';
import { useState } from 'react';

export default function CustomSignIn() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const { isSignedIn } = await signIn({
        username: email,
        password,
      });
      if (isSignedIn) {
        window.location.href = '/dashboard';
      }
    } catch (error) {
      console.error('Sign in error:', error);
    }
  };

  return (
    <form onSubmit={handleSignIn}>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
        required
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
        required
      />
      <button type="submit">Sign In</button>
    </form>
  );
}
```

## Social Sign In:
```tsx
import { signInWithRedirect } from 'aws-amplify/auth';

<button onClick={() => signInWithRedirect({ provider: 'Google' })}>
  Sign in with Google
</button>
<button onClick={() => signInWithRedirect({ provider: 'Facebook' })}>
  Sign in with Facebook
</button>
```""",

            "data-relationships": """# Data Relationships

## 1. Define Related Models:
```typescript
const schema = a.schema({
  User: a
    .model({
      username: a.string().required(),
      posts: a.hasMany('Post', 'userId'),
    })
    .authorization(allow => [allow.owner()]),
    
  Post: a
    .model({
      title: a.string().required(),
      content: a.string(),
      userId: a.id().required(),
      user: a.belongsTo('User', 'userId'),
      comments: a.hasMany('Comment', 'postId'),
    })
    .authorization(allow => [allow.owner()]),
    
  Comment: a
    .model({
      content: a.string().required(),
      postId: a.id().required(),
      post: a.belongsTo('Post', 'postId'),
    })
    .authorization(allow => [allow.authenticated().to(['read'])]),
});
```

## 2. Query with Relationships:
```tsx
// Get user with posts
const { data: user } = await client.models.User.get(
  { id: userId },
  { selectionSet: ['id', 'username', 'posts.*'] }
);

// Get post with user and comments
const { data: post } = await client.models.Post.get(
  { id: postId },
  { 
    selectionSet: [
      'id', 
      'title', 
      'content',
      'user.username',
      'comments.*'
    ] 
  }
);

// Create related data
const post = await client.models.Post.create({
  title: 'My Post',
  content: 'Content',
  userId: currentUser.id,
});
```"""
        }
        
        pattern = patterns.get(task, "Pattern not found")
        
        return [types.TextContent(
            type="text",
            text=f"{pattern}\n\n💡 **Next Steps:**\nUse `searchDocs` for more details on any specific topic mentioned above."
        )]
    
    else:
        return [types.TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]

async def main():
    """Run the MCP server."""
    # Use stdin/stdout for communication
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="amplify-gen-2-nextjs-docs",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())