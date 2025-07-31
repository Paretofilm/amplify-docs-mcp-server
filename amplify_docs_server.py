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
from pydantic import AnyUrl

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
        """Search documents by content and title."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            sql = """
                SELECT url, title, content, markdown_content, category, last_scraped
                FROM documents 
                WHERE (title LIKE ? OR content LIKE ?)
            """
            params = [f"%{query}%", f"%{query}%"]
            
            if category:
                sql += " AND category = ?"
                params.append(category)
            
            sql += " ORDER BY last_scraped DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(sql, params)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'url': row[0],
                    'title': row[1],
                    'content': row[2],
                    'markdown_content': row[3],
                    'category': row[4],
                    'last_scraped': row[5]
                })
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []
    
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

# Initialize database
init_database()

# Create server
server = Server("amplify-docs-mcp-server")

@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="fetchLatestDocs",
            description="Scrape and index the latest AWS Amplify Gen 2 documentation from docs.amplify.aws/nextjs/",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_pages": {
                        "type": "integer",
                        "description": "Maximum number of pages to scrape (default: 100)",
                        "default": 100
                    },
                    "force_refresh": {
                        "type": "boolean",
                        "description": "Force re-scraping even if documents exist (default: false)",
                        "default": False
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
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Handle tool execution."""
    
    if name == "fetchLatestDocs":
        max_pages = arguments.get("max_pages", 100)
        force_refresh = arguments.get("force_refresh", False)
        
        db = AmplifyDocsDatabase()
        
        # Check if we need to scrape
        if not force_refresh:
            stats = db.get_stats()
            if stats.get('total_documents', 0) > 0:
                return [types.TextContent(
                    type="text",
                    text=f"Documentation already indexed ({stats['total_documents']} documents). Use force_refresh=true to re-scrape."
                )]
        
        scraped_count = 0
        errors = 0
        
        async with AmplifyDocsScraper() as scraper:
            # Discover URLs
            discovered_urls = await scraper.discover_urls(scraper.base_url, max_depth=2)
            discovered_urls = discovered_urls[:max_pages]  # Limit pages
            
            # Scrape each URL
            for url in discovered_urls:
                doc_data = await scraper.fetch_page(url)
                if doc_data:
                    if db.save_document(doc_data):
                        scraped_count += 1
                    else:
                        errors += 1
                else:
                    errors += 1
        
        return [types.TextContent(
            type="text",
            text=f"Scraping completed! Processed {scraped_count} documents successfully, {errors} errors."
        )]
    
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
            "auth": "authentication signIn signUp cognito user",
            "api": "graphql rest api endpoint mutation query",
            "storage": "s3 storage upload download file",
            "deployment": "deploy hosting amplify build",
            "configuration": "configure amplify_outputs.json setup",
            "database": "dynamodb database table data",
            "functions": "lambda function serverless backend"
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
            mcp.server.stdio.InitializationOptions(
                server_name="amplify-docs-mcp-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())