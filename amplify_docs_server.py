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

# Import project detection utilities
try:
    from project_detection import (
        should_provide_project_setup,
        detect_required_features,
        extract_project_name,
        extract_project_description,
        generate_project_setup_response
    )
except ImportError:
    logger.warning("project_detection module not found, some features may be limited")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("amplify-docs-server")

# Search enhancement functions
def detect_query_intent(query: str) -> str:
    """Detect the intent behind a search query to provide better results."""
    query_lower = query.lower()
    
    # Setup/initialization intent
    if any(term in query_lower for term in ['create', 'start', 'new', 'init', 'setup', 'begin', 'template', 'clone']):
        return 'setup'
    
    # Authorization/security intent
    if any(term in query_lower for term in ['auth', 'owner', 'allow', 'permission', 'access', 'security', 'authenticated', 'identityClaim']):
        return 'auth'
    
    # Data modeling intent
    if any(term in query_lower for term in ['model', 'schema', 'data', 'field', 'type', 'relationship', 'hasMany', 'belongsTo']):
        return 'data'
    
    # Error/troubleshooting intent
    if any(term in query_lower for term in ['error', 'issue', 'problem', 'fail', 'not working', 'undefined', 'mistake']):
        return 'error'
    
    # Timestamp/date handling
    if any(term in query_lower for term in ['timestamp', 'createdAt', 'updatedAt', 'date', 'time']):
        return 'timestamps'
    
    # Import/module intent
    if any(term in query_lower for term in ['import', 'require', 'module', '.js', 'extension', 'typescript']):
        return 'imports'
    
    return 'general'

def expand_query_terms(query: str, intent: str) -> List[str]:
    """Expand query terms based on intent to find more relevant results."""
    expanded = [query]
    query_lower = query.lower()
    
    # Intent-specific expansions
    expansions = {
        'setup': {
            'create': ['setup', 'initialize', 'new project', 'getting started', 'npx create-next-app'],
            'template': ['DO NOT clone', 'npx create-next-app', 'setup', 'initialization'],
            'clone': ['DO NOT clone template', 'use npx create-next-app instead', 'setup correctly']
        },
        'auth': {
            'owner': ['authorization', 'ownership', 'allow.owner()', 'NOT ownerField'],
            'authenticated': ['allow.authenticated()', 'authorization rules', 'auth patterns'],
            'identityClaim': ['INCORRECT syntax', 'use allow.owner() instead', 'authorization']
        },
        'data': {
            'model': ['defineData', 'schema', 'data modeling', 'relationships'],
            'timestamp': ['automatic timestamps', 'createdAt updatedAt automatic', 'DO NOT add manually']
        },
        'timestamps': {
            'createdAt': ['automatic fields', 'DO NOT add manually', 'handled by Amplify'],
            'updatedAt': ['automatic fields', 'DO NOT add manually', 'handled by Amplify']
        },
        'imports': {
            '.js': ['TypeScript imports', 'DO NOT use .js extension', 'import paths'],
            'import': ['module imports', 'TypeScript', 'correct import syntax']
        }
    }
    
    # Add expansions based on detected terms
    for term, expansion_list in expansions.get(intent, {}).items():
        if term in query_lower:
            expanded.extend(expansion_list)
    
    # Always add common mistake indicators
    if 'error' in intent or 'mistake' in query_lower:
        expanded.extend(['common mistakes', 'pitfalls', 'troubleshooting', 'correct way'])
    
    return list(set(expanded))  # Remove duplicates

def detect_anti_patterns(query: str) -> Dict[str, str]:
    """Detect common anti-patterns in queries and provide corrections."""
    anti_patterns = {
        # Template confusion
        r'clone.*template|git clone.*amplify': {
            'issue': 'Cloning GitHub template',
            'correction': 'Use npx create-next-app@14.2.10 instead of cloning',
            'severity': 'high'
        },
        # Authorization mistakes
        r'ownerField|owner_field|identityClaim': {
            'issue': 'Incorrect ownership syntax',
            'correction': 'Use allow.owner() not .ownerField().identityClaim()',
            'severity': 'high'
        },
        # Timestamp handling
        r'createdAt.*string|updatedAt.*string|manually.*timestamp': {
            'issue': 'Manual timestamp management',
            'correction': 'Amplify handles createdAt/updatedAt automatically',
            'severity': 'medium'
        },
        # Import confusion
        r'import.*\.js|require.*\.js': {
            'issue': 'JS extension in TypeScript imports',
            'correction': 'Do not use .js extensions in TypeScript imports',
            'severity': 'medium'
        },
        # Directory creation
        r'no such file|cannot find.*amplify|mkdir': {
            'issue': 'Missing directory',
            'correction': 'Create directories with mkdir -p amplify/auth amplify/data',
            'severity': 'high'
        }
    }
    
    detected = {}
    for pattern, info in anti_patterns.items():
        if re.search(pattern, query, re.IGNORECASE):
            detected[pattern] = info
    
    return detected

def get_contextual_warnings(context: Dict[str, Any]) -> List[Dict[str, str]]:
    """Get contextual warnings based on current activity."""
    warnings = []
    
    query = context.get('searchQuery', '').lower()
    current_file = context.get('currentFile', '')
    last_error = context.get('lastError', '')
    
    # Setup warnings
    if 'template' in query and 'clone' in query:
        warnings.append({
            'type': 'setup',
            'message': '⚠️ Do NOT clone the GitHub template. Use: npx create-next-app@14.2.10',
            'severity': 'high'
        })
    
    # Authorization warnings
    if any(term in query for term in ['ownerField', 'identityClaim']):
        warnings.append({
            'type': 'auth',
            'message': '⚠️ Incorrect syntax. Use: allow.owner() not .ownerField().identityClaim()',
            'severity': 'high'
        })
    
    # Timestamp warnings
    if 'resource.ts' in current_file and any(term in query for term in ['createdAt', 'updatedAt']):
        warnings.append({
            'type': 'data',
            'message': '💡 Amplify automatically adds createdAt/updatedAt. Do not define manually.',
            'severity': 'medium'
        })
    
    # Import warnings
    if '.ts' in current_file and '.js' in query:
        warnings.append({
            'type': 'imports',
            'message': '⚠️ Do not use .js extensions in TypeScript imports',
            'severity': 'medium'
        })
    
    # Directory warnings
    if 'ENOENT' in last_error or 'no such file' in last_error:
        warnings.append({
            'type': 'setup',
            'message': '💡 Create directories first: mkdir -p amplify/auth amplify/data',
            'severity': 'high'
        })
    
    return warnings

def calculate_relevance_boost(doc: Dict[str, Any], query: str, intent: str) -> float:
    """Calculate relevance boost based on intent and common mistakes."""
    boost = 1.0
    content = doc.get('content', '').lower()
    title = doc.get('title', '').lower()
    
    # Boost setup documentation for setup intent
    if intent == 'setup':
        if 'getting started' in title or 'setup' in title:
            boost *= 2.0
        if 'npx create-next-app' in content:
            boost *= 1.5
        if 'do not clone' in content:
            boost *= 1.8
    
    # Boost authorization documentation for auth intent
    if intent == 'auth':
        if 'authorization' in title or 'authentication' in title:
            boost *= 2.0
        if 'allow.owner()' in content:
            boost *= 1.5
        if 'common mistakes' in content and 'auth' in content:
            boost *= 1.8
    
    # Boost troubleshooting for error intent
    if intent == 'error':
        if 'troubleshooting' in title or 'common mistakes' in title:
            boost *= 2.5
        if 'pitfall' in content or 'mistake' in content:
            boost *= 1.5
    
    # Boost timestamp documentation
    if intent == 'timestamps':
        if 'automatic' in content and ('createdAt' in content or 'updatedAt' in content):
            boost *= 2.0
    
    # General boosts for best practices
    if 'best practice' in content or 'correct way' in content:
        boost *= 1.3
    
    return boost

# CRITICAL: Validation to prevent incorrect commands
def validate_response(response_text: str) -> str:
    """Validate that response doesn't contain forbidden commands."""
    FORBIDDEN_COMMANDS = [
        "npx create-amplify@latest --template nextjs",
        "create-amplify@latest --template",
        "create-amplify@latest"
    ]
    
    for forbidden in FORBIDDEN_COMMANDS:
        if forbidden in response_text:
            logger.error(f"CRITICAL: Forbidden command '{forbidden}' detected in response!")
            response_text = response_text.replace(
                forbidden, 
                "npx create-next-app@14.2.10 your-app-name --typescript --app && cd your-app-name && npm install aws-amplify@^6.6.0"
            )
    
    return response_text

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
            
            # Common synonyms and variations - updated for Amplify Gen 2
            synonyms = {
                "auth": ["authentication", "auth", "signin", "signup", "login", "cognito", "authenticator"],
                "api": ["api", "rest", "http", "endpoint", "apigateway", "custom"],
                "data": ["data", "defineData", "model", "schema", "real-time", "subscription", "generateClient", "observeQuery"],
                "graphql": ["graphql", "query", "mutation", "subscription"],
                "ui": ["ui", "component", "frontend", "interface", "view", "crud", "form", "authenticator", "fileuploader"],
                "storage": ["storage", "s3", "file", "upload", "download", "fileuploader", "uploadData", "downloadData"],
                "db": ["database", "dynamodb", "table", "defineData", "model", "schema"],
                "deploy": ["deploy", "deployment", "hosting", "publish", "amplify", "sandbox", "npx"],
                "definedata": ["defineData", "data", "model", "schema", "backend"],
                "realtime": ["real-time", "realtime", "subscription", "observeQuery", "live"],
                "typescript": ["typescript", "types", "type-safe", "generateClient"]
            }
            
            # Add common typos/variations
            typo_fixes = {
                "authentcation": "authentication",
                "authentiction": "authentication", 
                "authenitcation": "authentication",
                "storag": "storage",
                "graphq": "graphql",
                "deply": "deploy",
                "uplod": "upload",
                "dowload": "download"
            }
            
            # Fix typos in query words
            corrected_words = []
            for word in query_words:
                corrected_words.append(typo_fixes.get(word, word))
            
            # Use corrected words if any typos were fixed
            if corrected_words != query_words:
                query_words = corrected_words
            
            # Handle empty query
            if not query_words:
                # Return all documents for empty query
                sql = """
                    SELECT url, title, content, markdown_content, category, last_scraped, 1 as relevance_score
                    FROM documents
                """
                params = []
                
                if category:
                    sql += " WHERE category = ?"
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
                        'last_scraped': row[5],
                        'relevance': row[6]
                    })
                
                conn.close()
                return results
            
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
            if query_lower:
                score_cases.append(f"WHEN LOWER(d.title) LIKE '%{query_lower}%' THEN 100")
                score_cases.append(f"WHEN LOWER(d.url) LIKE '%{query_lower}%' THEN 80")
            
            # Special scoring for Amplify Data queries
            if any(term in query_lower for term in ['definedata', 'a.model', 'schema', 'real-time', 'generateclient']):
                score_cases.append(f"WHEN d.category = 'api-data' THEN 90")
                score_cases.append(f"WHEN LOWER(d.url) LIKE '%/data/%' THEN 85")
                score_cases.append(f"WHEN LOWER(d.title) LIKE '%data%' THEN 75")
            
            # Word matches in title
            for word in query_words:
                score_cases.append(f"WHEN LOWER(d.title) LIKE '%{word}%' THEN 50")
            
            # Expanded word matches
            for word in expanded_words:
                conditions.append("(LOWER(d.title) LIKE ? OR LOWER(d.content) LIKE ? OR LOWER(d.url) LIKE ?)")
                params.extend([f"%{word}%", f"%{word}%", f"%{word}%"])
                score_cases.append(f"WHEN LOWER(d.title) LIKE '%{word}%' THEN 30")
                score_cases.append(f"WHEN LOWER(d.content) LIKE '%{word}%' THEN 10")
            
            # Build the query
            score_sql = "CASE " + " ".join(score_cases) + " ELSE 1 END"
            
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
            else:
                # Simple query without join - need to use table alias
                sql = f"""
                    SELECT DISTINCT d.url, d.title, d.content, d.markdown_content, d.category, d.last_scraped,
                           ({score_sql}) as relevance_score
                    FROM documents d
                    WHERE {' OR '.join(conditions)}
                """
                
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
        "CRITICAL_COMMAND": "npx create-next-app@14.2.10 my-app --typescript --app --tailwind --eslint",
        "WARNING": "NEVER use npx create-amplify@latest --template nextjs - it does NOT exist!"
    }

# Initialize database
init_database()

# Search pattern tracking for learning feedback
search_history = []
MAX_SEARCH_HISTORY = 100

def track_search_pattern(query: str, intent: str, results_found: bool):
    """Track search patterns for learning feedback."""
    global search_history
    search_history.append({
        'query': query,
        'intent': intent, 
        'results_found': results_found,
        'timestamp': datetime.now()
    })
    
    # Keep only recent searches
    if len(search_history) > MAX_SEARCH_HISTORY:
        search_history = search_history[-MAX_SEARCH_HISTORY:]
    
    # Detect confusion patterns
    if len(search_history) >= 3:
        recent = search_history[-3:]
        # Check if user is struggling (multiple failed searches or changing topics rapidly)
        if all(not s['results_found'] for s in recent):
            logger.info("User appears to be struggling - no results in last 3 searches")
        elif len(set(s['intent'] for s in recent)) == 3:
            logger.info("User switching between different intents - may be confused")

# Create server
server = Server("amplify-gen-2-nextjs-docs")

@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="whatIsThis",
            description="Learn what this MCP server provides and why to use it for AWS Amplify Gen 2 questions",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="quickHelp",
            description="Get instant help for common AWS Amplify Gen 2 tasks like authentication, data models, and forms",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "What do you want to do with Amplify Gen 2?",
                        "enum": [
                            "setup-email-auth",
                            "create-data-model",
                            "data-field-types",
                            "add-file-upload",
                            "generate-crud-forms",
                            "add-social-login",
                            "real-time-subscriptions",
                            "deploy-to-aws",
                            "custom-auth-flow",
                            "advanced-real-time",
                            "error-handling-patterns",
                            "custom-auth-rules",
                            "optimistic-ui-updates",
                            "advanced-form-customization",
                            "recipe-sharing-app",
                            "ecommerce-platform",
                            "saas-starter",
                            "real-time-chat",
                            "social-media-app"
                        ]
                    }
                },
                "required": ["task"]
            }
        ),
        types.Tool(
            name="getDocumentationOverview",
            description="Get a comprehensive overview of all AWS Amplify Gen 2 documentation with summaries and quick navigation",
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
            description="Search through AWS Amplify Gen 2 documentation - the official source for defineData, defineAuth, and Next.js integration",
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
                        "enum": ["api-data", "authentication", "backend", "deployment", "frontend", "general", "getting-started", "reference", "storage", "troubleshooting"]
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
            description="Retrieve a specific AWS Amplify Gen 2 document by URL for complete documentation content",
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
            description="List all available AWS Amplify Gen 2 documentation categories including api-data, authentication, storage",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="getStats",
            description="Get statistics about the indexed AWS Amplify Gen 2 documentation database",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="findPatterns",
            description="Find common AWS Amplify Gen 2 patterns and examples for defineData, defineAuth, storage, and more",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern_type": {
                        "type": "string",
                        "description": "Type of pattern to find",
                        "enum": ["auth", "data", "api", "storage", "deployment", "configuration", "database", "functions", "ui", "ssr", "typescript", "workflow"]
                    }
                },
                "required": ["pattern_type"]
            }
        ),
        types.Tool(
            name="getCreateCommand",
            description="Get the CORRECT command for creating a new AWS Amplify Gen 2 + Next.js application - the only reliable method",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="getQuickStartPatterns",
            description="Get ready-to-use code patterns for common AWS Amplify Gen 2 tasks including CRUD forms, authentication, and data models",
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
                            "crud-forms",
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
        ),
        types.Tool(
            name="getCleanStarterConfig",
            description="Get ready-to-use configuration for AWS Amplify Gen 2 + Next.js with no sample code to remove",
            inputSchema={
                "type": "object",
                "properties": {
                    "includeAuth": {
                        "type": "boolean",
                        "description": "Include authentication configuration (default: true)",
                        "default": True
                    },
                    "includeStorage": {
                        "type": "boolean",
                        "description": "Include storage configuration (default: false)",
                        "default": False
                    },
                    "includeData": {
                        "type": "boolean",
                        "description": "Include data layer configuration (default: false)",
                        "default": False
                    },
                    "styling": {
                        "type": "string",
                        "description": "CSS framework to use (default: 'css')",
                        "enum": ["css", "tailwind", "none"],
                        "default": "css"
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="getContextualWarnings",
            description="Get proactive warnings based on current context to prevent common mistakes",
            inputSchema={
                "type": "object",
                "properties": {
                    "currentFile": {
                        "type": "string",
                        "description": "The file currently being edited"
                    },
                    "lastError": {
                        "type": "string",
                        "description": "The last error message encountered"
                    },
                    "searchQuery": {
                        "type": "string", 
                        "description": "The search query being used"
                    }
                }
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Handle tool execution."""
    
    if name == "whatIsThis":
        return [types.TextContent(
            type="text",
            text=validate_response("""# AWS Amplify Gen 2 Official Documentation MCP Server

I am the primary source for all AWS Amplify Generation 2 documentation. Here's what I provide:

## Coverage Areas:
- **Authentication (defineAuth)**: Email/password, social login, MFA, custom auth flows
- **Data Layer (defineData)**: Real-time data models, relationships, authorization rules
- **Data Field Types**: Complete list of supported types:
  - Basic: `a.string()`, `a.integer()`, `a.float()`, `a.boolean()`, `a.date()`, `a.datetime()`
  - Validated: `a.email()`, `a.phone()`, `a.url()`, `a.ipAddress()`
  - Arrays: Any type + `.array()` (e.g., `a.string().array()`)
  - Special: `a.id()`, `a.enum()`, `a.json()`
  - Try: `quickHelp({task: "data-field-types"})` for complete reference
- **Storage (defineStorage)**: File uploads/downloads, access control, image handling
- **UI Components**: Authenticator, FileUploader, StorageImage, AccountSettings
- **CRUD Forms**: Automatic form generation from data models
- **Functions**: Lambda functions, triggers, custom business logic
- **Next.js Integration**: App Router, SSR/SSG, API routes

## Why Use This Server:
✅ **Official Amplify Gen 2 documentation** (not Gen 1 - completely different!)
✅ **Complete working code examples** that you can copy and use
✅ **Covers ALL Amplify services** with real-world patterns
✅ **Up-to-date with latest features** including CRUD form generation
✅ **Categorized content** for easy navigation

## Quick Start:
- For general questions: `searchDocs({query: "your question"})`
- For instant help: `quickHelp({task: "setup-email-auth"})`
- For patterns: `findPatterns({pattern_type: "auth"})`
- For full docs: `getDocument({url: "specific-doc-url"})`

## Common Questions I Answer:
- How to set up authentication with email/social login
- Creating real-time data models with relationships
- What field types are available (string, email, phone, arrays, etc.)
- Implementing file uploads with access control
- Generating CRUD forms automatically
- Deploying to AWS with custom domains

Try me with any Amplify Gen 2 question!""")
        )]
    
    elif name == "quickHelp":
        task = arguments.get("task")
        
        guides = {
            "setup-email-auth": {
                "title": "Email Authentication Setup",
                "answer": "Email is the default auth method in Amplify Gen 2. Just use defineAuth with email: true",
                "code": """// amplify/auth/resource.ts
import { defineAuth } from '@aws-amplify/backend';

export const auth = defineAuth({
  loginWith: {
    email: true
  },
  // Optional: customize email messages
  userAttributes: {
    email: {
      required: true,
      mutable: true
    }
  }
});

// In your Next.js component
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
}""",
                "nextSteps": "1. Run 'npx ampx sandbox' to deploy\n2. The Authenticator component handles all UI\n3. Add signUpAttributes for additional fields"
            },
            "create-data-model": {
                "title": "Data Model Creation",
                "answer": "Define your data model using a.model() in a TypeScript schema",
                "code": """// amplify/data/resource.ts
import { a, defineData, type ClientSchema } from '@aws-amplify/backend';

const schema = a.schema({
  Todo: a.model({
    content: a.string().required(),
    isDone: a.boolean().default(false),
    priority: a.enum(['low', 'medium', 'high']),
    owner: a.string(), // automatically populated
    createdAt: a.datetime(),
    updatedAt: a.datetime()
  })
  .authorization(allow => [allow.owner()])
});

export type Schema = ClientSchema<typeof schema>;

export const data = defineData({
  schema,
  authorizationModes: {
    defaultAuthorizationMode: 'userPool'
  }
});

// In your frontend
import { generateClient } from 'aws-amplify/data';
import type { Schema } from '@/amplify/data/resource';

const client = generateClient<Schema>();

// Create
const { data: todo } = await client.models.Todo.create({
  content: 'Build an app',
  priority: 'high'
});

// Real-time subscription
const sub = client.models.Todo.observeQuery().subscribe({
  next: ({ items }) => console.log(items)
});""",
                "nextSteps": "1. Run 'npx ampx sandbox' to generate the API\n2. Use generateClient<Schema>() for type-safe operations\n3. Add relationships with a.belongsTo() and a.hasMany()"
            },
            "data-field-types": {
                "title": "Data Field Types Reference",
                "answer": "Complete guide to all supported field types in Amplify Gen 2 data models",
                "code": """// amplify/data/resource.ts
import { a, defineData, type ClientSchema } from '@aws-amplify/backend';

const schema = a.schema({
  ExampleModel: a.model({
    // Scalar types
    stringField: a.string().required(),
    integerField: a.integer(),
    floatField: a.float(),
    booleanField: a.boolean().default(false),
    
    // Date/Time types
    dateField: a.date(),           // YYYY-MM-DD
    timeField: a.time(),           // HH:MM:SS
    datetimeField: a.datetime(),   // Full date and time
    timestampField: a.timestamp(),  // Unix timestamp
    
    // Validated types
    emailField: a.email().required(),    // Built-in email validation
    phoneField: a.phone(),               // Built-in phone validation
    urlField: a.url(),                   // Built-in URL validation
    ipField: a.ipAddress(),              // Built-in IP validation
    
    // Complex types
    jsonField: a.json(),           // For nested objects
    enumField: a.enum(['option1', 'option2', 'option3']),
    
    // Array types
    stringArray: a.string().array(),     // Array of strings
    integerArray: a.integer().array(),   // Array of integers
    floatArray: a.float().array(),       // Array of floats
    
    // Relationships
    userId: a.id().required(),
    user: a.belongsTo('User', 'userId'),
    posts: a.hasMany('Post', 'authorId')
  })
});

// Usage examples:
// Store complex objects in JSON
const profile = {
  jsonField: {
    preferences: { theme: 'dark', language: 'en' },
    metadata: { lastLogin: new Date() }
  }
};

// Store arrays
const data = {
  stringArray: ['tag1', 'tag2', 'tag3'],
  integerArray: [1, 2, 3, 4, 5]
};""",
                "nextSteps": "1. Use a.email() and a.phone() for validated fields\n2. Use .array() for arrays instead of JSON workarounds\n3. Use a.json() for complex nested objects\n4. See https://docs.amplify.aws/nextjs/build-a-backend/data/data-modeling/add-fields/"
            },
            "add-file-upload": {
                "title": "File Upload Implementation",
                "answer": "Use FileUploader component for the UI and defineStorage for backend",
                "code": """// amplify/storage/resource.ts
import { defineStorage } from '@aws-amplify/backend';

export const storage = defineStorage({
  name: 'myAppStorage',
  access: (allow) => ({
    'profile-pictures/*': [
      allow.authenticated.to(['read', 'write', 'delete'])
    ],
    'public/*': [
      allow.guest.to(['read']),
      allow.authenticated.to(['read', 'write', 'delete'])
    ]
  })
});

// In your component
'use client';
import { FileUploader } from '@aws-amplify/ui-react';
import { uploadData } from 'aws-amplify/storage';

export default function ProfileUpload() {
  return (
    <FileUploader
      acceptedFileTypes={['image/*']}
      path="profile-pictures/"
      maxFileCount={1}
      onFileRemove={({ key }) => {
        // Handle file removal
      }}
      onUploadSuccess={({ key }) => {
        console.log('Uploaded:', key);
      }}
    />
  );
}

// Manual upload
async function uploadFile(file: File) {
  const result = await uploadData({
    path: `profile-pictures/${file.name}`,
    data: file,
    options: {
      contentType: file.type
    }
  }).result;
  
  return result.path;
}""",
                "nextSteps": "1. Configure storage paths in defineStorage\n2. Use FileUploader for UI or uploadData for programmatic uploads\n3. Display with StorageImage component"
            },
            "generate-crud-forms": {
                "title": "CRUD Form Generation", 
                "answer": "Generate forms automatically from your data models",
                "code": """// First, ensure you have a data model
// amplify/data/resource.ts
const schema = a.schema({
  Product: a.model({
    name: a.string().required(),
    description: a.string(),
    price: a.float(),
    category: a.enum(['electronics', 'clothing', 'food']),
    inStock: a.boolean().default(true)
  })
});

// Generate forms (run in your project root)
npx ampx generate forms

// This creates form components in ui-components/
// Then use in your app:
'use client';
import { 
  ProductCreateForm, 
  ProductUpdateForm 
} from '@/ui-components';

// Create form
export function AddProduct() {
  return (
    <ProductCreateForm
      onSuccess={(product) => {
        console.log('Created:', product);
        // Navigate or show success
      }}
      onError={(error) => {
        console.error('Error:', error);
      }}
    />
  );
}

// Update form
export function EditProduct({ product }) {
  return (
    <ProductUpdateForm
      product={product}
      onSuccess={(updated) => {
        console.log('Updated:', updated);
      }}
      // Customize fields
      overrides={{
        name: { label: 'Product Name' },
        price: { 
          label: 'Price (USD)',
          placeholder: '0.00'
        }
      }}
    />
  );
}""",
                "nextSteps": "1. Run 'npx ampx generate forms' after defining models\n2. Import forms from '@/ui-components'\n3. Customize with overrides prop\n4. Re-generate when model changes"
            },
            "add-social-login": {
                "title": "Social Login Setup",
                "answer": "Add Google, Facebook, or other social providers to defineAuth",
                "code": """// amplify/auth/resource.ts
import { defineAuth } from '@aws-amplify/backend';

export const auth = defineAuth({
  loginWith: {
    email: true,
    externalProviders: {
      google: {
        clientId: secret('GOOGLE_CLIENT_ID'),
        clientSecret: secret('GOOGLE_CLIENT_SECRET'),
        scopes: ['email', 'profile']
      },
      facebook: {
        clientId: secret('FACEBOOK_CLIENT_ID'),
        clientSecret: secret('FACEBOOK_CLIENT_SECRET'),
        scopes: ['email', 'public_profile']
      },
      // Callback URLs are auto-configured
      callbackUrls: [
        'http://localhost:3000/',
        'https://yourdomain.com/'
      ],
      logoutUrls: [
        'http://localhost:3000/',
        'https://yourdomain.com/'
      ]
    }
  }
});

// Set secrets
npx ampx secret set GOOGLE_CLIENT_ID
npx ampx secret set GOOGLE_CLIENT_SECRET

// In your component
import { signInWithRedirect } from 'aws-amplify/auth';

<button onClick={() => signInWithRedirect({ provider: 'Google' })}>
  Sign in with Google
</button>

<button onClick={() => signInWithRedirect({ provider: 'Facebook' })}>
  Sign in with Facebook
</button>""",
                "nextSteps": "1. Register OAuth apps with providers\n2. Set secrets with 'npx ampx secret set'\n3. Add callback URLs to OAuth app settings\n4. The Authenticator component supports social login automatically"
            },
            "real-time-subscriptions": {
                "title": "Real-time Data Subscriptions",
                "answer": "Use observeQuery() for real-time data synchronization",
                "code": """// Define a model with auth rules
const schema = a.schema({
  Message: a.model({
    content: a.string().required(),
    username: a.string().required(),
    roomId: a.string().required(),
    createdAt: a.datetime()
  })
  .authorization(allow => [
    allow.authenticated().to(['read']),
    allow.owner().to(['create', 'delete'])
  ])
});

// In your component
'use client';
import { generateClient } from 'aws-amplify/data';
import { useEffect, useState } from 'react';
import type { Schema } from '@/amplify/data/resource';

const client = generateClient<Schema>();

export function ChatRoom({ roomId }: { roomId: string }) {
  const [messages, setMessages] = useState<Schema['Message']['type'][]>([]);

  useEffect(() => {
    // Subscribe to all messages in this room
    const sub = client.models.Message.observeQuery({
      filter: { roomId: { eq: roomId } }
    }).subscribe({
      next: ({ items, isSynced }) => {
        setMessages(items);
        if (isSynced) {
          console.log('Fully synced with cloud');
        }
      },
      error: (err) => console.error(err)
    });

    return () => sub.unsubscribe();
  }, [roomId]);

  // Send message
  async function sendMessage(content: string) {
    await client.models.Message.create({
      content,
      username: user.username,
      roomId,
      createdAt: new Date().toISOString()
    });
  }

  return (
    <div>
      {messages.map(msg => (
        <div key={msg.id}>
          <strong>{msg.username}:</strong> {msg.content}
        </div>
      ))}
    </div>
  );
}""",
                "nextSteps": "1. observeQuery() syncs data in real-time\n2. Filter subscriptions with query parameters\n3. Handle isSynced for loading states\n4. Unsubscribe in cleanup to prevent memory leaks"
            },
            "deploy-to-aws": {
                "title": "Deploy to AWS",
                "answer": "Deploy your app using Amplify Hosting with Git integration",
                "code": """# 1. First, deploy your backend
npx ampx pipeline-deploy --branch main --app-id YOUR_APP_ID

# 2. For full-stack deployment with hosting:

## Option A: Deploy via Git (Recommended)
# - Push your code to GitHub/GitLab/Bitbucket
# - Go to AWS Amplify Console
# - Click "New app" > "Host web app"
# - Connect your repository
# - Amplify auto-detects Next.js settings

## Option B: Manual deployment
# Build your app
npm run build

# Deploy to Amplify Hosting
npx ampx deploy

# 3. Environment variables
# Set in Amplify Console > App settings > Environment variables
# Or in amplify/backend.ts:
import { defineBackend } from '@aws-amplify/backend';
import { auth } from './auth/resource';
import { data } from './data/resource';

const backend = defineBackend({
  auth,
  data,
});

// Access secrets
const myApiKey = secret('MY_API_KEY');

# 4. Custom domain
# - Go to Amplify Console > Domain management
# - Add your domain
# - Follow DNS configuration steps

# 5. Preview deployments
# Every PR gets a preview URL automatically""",
                "nextSteps": "1. Connect Git repository for automatic deployments\n2. Set environment variables in Amplify Console\n3. Configure custom domain\n4. Enable preview deployments for PRs"
            },
            "custom-auth-flow": {
                "title": "Custom Authentication Flow",
                "answer": "Implement custom auth challenges with Lambda triggers",
                "code": """// amplify/auth/resource.ts
import { defineAuth } from '@aws-amplify/backend';
import { defineFunction } from '@aws-amplify/backend';

// Define custom auth trigger
const customAuthChallenge = defineFunction({
  name: 'custom-auth-challenge',
  entry: './custom-auth-challenge.ts'
});

export const auth = defineAuth({
  loginWith: {
    email: true,
    // Enable custom auth flow
    customAuth: {
      triggers: {
        createAuthChallenge,
        defineAuthChallenge,
        verifyAuthChallenge
      }
    }
  }
});

// custom-auth-challenge.ts
import { Handler } from 'aws-lambda';

export const handler: Handler = async (event) => {
  if (event.request.challengeName === 'CUSTOM_CHALLENGE') {
    // Generate challenge (e.g., send SMS code)
    const code = Math.random().toString().substr(2, 6);
    
    // Store code (use Parameter Store or DynamoDB)
    await storeCode(event.request.userAttributes.phone_number, code);
    
    // Send SMS
    await sendSMS(event.request.userAttributes.phone_number, code);
    
    event.response.publicChallengeParameters = {};
    event.response.privateChallengeParameters = { code };
    event.response.challengeMetadata = 'SMS_CODE';
  }
  
  return event;
};

// Frontend usage
import { signIn } from 'aws-amplify/auth';

// Start custom auth flow
const { nextStep } = await signIn({
  username: 'user@example.com',
  options: {
    authFlowType: 'CUSTOM_WITH_SRP'
  }
});

if (nextStep.signInStep === 'CONFIRM_CUSTOM_CHALLENGE') {
  // Get code from user
  const code = prompt('Enter SMS code');
  
  // Confirm challenge
  await confirmSignIn({
    challengeResponse: code
  });
}""",
                "nextSteps": "1. Implement Lambda triggers for custom logic\n2. Use DynamoDB or Parameter Store for state\n3. Handle multiple challenge rounds if needed\n4. Test with different auth scenarios"
            },
            "advanced-real-time": {
                "title": "Advanced Real-time Patterns with observeQuery",
                "answer": "Comprehensive real-time subscription patterns with filtering, error handling, and connection management",
                "code": """// Advanced observeQuery with filtering and pagination
import { generateClient } from 'aws-amplify/data';
import { ConnectionState } from '@aws-amplify/datastore';

const client = generateClient<Schema>();

// 1. Filtered real-time with complex conditions
export function useFilteredTodos(userId: string, priority: 'high' | 'medium') {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>();

  useEffect(() => {
    let subscription: any;

    const setupSubscription = async () => {
      try {
        // Complex filter with multiple conditions
        subscription = client.models.Todo.observeQuery({
          filter: {
            and: [
              { owner: { eq: userId } },
              { priority: { eq: priority } },
              { deletedAt: { attributeExists: false } }
            ]
          },
          limit: 100,
          sortDirection: 'DESC'
        }).subscribe({
          next: ({ items, isSynced }) => {
            setTodos(items);
            setLoading(!isSynced);
            setError(null);
          },
          error: (err) => {
            console.error('Subscription error:', err);
            setError(err);
            setLoading(false);
            
            // Retry logic
            setTimeout(() => {
              setupSubscription();
            }, 5000);
          }
        });

        // Monitor connection state
        Hub.listen('datastore', (data) => {
          const { event, data: eventData } = data.payload;
          if (event === 'networkStatus') {
            setConnectionState(eventData.active ? 'CONNECTED' : 'DISCONNECTED');
          }
        });
      } catch (err) {
        setError(err as Error);
        setLoading(false);
      }
    };

    setupSubscription();

    return () => {
      subscription?.unsubscribe();
      Hub.remove('datastore');
    };
  }, [userId, priority]);

  return { todos, loading, error, connectionState };
}

// 2. Optimistic updates with real-time sync
export function useOptimisticTodos() {
  const [todos, setTodos] = useState<Todo[]>([]);
  const [pendingUpdates, setPendingUpdates] = useState<Set<string>>(new Set());

  // Subscribe to real-time updates
  useEffect(() => {
    const sub = client.models.Todo.observeQuery().subscribe({
      next: ({ items }) => {
        setTodos(items);
        // Clear pending updates when server confirms
        setPendingUpdates(new Set());
      }
    });

    return () => sub.unsubscribe();
  }, []);

  const updateTodo = async (id: string, updates: Partial<Todo>) => {
    // Optimistic update
    setTodos(prev => 
      prev.map(todo => 
        todo.id === id ? { ...todo, ...updates } : todo
      )
    );
    setPendingUpdates(prev => new Set(prev).add(id));

    try {
      await client.models.Todo.update({
        id,
        ...updates
      });
    } catch (error) {
      // Revert on error
      const { data: current } = await client.models.Todo.get({ id });
      setTodos(prev => 
        prev.map(todo => 
          todo.id === id ? current : todo
        )
      );
      setPendingUpdates(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      throw error;
    }
  };

  return { todos, updateTodo, pendingUpdates };
}

// 3. Pagination with real-time updates
export function usePaginatedRealTime(pageSize = 20) {
  const [items, setItems] = useState<Todo[]>([]);
  const [nextToken, setNextToken] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);

  // Initial load and subscription
  useEffect(() => {
    const subscription = client.models.Todo.observeQuery({
      limit: pageSize
    }).subscribe({
      next: ({ items: newItems, nextToken: token }) => {
        setItems(newItems);
        setNextToken(token);
        setHasMore(!!token);
      }
    });

    return () => subscription.unsubscribe();
  }, [pageSize]);

  const loadMore = async () => {
    if (!nextToken) return;

    const { data: moreItems, nextToken: newToken } = 
      await client.models.Todo.list({
        limit: pageSize,
        nextToken
      });

    setItems(prev => [...prev, ...moreItems]);
    setNextToken(newToken);
    setHasMore(!!newToken);
  };

  return { items, loadMore, hasMore };
}""",
                "nextSteps": "1. Implement connection state monitoring with Hub\n2. Add retry logic for failed subscriptions\n3. Handle offline scenarios with DataStore\n4. Optimize with selective sync for large datasets"
            },
            "error-handling-patterns": {
                "title": "Comprehensive Error Handling Patterns",
                "answer": "Robust error handling for all Amplify operations with retry logic and user feedback",
                "code": """// Error handling utilities and patterns
import { GraphQLError } from 'graphql';

// 1. Error types and utilities
export class AmplifyError extends Error {
  constructor(
    message: string,
    public code: string,
    public details?: any
  ) {
    super(message);
    this.name = 'AmplifyError';
  }
}

export const errorHandler = {
  isNetworkError: (error: any): boolean => {
    return error.message?.includes('Network') || 
           error.code === 'NetworkError';
  },
  
  isAuthError: (error: any): boolean => {
    return error.code === 'UserUnAuthenticatedException' ||
           error.message?.includes('Unauthorized');
  },
  
  isValidationError: (error: any): boolean => {
    return error.errors?.some((e: GraphQLError) => 
      e.extensions?.code === 'ValidationError'
    );
  },
  
  getUserMessage: (error: any): string => {
    if (errorHandler.isNetworkError(error)) {
      return 'Connection error. Please check your internet connection.';
    }
    if (errorHandler.isAuthError(error)) {
      return 'Please sign in to continue.';
    }
    if (errorHandler.isValidationError(error)) {
      return 'Please check your input and try again.';
    }
    return 'An unexpected error occurred. Please try again.';
  }
};

// 2. Retry wrapper with exponential backoff
export async function withRetry<T>(
  operation: () => Promise<T>,
  options = {
    maxAttempts: 3,
    initialDelay: 1000,
    maxDelay: 10000,
    shouldRetry: (error: any) => errorHandler.isNetworkError(error)
  }
): Promise<T> {
  let lastError: any;
  
  for (let attempt = 0; attempt < options.maxAttempts; attempt++) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;
      
      if (attempt === options.maxAttempts - 1 || 
          !options.shouldRetry(error)) {
        throw error;
      }
      
      const delay = Math.min(
        options.initialDelay * Math.pow(2, attempt),
        options.maxDelay
      );
      
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  
  throw lastError;
}

// 3. Error boundary component
export class ErrorBoundary extends React.Component<
  { children: React.ReactNode; fallback?: React.ComponentType<{ error: Error }> },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error('Error caught by boundary:', error, errorInfo);
    // Send to monitoring service
  }

  render() {
    if (this.state.hasError && this.state.error) {
      const Fallback = this.props.fallback || DefaultErrorFallback;
      return <Fallback error={this.state.error} />;
    }

    return this.props.children;
  }
}

// 4. Hook with built-in error handling
export function useAsyncOperation<T>() {
  const [state, setState] = useState<{
    loading: boolean;
    error: Error | null;
    data: T | null;
  }>({
    loading: false,
    error: null,
    data: null
  });

  const execute = useCallback(async (operation: () => Promise<T>) => {
    setState({ loading: true, error: null, data: null });
    
    try {
      const data = await withRetry(operation);
      setState({ loading: false, error: null, data });
      return data;
    } catch (error) {
      const amplifyError = error instanceof AmplifyError 
        ? error 
        : new AmplifyError(
            errorHandler.getUserMessage(error),
            error.code || 'UNKNOWN',
            error
          );
      
      setState({ loading: false, error: amplifyError, data: null });
      throw amplifyError;
    }
  }, []);

  return { ...state, execute };
}

// 5. Usage example with all patterns
export function TodoManager() {
  const { execute, loading, error, data } = useAsyncOperation<Todo[]>();
  
  const loadTodos = async () => {
    await execute(async () => {
      const { data } = await client.models.Todo.list();
      return data;
    });
  };

  const createTodo = async (content: string) => {
    try {
      await withRetry(
        async () => {
          const { data } = await client.models.Todo.create({
            content,
            isDone: false
          });
          return data;
        },
        { shouldRetry: (err) => !errorHandler.isValidationError(err) }
      );
      
      // Refresh list on success
      await loadTodos();
    } catch (error) {
      // Error is already handled by the hook
      console.error('Failed to create todo:', error);
    }
  };

  if (error) {
    return (
      <div className="error-container">
        <p>{error.message}</p>
        <button onClick={loadTodos}>Retry</button>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      {/* Your component content */}
    </ErrorBoundary>
  );
}""",
                "nextSteps": "1. Integrate with error monitoring service (Sentry, etc.)\n2. Add toast notifications for user feedback\n3. Implement offline queue for failed mutations\n4. Create custom error pages for different error types"
            },
            "custom-auth-rules": {
                "title": "Advanced Custom Authorization Rules",
                "answer": "Complex authorization patterns including multi-tenant, role-based, and dynamic permissions",
                "code": """// Advanced authorization patterns
import { a, defineData, type ClientSchema } from '@aws-amplify/backend';

// 1. Group-based access control
const schema = a.schema({
  // Admin-only model
  AdminSettings: a.model({
    key: a.string().required(),
    value: a.string(),
    updatedBy: a.string()
  }).authorization(allow => [
    allow.groups(['Admins']).to(['create', 'read', 'update', 'delete'])
  ]),
  
  // Multi-group access with owner
  Document: a.model({
    title: a.string().required(),
    content: a.string(),
    status: a.enum(['draft', 'review', 'published']),
    tags: a.string().array(),
    owner: a.string()
  }).authorization(allow => [
    allow.owner(),                                    // Owners have full access
    allow.groups(['Editors']).to(['read', 'update']), // Editors can read and update
    allow.groups(['Viewers']).to(['read'])            // Viewers can only read
  ]),
  
  Project: a.model({
    name: a.string().required(),
    organizationId: a.id().required(),
    status: a.enum(['draft', 'active', 'archived']),
    visibility: a.enum(['private', 'team', 'public']),
    createdBy: a.string(),
    assignedTo: a.string().array()
  }).authorization(allow => [
    // Public projects readable by all
    allow.publicApiKey().to(['read']).when(
      (project) => project.visibility.eq('public')
    ),
    // Team members based on organization
    allow.custom({
      provider: 'function',
      operations: ['read', 'update']
    }),
    // Assigned users can update
    allow.custom({
      provider: 'function', 
      operations: ['update']
    })
  ])
});

// 2. Custom authorization function
export const authFunction = defineFunction({
  name: 'custom-auth-function',
  entry: './auth-handler.ts',
  environment: {
    ORGANIZATION_TABLE: organizationTable.name
  }
});

// auth-handler.ts
import { AppSyncAuthorizerHandler } from 'aws-lambda';
import { DynamoDB } from 'aws-sdk';

const dynamodb = new DynamoDB.DocumentClient();

export const handler: AppSyncAuthorizerHandler = async (event) => {
  const { authorizationToken, requestContext } = event;
  const { operationType, resourcePath } = requestContext;
  
  // Decode user info from token
  const userInfo = decodeToken(authorizationToken);
  const { userId, email } = userInfo;
  
  // Check organization membership
  if (resourcePath.modelName === 'Project') {
    const projectId = resourcePath.id;
    const hasAccess = await checkProjectAccess(
      userId, 
      projectId, 
      operationType
    );
    
    return {
      isAuthorized: hasAccess,
      resolverContext: {
        userId,
        organizationId: userInfo.organizationId
      }
    };
  }
  
  // Check organization-level permissions
  if (resourcePath.modelName === 'OrganizationMember') {
    const orgId = event.arguments?.organizationId;
    const memberRole = await getMemberRole(userId, orgId);
    
    const canPerformOperation = 
      memberRole === 'owner' || 
      (memberRole === 'admin' && operationType !== 'DELETE');
    
    return {
      isAuthorized: canPerformOperation,
      resolverContext: { userId, memberRole }
    };
  }
  
  return { isAuthorized: false };
};

async function checkProjectAccess(
  userId: string, 
  projectId: string, 
  operation: string
): Promise<boolean> {
  // Get project details
  const project = await getProject(projectId);
  
  // Public projects are readable
  if (operation === 'READ' && project.visibility === 'public') {
    return true;
  }
  
  // Check organization membership
  const membership = await getMembership(userId, project.organizationId);
  if (!membership) return false;
  
  // Check role-based permissions
  const permissions = getRolePermissions(membership.role);
  const requiredPermission = `${operation.toLowerCase()}:project`;
  
  return permissions.includes(requiredPermission) ||
         project.assignedTo?.includes(userId);
}

// 3. Dynamic field-level authorization
const AdvancedSchema = a.schema({
  UserProfile: a.model({
    username: a.string().required(),
    email: a.email().required(),  // Use proper email type
    phone: a.phone(),              // Use proper phone type
    salary: a.float(),             // Sensitive field
    department: a.string(),
    managerId: a.string(),
    settings: a.json(),
    tags: a.string().array()       // Use array() for arrays
  }).authorization(allow => [
    // Owners can see all their fields
    allow.owner(),
    // HR can see salary
    allow.groups(['HR']).to(['read']),
    // Managers can see their reports
    allow.custom({
      provider: 'function',
      operations: ['read']
    })
  ])
  // Field-level auth implemented in resolvers
});

// 4. Time-based and conditional access
const ConditionalSchema = a.schema({
  TimeLimitedContent: a.model({
    title: a.string(),
    content: a.string(),
    accessStartDate: a.datetime(),
    accessEndDate: a.datetime(),
    requiredTier: a.enum(['free', 'premium']),
    maxViews: a.integer()
  }).authorization(allow => [
    allow.custom({
      provider: 'function',
      operations: ['read']
    })
  ])
});

// Time-based auth handler
export const timeBasedAuth = async (event: any) => {
  const now = new Date();
  const content = event.source;
  
  // Check time window
  const startDate = new Date(content.accessStartDate);
  const endDate = new Date(content.accessEndDate);
  
  if (now < startDate || now > endDate) {
    return { isAuthorized: false };
  }
  
  // Check user tier
  const userTier = await getUserTier(event.identity.userId);
  if (content.requiredTier === 'premium' && userTier === 'free') {
    return { isAuthorized: false };
  }
  
  // Check view count
  const viewCount = await incrementViewCount(
    event.identity.userId, 
    content.id
  );
  
  if (viewCount > content.maxViews) {
    return { isAuthorized: false };
  }
  
  return { isAuthorized: true };
};""",
                "nextSteps": "1. Implement caching for authorization checks\n2. Add audit logging for all auth decisions\n3. Create permission management UI\n4. Set up auth testing framework"
            },
            "optimistic-ui-updates": {
                "title": "Optimistic UI Update Patterns",
                "answer": "Implement instant UI feedback with proper rollback handling",
                "code": """// Optimistic UI patterns for Amplify Data
import { generateClient } from 'aws-amplify/data';
import { useOptimistic } from 'react';

// 1. Custom hook for optimistic updates
export function useOptimisticMutation<T extends { id: string }>() {
  const [optimisticItems, setOptimisticItems] = useState<Map<string, T>>(new Map());
  const [failedOperations, setFailedOperations] = useState<Set<string>>(new Set());

  const optimisticUpdate = async (
    item: T,
    mutation: () => Promise<T>,
    options?: {
      onSuccess?: (data: T) => void;
      onError?: (error: Error, rollbackData: T) => void;
    }
  ) => {
    const operationId = crypto.randomUUID();
    const previousState = { ...item };

    // Apply optimistic update
    setOptimisticItems(prev => new Map(prev).set(item.id, item));

    try {
      const result = await mutation();
      
      // Replace optimistic with real data
      setOptimisticItems(prev => {
        const next = new Map(prev);
        next.delete(item.id);
        return next;
      });
      
      options?.onSuccess?.(result);
      return result;
    } catch (error) {
      // Rollback
      setOptimisticItems(prev => {
        const next = new Map(prev);
        next.delete(item.id);
        return next;
      });
      
      setFailedOperations(prev => new Set(prev).add(operationId));
      
      options?.onError?.(error as Error, previousState);
      throw error;
    }
  };

  return {
    optimisticUpdate,
    optimisticItems,
    failedOperations,
    clearFailure: (id: string) => {
      setFailedOperations(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };
}

// 2. Optimistic list management
export function useOptimisticList<T extends { id: string }>(
  initialItems: T[]
) {
  const [items, setItems] = useState(initialItems);
  const [pendingOperations, setPendingOperations] = useState<
    Map<string, { type: 'create' | 'update' | 'delete'; timestamp: number }>
  >(new Map());

  const optimisticCreate = async (
    newItem: Omit<T, 'id'>,
    createFn: () => Promise<T>
  ) => {
    const tempId = `temp-${Date.now()}`;
    const optimisticItem = { ...newItem, id: tempId } as T;
    
    // Add to list immediately
    setItems(prev => [optimisticItem, ...prev]);
    setPendingOperations(prev => 
      new Map(prev).set(tempId, { type: 'create', timestamp: Date.now() })
    );

    try {
      const created = await createFn();
      
      // Replace temp item with real one
      setItems(prev => 
        prev.map(item => item.id === tempId ? created : item)
      );
      setPendingOperations(prev => {
        const next = new Map(prev);
        next.delete(tempId);
        return next;
      });
      
      return created;
    } catch (error) {
      // Remove failed item
      setItems(prev => prev.filter(item => item.id !== tempId));
      setPendingOperations(prev => {
        const next = new Map(prev);
        next.delete(tempId);
        return next;
      });
      throw error;
    }
  };

  const optimisticUpdate = async (
    id: string,
    updates: Partial<T>,
    updateFn: () => Promise<T>
  ) => {
    const originalItem = items.find(item => item.id === id);
    if (!originalItem) throw new Error('Item not found');

    // Apply update immediately
    setItems(prev =>
      prev.map(item =>
        item.id === id ? { ...item, ...updates } : item
      )
    );
    setPendingOperations(prev =>
      new Map(prev).set(id, { type: 'update', timestamp: Date.now() })
    );

    try {
      const updated = await updateFn();
      
      // Apply server response
      setItems(prev =>
        prev.map(item => item.id === id ? updated : item)
      );
      setPendingOperations(prev => {
        const next = new Map(prev);
        next.delete(id);
        return next;
      });
      
      return updated;
    } catch (error) {
      // Rollback to original
      setItems(prev =>
        prev.map(item => item.id === id ? originalItem : item)
      );
      setPendingOperations(prev => {
        const next = new Map(prev);
        next.delete(id);
        return next;
      });
      throw error;
    }
  };

  const optimisticDelete = async (
    id: string,
    deleteFn: () => Promise<void>
  ) => {
    const originalItem = items.find(item => item.id === id);
    if (!originalItem) throw new Error('Item not found');

    // Remove immediately
    setItems(prev => prev.filter(item => item.id !== id));
    setPendingOperations(prev =>
      new Map(prev).set(id, { type: 'delete', timestamp: Date.now() })
    );

    try {
      await deleteFn();
      
      setPendingOperations(prev => {
        const next = new Map(prev);
        next.delete(id);
        return next;
      });
    } catch (error) {
      // Restore item
      setItems(prev => [...prev, originalItem]);
      setPendingOperations(prev => {
        const next = new Map(prev);
        next.delete(id);
        return next;
      });
      throw error;
    }
  };

  return {
    items,
    pendingOperations,
    optimisticCreate,
    optimisticUpdate,
    optimisticDelete,
    isPending: (id: string) => pendingOperations.has(id)
  };
}

// 3. Real usage example with error handling
export function TodoList() {
  const client = generateClient<Schema>();
  const [todos, setTodos] = useState<Todo[]>([]);
  const { 
    items, 
    optimisticCreate, 
    optimisticUpdate, 
    optimisticDelete,
    isPending 
  } = useOptimisticList(todos);

  // Subscribe to real-time updates
  useEffect(() => {
    const sub = client.models.Todo.observeQuery().subscribe({
      next: ({ items }) => setTodos(items),
      error: (err) => console.error('Subscription error:', err)
    });

    return () => sub.unsubscribe();
  }, []);

  const createTodo = async (content: string) => {
    try {
      await optimisticCreate(
        { content, isDone: false, createdAt: new Date().toISOString() },
        async () => {
          const { data } = await client.models.Todo.create({ content });
          return data;
        }
      );
      
      toast.success('Todo created!');
    } catch (error) {
      toast.error('Failed to create todo. Please try again.');
    }
  };

  const toggleTodo = async (todo: Todo) => {
    try {
      await optimisticUpdate(
        todo.id,
        { isDone: !todo.isDone },
        async () => {
          const { data } = await client.models.Todo.update({
            id: todo.id,
            isDone: !todo.isDone
          });
          return data;
        }
      );
    } catch (error) {
      toast.error('Failed to update todo.');
    }
  };

  const deleteTodo = async (id: string) => {
    try {
      await optimisticDelete(
        id,
        async () => {
          await client.models.Todo.delete({ id });
        }
      );
      
      toast.success('Todo deleted!');
    } catch (error) {
      toast.error('Failed to delete todo.');
    }
  };

  return (
    <div>
      {items.map(todo => (
        <div 
          key={todo.id} 
          className={isPending(todo.id) ? 'opacity-50' : ''}
        >
          <input
            type="checkbox"
            checked={todo.isDone}
            onChange={() => toggleTodo(todo)}
            disabled={isPending(todo.id)}
          />
          <span>{todo.content}</span>
          <button 
            onClick={() => deleteTodo(todo.id)}
            disabled={isPending(todo.id)}
          >
            Delete
          </button>
        </div>
      ))}
    </div>
  );
}

// 4. Conflict resolution pattern
export function useOptimisticWithConflictResolution<T>() {
  const [conflicts, setConflicts] = useState<
    Array<{
      id: string;
      local: T;
      remote: T;
      timestamp: number;
    }>
  >([]);

  const handleConflict = async (
    id: string,
    resolution: 'local' | 'remote' | ((local: T, remote: T) => T)
  ) => {
    const conflict = conflicts.find(c => c.id === id);
    if (!conflict) return;

    let resolved: T;
    if (resolution === 'local') {
      resolved = conflict.local;
    } else if (resolution === 'remote') {
      resolved = conflict.remote;
    } else {
      resolved = resolution(conflict.local, conflict.remote);
    }

    // Apply resolution
    await client.models.Todo.update(resolved);
    
    setConflicts(prev => prev.filter(c => c.id !== id));
  };

  return { conflicts, handleConflict };
}""",
                "nextSteps": "1. Add undo/redo functionality\n2. Implement offline queue for failed operations\n3. Create conflict resolution UI\n4. Add operation batching for performance"
            },
            "advanced-form-customization": {
                "title": "Advanced Form Customization Patterns",
                "answer": "Extensive form customization including validation, conditional fields, and complex UI",
                "code": """// Advanced form customization patterns
import { 
  FormBuilder,
  TextField,
  SelectField,
  StepperField,
  FileUploader,
  Collection
} from '@aws-amplify/ui-react';

// 1. Fully custom form with validation and conditional logic
export function AdvancedProductForm({ product, onSuccess }: {
  product?: Product;
  onSuccess: (product: Product) => void;
}) {
  const [formData, setFormData] = useState({
    name: product?.name || '',
    category: product?.category || '',
    price: product?.price || 0,
    hasDiscount: product?.hasDiscount || false,
    discountPercentage: product?.discountPercentage || 0,
    images: product?.images || [],
    specifications: product?.specifications || {},
    variants: product?.variants || []
  });
  
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  // Custom validation rules
  const validate = (field: string, value: any) => {
    const newErrors = { ...errors };

    switch (field) {
      case 'name':
        if (!value || value.length < 3) {
          newErrors.name = 'Product name must be at least 3 characters';
        } else if (value.length > 100) {
          newErrors.name = 'Product name must be less than 100 characters';
        } else {
          delete newErrors.name;
        }
        break;
        
      case 'price':
        if (value < 0) {
          newErrors.price = 'Price cannot be negative';
        } else if (value > 999999) {
          newErrors.price = 'Price cannot exceed $999,999';
        } else {
          delete newErrors.price;
        }
        break;
        
      case 'discountPercentage':
        if (formData.hasDiscount) {
          if (value < 0 || value > 100) {
            newErrors.discountPercentage = 'Discount must be between 0-100%';
          } else {
            delete newErrors.discountPercentage;
          }
        }
        break;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleFieldChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (touched[field]) {
      validate(field, value);
    }
  };

  const handleBlur = (field: string) => {
    setTouched(prev => ({ ...prev, [field]: true }));
    validate(field, formData[field as keyof typeof formData]);
  };

  // 2. Dynamic form sections
  const SpecificationsSection = () => {
    const [specs, setSpecs] = useState<Array<{ key: string; value: string }>>(
      Object.entries(formData.specifications).map(([key, value]) => ({ key, value }))
    );

    const addSpec = () => {
      setSpecs([...specs, { key: '', value: '' }]);
    };

    const updateSpec = (index: number, field: 'key' | 'value', value: string) => {
      const newSpecs = [...specs];
      newSpecs[index][field] = value;
      setSpecs(newSpecs);
      
      // Update form data
      const specsObj = newSpecs.reduce((acc, spec) => {
        if (spec.key) acc[spec.key] = spec.value;
        return acc;
      }, {} as Record<string, string>);
      
      handleFieldChange('specifications', specsObj);
    };

    const removeSpec = (index: number) => {
      const newSpecs = specs.filter((_, i) => i !== index);
      setSpecs(newSpecs);
    };

    return (
      <div className="specifications-section">
        <h3>Product Specifications</h3>
        {specs.map((spec, index) => (
          <div key={index} className="spec-row">
            <TextField
              label="Specification"
              value={spec.key}
              onChange={(e) => updateSpec(index, 'key', e.target.value)}
              placeholder="e.g., Weight"
            />
            <TextField
              label="Value"
              value={spec.value}
              onChange={(e) => updateSpec(index, 'value', e.target.value)}
              placeholder="e.g., 2.5 kg"
            />
            <Button onClick={() => removeSpec(index)} size="small">
              Remove
            </Button>
          </div>
        ))}
        <Button onClick={addSpec} variation="secondary">
          Add Specification
        </Button>
      </div>
    );
  };

  // 3. Complex variant management
  const VariantsSection = () => {
    const [variants, setVariants] = useState<ProductVariant[]>(
      formData.variants || []
    );

    const addVariant = () => {
      const newVariant: ProductVariant = {
        id: crypto.randomUUID(),
        size: '',
        color: '',
        sku: '',
        additionalPrice: 0,
        inventory: 0
      };
      setVariants([...variants, newVariant]);
    };

    const updateVariant = (id: string, updates: Partial<ProductVariant>) => {
      const newVariants = variants.map(v =>
        v.id === id ? { ...v, ...updates } : v
      );
      setVariants(newVariants);
      handleFieldChange('variants', newVariants);
    };

    return (
      <Collection
        items={variants}
        type="list"
        direction="column"
        gap="1rem"
      >
        {(variant, index) => (
          <Card key={variant.id}>
            <div className="variant-form">
              <SelectField
                label="Size"
                value={variant.size}
                onChange={(e) => updateVariant(variant.id, { size: e.target.value })}
              >
                <option value="">Select size</option>
                <option value="XS">XS</option>
                <option value="S">S</option>
                <option value="M">M</option>
                <option value="L">L</option>
                <option value="XL">XL</option>
              </SelectField>
              
              <ColorPicker
                label="Color"
                value={variant.color}
                onChange={(color) => updateVariant(variant.id, { color })}
              />
              
              <TextField
                label="SKU"
                value={variant.sku}
                onChange={(e) => updateVariant(variant.id, { sku: e.target.value })}
                placeholder="ABC-123"
              />
              
              <StepperField
                label="Additional Price"
                value={variant.additionalPrice}
                onStepChange={(value) => 
                  updateVariant(variant.id, { additionalPrice: value })
                }
                min={0}
                max={1000}
                step={0.01}
              />
              
              <StepperField
                label="Inventory"
                value={variant.inventory}
                onStepChange={(value) => 
                  updateVariant(variant.id, { inventory: value })
                }
                min={0}
                max={10000}
              />
            </div>
          </Card>
        )}
      </Collection>
    );
  };

  // 4. Advanced file upload with preview
  const ImageUploadSection = () => {
    const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
    
    return (
      <div className="image-upload-section">
        <FileUploader
          acceptedFileTypes={['image/*']}
          path="products/"
          maxFileCount={5}
          isResumable
          onUploadStart={({ key }) => {
            setUploadProgress(prev => ({ ...prev, [key]: 0 }));
          }}
          onUploadProgress={({ key, progress }) => {
            setUploadProgress(prev => ({ ...prev, [key]: progress }));
          }}
          onUploadSuccess={({ key }) => {
            handleFieldChange('images', [...formData.images, key]);
            setUploadProgress(prev => {
              const next = { ...prev };
              delete next[key];
              return next;
            });
          }}
          onUploadError={({ key, error }) => {
            console.error(`Upload failed for ${key}:`, error);
            setUploadProgress(prev => {
              const next = { ...prev };
              delete next[key];
              return next;
            });
          }}
        />
        
        {/* Image previews with reordering */}
        <DraggableImageGrid
          images={formData.images}
          onReorder={(newOrder) => handleFieldChange('images', newOrder)}
          onRemove={(key) => {
            handleFieldChange(
              'images', 
              formData.images.filter(img => img !== key)
            );
          }}
        />
        
        {/* Upload progress indicators */}
        {Object.entries(uploadProgress).map(([key, progress]) => (
          <ProgressBar key={key} value={progress} label={`Uploading...`} />
        ))}
      </div>
    );
  };

  // 5. Form submission with optimistic updates
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate all fields
    const isValid = Object.keys(formData).every(field => 
      validate(field, formData[field as keyof typeof formData])
    );
    
    if (!isValid) {
      setTouched(
        Object.keys(formData).reduce((acc, key) => ({ ...acc, [key]: true }), {})
      );
      return;
    }
    
    try {
      const result = product
        ? await client.models.Product.update({ id: product.id, ...formData })
        : await client.models.Product.create(formData);
        
      onSuccess(result.data);
      toast.success(`Product ${product ? 'updated' : 'created'} successfully!`);
    } catch (error) {
      toast.error('Failed to save product. Please try again.');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="advanced-product-form">
      <TextField
        label="Product Name"
        value={formData.name}
        onChange={(e) => handleFieldChange('name', e.target.value)}
        onBlur={() => handleBlur('name')}
        errorMessage={errors.name}
        hasError={!!errors.name && touched.name}
        isRequired
      />
      
      <SelectField
        label="Category"
        value={formData.category}
        onChange={(e) => handleFieldChange('category', e.target.value)}
      >
        <option value="">Select category</option>
        <option value="electronics">Electronics</option>
        <option value="clothing">Clothing</option>
        <option value="home">Home & Garden</option>
      </SelectField>
      
      <TextField
        label="Price"
        type="number"
        value={formData.price}
        onChange={(e) => handleFieldChange('price', parseFloat(e.target.value))}
        onBlur={() => handleBlur('price')}
        errorMessage={errors.price}
        hasError={!!errors.price && touched.price}
        isRequired
      />
      
      <CheckboxField
        label="Has Discount"
        checked={formData.hasDiscount}
        onChange={(e) => handleFieldChange('hasDiscount', e.target.checked)}
      />
      
      {formData.hasDiscount && (
        <StepperField
          label="Discount Percentage"
          value={formData.discountPercentage}
          onStepChange={(value) => handleFieldChange('discountPercentage', value)}
          min={0}
          max={100}
          step={5}
        />
      )}
      
      <Divider />
      
      <ImageUploadSection />
      
      <Divider />
      
      <SpecificationsSection />
      
      <Divider />
      
      <VariantsSection />
      
      <div className="form-actions">
        <Button type="submit" variation="primary" isLoading={isSubmitting}>
          {product ? 'Update Product' : 'Create Product'}
        </Button>
        <Button type="button" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}""",
                "nextSteps": "1. Add form state persistence (save drafts)\n2. Implement multi-step forms with progress\n3. Add keyboard navigation support\n4. Create reusable form field components"
            },
            
            "recipe-sharing-app": {
                "title": "Recipe Sharing Platform Starter",
                "answer": "Complete setup for a recipe sharing application with user profiles, social features, and media storage",
                "code": """## Create Recipe Sharing Platform

```bash
npx create-next-app@14.2.10 recipe-sharing-platform --typescript --app --tailwind --eslint
cd recipe-sharing-platform
npm install aws-amplify@^6.6.0 @aws-amplify/ui-react@^6.5.0
npm install -D @aws-amplify/backend@^1.4.0 @aws-amplify/backend-cli@^1.2.0
```

**amplify/data/resource.ts:**
```typescript
import { a, defineData } from '@aws-amplify/backend';

const schema = a.schema({
  Recipe: a.model({
    title: a.string().required(),
    description: a.string(),
    ingredients: a.string().array().required(),
    instructions: a.string().array().required(),
    prepTime: a.integer(),
    cookTime: a.integer(),
    servings: a.integer(),
    difficulty: a.enum(['easy', 'medium', 'hard']),
    imageUrl: a.string(),
    tags: a.string().array(),
    authorId: a.id().required(),
    author: a.belongsTo('UserProfile', 'authorId'),
    ratings: a.hasMany('Rating', 'recipeId')
  }).authorization(allow => [
    allow.owner().to(['create', 'update', 'delete']),
    allow.authenticated().to(['read'])
  ]),
  
  UserProfile: a.model({
    username: a.string().required(),
    bio: a.string(),
    avatarUrl: a.string(),
    recipes: a.hasMany('Recipe', 'authorId')
  }).authorization(allow => [
    allow.owner(),
    allow.authenticated().to(['read'])
  ])
});

export const data = defineData({ schema });
```""",
                "nextSteps": "1. Add image upload with Storage\n2. Implement recipe search\n3. Build rating system\n4. Create social features"
            },
            
            "ecommerce-platform": {
                "title": "E-Commerce Platform Starter",
                "answer": "Full e-commerce setup with products, cart, and orders",
                "code": """## Create E-Commerce Platform

```bash
npx create-next-app@14.2.10 ecommerce-platform --typescript --app --tailwind --eslint
cd ecommerce-platform
npm install aws-amplify@^6.6.0 @aws-amplify/ui-react@^6.5.0
npm install -D @aws-amplify/backend@^1.4.0 @aws-amplify/backend-cli@^1.2.0
```

**amplify/data/resource.ts:**
```typescript
import { a, defineData } from '@aws-amplify/backend';

const schema = a.schema({
  Product: a.model({
    name: a.string().required(),
    description: a.string(),
    price: a.float().required(),
    salePrice: a.float(),
    sku: a.string().required(),
    category: a.string().required(),
    images: a.string().array(),
    inStock: a.boolean().default(true),
    stockQuantity: a.integer().default(0)
  }).authorization(allow => [
    allow.publicApiKey().to(['read']),
    allow.groups(['admin']).to(['create', 'update', 'delete'])
  ]),
  
  Cart: a.model({
    userId: a.id().required(),
    items: a.hasMany('CartItem', 'cartId'),
    subtotal: a.float().default(0),
    total: a.float().default(0)
  }).authorization(allow => [allow.owner()]),
  
  Order: a.model({
    userId: a.id().required(),
    orderNumber: a.string().required(),
    status: a.enum(['pending', 'processing', 'shipped', 'delivered']),
    total: a.float().required(),
    shippingAddress: a.json().required()
  }).authorization(allow => [
    allow.owner(),
    allow.groups(['admin'])
  ])
});

export const data = defineData({ schema });
```""",
                "nextSteps": "1. Build product catalog UI\n2. Implement cart functionality\n3. Add payment integration\n4. Create admin dashboard"
            },
            
            "saas-starter": {
                "title": "SaaS Application Starter",
                "answer": "Multi-tenant SaaS setup with teams and subscriptions",
                "code": """## Create SaaS Platform

```bash
npx create-next-app@14.2.10 saas-platform --typescript --app --tailwind --eslint
cd saas-platform
npm install aws-amplify@^6.6.0 @aws-amplify/ui-react@^6.5.0
npm install -D @aws-amplify/backend@^1.4.0 @aws-amplify/backend-cli@^1.2.0
```

**amplify/data/resource.ts:**
```typescript
import { a, defineData } from '@aws-amplify/backend';

const schema = a.schema({
  Organization: a.model({
    name: a.string().required(),
    slug: a.string().required(),
    plan: a.enum(['free', 'starter', 'pro', 'enterprise']).default('free'),
    billingEmail: a.email(),
    members: a.hasMany('TeamMember', 'organizationId'),
    projects: a.hasMany('Project', 'organizationId')
  }).authorization(allow => [
    allow.owner(),
    allow.groups(['admin'])
  ]),
  
  TeamMember: a.model({
    organizationId: a.id().required(),
    organization: a.belongsTo('Organization', 'organizationId'),
    userId: a.id().required(),
    email: a.email().required(),
    role: a.enum(['owner', 'admin', 'member', 'viewer']).required()
  }).authorization(allow => [
    allow.owner(),
    allow.groups(['admin'])
  ]),
  
  Project: a.model({
    name: a.string().required(),
    organizationId: a.id().required(),
    organization: a.belongsTo('Organization', 'organizationId'),
    settings: a.json()
  }).authorization(allow => [
    allow.owner(),
    allow.groups(['admin'])
  ])
});

export const data = defineData({ schema });
```""",
                "nextSteps": "1. Add team invitation system\n2. Implement billing with Stripe\n3. Build usage tracking\n4. Create role-based access"
            },
            
            "real-time-chat": {
                "title": "Real-Time Chat Application",
                "answer": "Chat app with channels and direct messages",
                "code": """## Create Chat Application

```bash
npx create-next-app@14.2.10 chat-application --typescript --app --tailwind --eslint
cd chat-application
npm install aws-amplify@^6.6.0 @aws-amplify/ui-react@^6.5.0
npm install -D @aws-amplify/backend@^1.4.0 @aws-amplify/backend-cli@^1.2.0
```

**amplify/data/resource.ts:**
```typescript
import { a, defineData } from '@aws-amplify/backend';

const schema = a.schema({
  Channel: a.model({
    name: a.string().required(),
    description: a.string(),
    type: a.enum(['public', 'private', 'direct']).required(),
    members: a.id().array(),
    messages: a.hasMany('Message', 'channelId')
  }).authorization(allow => [
    allow.authenticated().to(['read']),
    allow.owner().to(['create', 'update', 'delete'])
  ]),
  
  Message: a.model({
    channelId: a.id().required(),
    channel: a.belongsTo('Channel', 'channelId'),
    content: a.string().required(),
    authorId: a.id().required(),
    authorName: a.string().required()
  }).authorization(allow => [
    allow.authenticated().to(['read', 'create']),
    allow.owner().to(['update', 'delete'])
  ])
});

export const data = defineData({ schema });
```

**Real-time subscription:**
```typescript
const sub = client.models.Message
  .observeQuery({ filter: { channelId: { eq: channelId }}})
  .subscribe({
    next: ({ items }) => setMessages(items)
  });
```""",
                "nextSteps": "1. Add typing indicators\n2. Implement file sharing\n3. Build notification system\n4. Add message reactions"
            },
            
            "social-media-app": {
                "title": "Social Media Platform Starter",
                "answer": "Instagram-like social platform with posts and engagement",
                "code": """## Create Social Media App

```bash
npx create-next-app@14.2.10 social-media-app --typescript --app --tailwind --eslint
cd social-media-app
npm install aws-amplify@^6.6.0 @aws-amplify/ui-react@^6.5.0
npm install -D @aws-amplify/backend@^1.4.0 @aws-amplify/backend-cli@^1.2.0
```

**amplify/data/resource.ts:**
```typescript
import { a, defineData } from '@aws-amplify/backend';

const schema = a.schema({
  UserProfile: a.model({
    username: a.string().required(),
    displayName: a.string().required(),
    bio: a.string(),
    avatarUrl: a.string(),
    isVerified: a.boolean().default(false),
    posts: a.hasMany('Post', 'authorId'),
    followers: a.hasMany('Follow', 'followingId'),
    following: a.hasMany('Follow', 'followerId')
  }).authorization(allow => [
    allow.owner(),
    allow.authenticated().to(['read'])
  ]),
  
  Post: a.model({
    authorId: a.id().required(),
    author: a.belongsTo('UserProfile', 'authorId'),
    content: a.string(),
    images: a.string().array().required(),
    tags: a.string().array(),
    likes: a.hasMany('Like', 'postId'),
    comments: a.hasMany('Comment', 'postId')
  }).authorization(allow => [
    allow.owner().to(['create', 'update', 'delete']),
    allow.authenticated().to(['read'])
  ]),
  
  Like: a.model({
    postId: a.id().required(),
    userId: a.id().required()
  }).authorization(allow => [
    allow.owner(),
    allow.authenticated().to(['read'])
  ])
});

export const data = defineData({ schema });
```""",
                "nextSteps": "1. Build infinite scroll feed\n2. Add story feature\n3. Implement explore page\n4. Create direct messaging"
            }
        }
        
        guide = guides.get(task)
        if not guide:
            return [types.TextContent(
                type="text",
                text=validate_response("Task not found. Available tasks: " + ", ".join(guides.keys()) + "\n\nTry searchDocs() for other questions.")
            )]
        
        return [types.TextContent(
            type="text",
            text=validate_response(f"# {guide['title']}\n\n{guide['answer']}\n\n## Code Example:\n```typescript\n{guide['code']}\n```\n\n## Next Steps:\n{guide['nextSteps']}")
        )]
    
    elif name == "getDocumentationOverview":
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
                text=validate_response(f"""# Amplify Gen 2 Documentation Overview
                
Total Documents: {stats.get('total_documents', 0)}
Last Updated: {stats.get('last_update', 'Unknown')}

Categories:
{chr(10).join(f"- {cat}: {count} documents" for cat, count in stats.get('categories', {}).items())}

Use searchDocs to find specific topics or getDocument to retrieve full documentation.""")
            )]
        
        # Load the index
        with open(index_file, 'r', encoding='utf-8') as f:
            index = json.load(f)
        
        if format_type == "full":
            # Return full detailed overview
            return [types.TextContent(
                type="text",
                text=validate_response(index["overview"])
            )]
        else:
            # Return summary overview
            summary = f"""# Amplify Gen 2 Documentation Summary

## Quick Access Commands
- Create new app: `npx create-next-app@14.2.10 your-app-name --typescript --app --tailwind --eslint`
- Install Amplify: `npm install aws-amplify@^6.6.0 @aws-amplify/ui-react@^6.5.0`
- Search docs: Use searchDocs tool with your query
- Get patterns: Use findPatterns tool with pattern type
- **Field Types Reference**: `quickHelp({task: "data-field-types"})`

## Key Data Field Types
- Basic: `a.string()`, `a.integer()`, `a.float()`, `a.boolean()`, `a.date()`
- Validated: `a.email()`, `a.phone()`, `a.url()`, `a.ipAddress()` ✅
- Arrays: Any type + `.array()` (e.g., `a.string().array()`)
- Complex: `a.json()` for nested objects

## Main Categories
"""
            for cat_id, cat_data in index["categories"].items():
                summary += f"\n**{cat_data['title']}** ({cat_data['doc_count']} docs)\n"
                summary += f"{cat_data['summary'][:150]}...\n"
            
            summary += "\n## Common Patterns Available\n"
            patterns = ["auth", "api", "storage", "data", "deployment"]
            summary += "- " + "\n- ".join(patterns)
            
            summary += "\n\n💡 Use getDocumentationOverview with format='full' for detailed information."
            
            return [types.TextContent(type="text", text=validate_response(summary))]
    
    elif name == "searchDocs":
        query = arguments["query"]
        category = arguments.get("category")
        limit = arguments.get("limit", 10)
        
        # 1. Detect intent
        intent = detect_query_intent(query)
        logger.info(f"Search intent detected: {intent} for query: {query}")
        
        # 2. Detect anti-patterns and provide immediate corrections
        anti_patterns = detect_anti_patterns(query)
        warnings = []
        if anti_patterns:
            warnings.append("⚠️ **Common Mistakes Detected:**")
            for pattern_info in anti_patterns.values():
                warnings.append(f"- {pattern_info['issue']}: {pattern_info['correction']}")
        
        # 3. Check if this is a project creation query (with enhanced detection)
        if intent == 'setup' and should_provide_project_setup and should_provide_project_setup(query):
            response = ""
            if warnings:
                response = "\n".join(warnings) + "\n\n---\n\n"
            response += generate_project_setup_response(query)
            return [types.TextContent(
                type="text",
                text=validate_response(response)
            )]
        
        # 4. Expand query terms based on intent
        expanded_terms = expand_query_terms(query, intent)
        logger.info(f"Expanded search terms: {expanded_terms}")
        
        db = AmplifyDocsDatabase()
        
        # 5. Validate category if provided
        if category:
            valid_categories = db.list_categories()
            if category not in valid_categories:
                return [types.TextContent(
                    type="text",
                    text=f"Invalid category '{category}'. Valid categories are:\n" + 
                         "\n".join(f"- {cat}" for cat in sorted(valid_categories)) +
                         f"\n\nSearching without category filter for '{query}'..."
                )]
                category = None
        
        # 6. Search with expanded terms
        all_results = []
        seen_urls = set()
        
        # Search for each expanded term
        for term in expanded_terms[:5]:  # Limit to prevent too many searches
            term_results = db.search_documents(term, category, limit)
            for doc in term_results:
                if doc['url'] not in seen_urls:
                    # Calculate relevance boost
                    doc['relevance_boost'] = calculate_relevance_boost(doc, query, intent)
                    all_results.append(doc)
                    seen_urls.add(doc['url'])
        
        # 7. Sort by relevance boost
        all_results.sort(key=lambda x: x.get('relevance_boost', 1.0), reverse=True)
        results = all_results[:limit]
        
        # 8. Build response with warnings and contextual help
        response_text = ""
        
        # Add warnings if any
        if warnings:
            response_text += "\n".join(warnings) + "\n\n"
        
        # Add contextual help based on intent
        if intent == 'auth':
            response_text += "📚 **Authorization Quick Reference:**\n"
            response_text += "- ✅ Correct: `allow.owner()`, `allow.authenticated()`, `allow.groups(['admin'])`\n"
            response_text += "- ❌ Wrong: `.ownerField().identityClaim()` (old Gen 1 syntax)\n\n"
        elif intent == 'timestamps':
            response_text += "💡 **Timestamp Fields:**\n"
            response_text += "- Amplify automatically adds `createdAt` and `updatedAt` to all models\n"
            response_text += "- Do NOT define these fields manually in your schema\n\n"
        elif intent == 'setup':
            response_text += "🚀 **Project Setup:**\n"
            response_text += "- ✅ Use: `npx create-next-app@14.2.10 your-app-name`\n"
            response_text += "- ❌ Don't: Clone the GitHub template repository\n\n"
        
        # Check if user is searching for field types (existing logic)
        query_lower = query.lower()
        field_type_terms = [
            "field type", "data type", "model field", "schema type",
            "a.string", "a.email", "a.phone", "a.integer", "a.float",
            "email validation", "phone validation", "array field",
            "what types", "supported types", "available types",
            "field validation", "data validation", "type validation"
        ]
        
        if any(term in query_lower for term in field_type_terms):
            # Add field types reference as first result
            field_type_ref = f"""## 📋 Amplify Gen 2 Field Types Quick Reference

### Basic Types
- `a.string()` - Text values
- `a.integer()` - Whole numbers  
- `a.float()` - Decimal numbers
- `a.boolean()` - True/false values
- `a.date()` - Date only (YYYY-MM-DD)
- `a.datetime()` - Date and time

### Validated Types (YES, these are supported! ✅)
- `a.email()` - Email with built-in validation
- `a.phone()` - Phone numbers with validation
- `a.url()` - URLs with validation
- `a.ipAddress()` - IP addresses with validation

### Arrays
- `a.string().array()` - Array of strings
- `a.integer().array()` - Array of numbers
- Any type + `.array()` works!

### Special Types
- `a.id()` - Unique identifiers
- `a.enum(['option1', 'option2'])` - Limited choices
- `a.json()` - Complex nested objects

**For complete examples:** Use `quickHelp({task: "data-field-types"})`

---

"""
            response_text += field_type_ref
        
        if not results:
            response_text += f"\nNo documents found matching '{query}'\n\n"
            # Suggest alternatives based on intent
            if intent == 'setup':
                response_text += "💡 **Try:** `quickHelp({task: 'create-app'})` for setup instructions\n"
            elif intent == 'auth':
                response_text += "💡 **Try:** `quickHelp({task: 'setup-email-auth'})` for authentication setup\n"
            elif intent == 'data':
                response_text += "💡 **Try:** `quickHelp({task: 'create-data-model'})` for data modeling\n"
        else:
            response_text += f"\nFound {len(results)} documents matching '{query}':\n\n"
            
            for i, doc in enumerate(results, 1):
                # Show relevance indicator for highly boosted results
                relevance_indicator = "⭐ " if doc.get('relevance_boost', 1.0) > 1.5 else ""
                response_text += f"{relevance_indicator}**{i}. {doc['title']}** ({doc['category']})\n"
                response_text += f"URL: {doc['url']}\n"
                # Include a snippet of content
                content_snippet = doc['content'][:200] + "..." if len(doc['content']) > 200 else doc['content']
                response_text += f"Content: {content_snippet}\n\n"
        
        # Add related patterns suggestion
        if intent != 'general':
            response_text += f"\n💡 **Related:** Use `findPatterns({{pattern_type: '{intent}'}})` for more {intent} examples\n"
        
        # Track search pattern for learning
        track_search_pattern(query, intent, len(results) > 0)
        
        # If user is struggling, add extra help
        if len(search_history) >= 3 and all(not s['results_found'] for s in search_history[-3:]):
            response_text += "\n\n🤔 **Having trouble finding what you need?**\n"
            response_text += "- Try `getDocumentationOverview()` to see all available topics\n"
            response_text += "- Use `quickHelp({task: 'your-task'})` for common tasks\n"
            response_text += "- Check `listCategories()` to browse by category\n"
        
        return [types.TextContent(type="text", text=validate_response(response_text))]
    
    elif name == "getDocument":
        url = arguments["url"]
        
        db = AmplifyDocsDatabase()
        doc = db.get_document_by_url(url)
        
        if not doc:
            return [types.TextContent(
                type="text",
                text=validate_response(f"Document not found: {url}")
            )]
        
        return [types.TextContent(
            type="text",
            text=validate_response(f"# {doc['title']}\n\n**URL:** {doc['url']}\n**Category:** {doc['category']}\n**Last Updated:** {doc['last_scraped']}\n\n## Content\n\n{doc['markdown_content']}")
        )]
    
    elif name == "listCategories":
        db = AmplifyDocsDatabase()
        categories = db.list_categories()
        
        return [types.TextContent(
            type="text",
            text=validate_response(f"Available categories:\n" + "\n".join(f"- {cat}" for cat in categories))
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
        
        return [types.TextContent(type="text", text=validate_response(response_text))]
    
    elif name == "findPatterns":
        pattern_type = arguments["pattern_type"]
        
        # Define search queries for different patterns - aligned with Amplify Gen 2 architecture
        pattern_queries = {
            # Authentication patterns (Cognito integration)
            "auth": "authentication signIn signUp cognito user authenticator multi-factor social providers",
            
            # REST/HTTP API patterns (API Gateway) - NOT the primary data solution
            "api": "rest api gateway http endpoint custom lambda apigateway authorization headers",
            
            # File operations (S3 integration)
            "storage": "s3 storage upload download file fileuploader storageimage uploadData downloadData",
            
            # CI/CD patterns
            "deployment": "deploy hosting amplify sandbox git npx pipeline build",
            
            # amplify/backend.ts patterns
            "configuration": "configure amplify_outputs.json defineBackend backend.ts setup",
            
            # Data field types
            "field-types": "field types string integer float boolean datetime email phone array json enum",
            
            # Amplify Data patterns (the PRIMARY data solution)
            "data": "defineData model schema real-time subscription generateClient observeQuery authorization",
            "database": "defineData model schema dynamodb table data real-time subscription",
            
            # Lambda functions
            "functions": "lambda function serverless backend handler custom business logic",
            
            # UI building patterns (including CRUD forms)
            "ui": "ui component library crud form generation formbuilder authenticator fileuploader storageimage",
            
            # Server-side rendering patterns
            "ssr": "server-side rendering nextjs ssr ssg static generation getServerSideProps",
            
            # TypeScript-first patterns
            "typescript": "typescript types generateClient type-safe schema typing interfaces",
            
            # Development workflows
            "workflow": "sandbox development git workflow pipeline local testing amplify sandbox"
        }
        
        db = AmplifyDocsDatabase()
        
        # Add logging for debugging
        logger.info(f"findPatterns called with pattern_type: {pattern_type}")
        
        # Apply specific filtering based on pattern type
        if pattern_type == "api":
            # For API patterns, exclude storage results
            query = pattern_queries.get(pattern_type)
            results = db.search_documents(query, limit=10)
            # Filter out storage documents
            original_count = len(results)
            results = [r for r in results if r['category'] != 'storage' and 'storage' not in r['url'].lower()]
            results = results[:5]  # Limit to 5 after filtering
            logger.info(f"API pattern search: {original_count} results before filtering, {len(results)} after filtering out storage")
            
        elif pattern_type == "data":
            # For data patterns, focus on api-data category and backend
            query = pattern_queries.get(pattern_type)
            # First try api-data category
            results = db.search_documents(query, category="api-data", limit=5)
            if len(results) < 3:
                # If not enough results, also search in backend category
                backend_results = db.search_documents(query, category="backend", limit=5)
                results.extend(backend_results)
                results = results[:5]  # Limit total to 5
            logger.info(f"Data pattern search: found {len(results)} results in api-data/backend categories")
            
        elif pattern_type == "storage":
            # For storage, search specifically in storage category
            query = pattern_queries.get(pattern_type)
            results = db.search_documents(query, category="storage", limit=5)
            logger.info(f"Storage pattern search: found {len(results)} results in storage category")
            
        else:
            # Default behavior for other patterns
            query = pattern_queries.get(pattern_type, pattern_type)
            results = db.search_documents(query, limit=5)
            logger.info(f"Pattern search for '{pattern_type}': found {len(results)} results")
        
        if not results:
            return [types.TextContent(
                type="text",
                text=validate_response(f"No patterns found for '{pattern_type}'")
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
        
        return [types.TextContent(type="text", text=validate_response(response_text))]
    
    elif name == "getCreateCommand":
        response_text = """# Create Amplify Gen 2 + Next.js Application

This creates a **clean, production-ready setup** with no sample code to remove - just the essentials you need.

Based on the official AWS template: https://github.com/aws-samples/amplify-next-template

## Step 1: Create Your Project

```bash
# Replace 'your-app-name' with a descriptive name using hyphens (e.g., recipe-sharing-app)
npx create-next-app@14.2.10 your-app-name --typescript --app --tailwind --eslint
cd your-app-name
```

## Step 2: Install Amplify

```bash
npm install aws-amplify@^6.6.0 @aws-amplify/ui-react@^6.5.0
npm install -D @aws-amplify/backend@^1.4.0 @aws-amplify/backend-cli@^1.2.0 typescript@^5.0.0
```

## Step 3: Set Up Your Backend

Create the backend structure:
```bash
mkdir -p amplify/auth amplify/data
```

**amplify/backend.ts:**
```typescript
import { defineBackend } from '@aws-amplify/backend';
import { auth } from './auth/resource';

export const backend = defineBackend({
  auth,
});
```

**amplify/auth/resource.ts:**
```typescript
import { defineAuth } from '@aws-amplify/backend';

export const auth = defineAuth({
  loginWith: {
    email: true,
  },
});
```

## Step 4: Configure Frontend

**app/components/ConfigureAmplifyClientSide.tsx:**
```typescript
"use client";

import { Amplify } from "aws-amplify";
import outputs from "@/amplify_outputs.json";

Amplify.configure(outputs, { ssr: true });

export default function ConfigureAmplifyClientSide() {
  return null;
}
```

## Step 5: Start Development

```bash
npx ampx sandbox
```

In a new terminal:
```bash
npm run dev
```

Your application is now ready!

## 💡 Pro Tip
Use the `getCleanStarterConfig` tool for a fully customizable setup with all configuration files.
"""
        return [types.TextContent(type="text", text=validate_response(response_text))]
    
    elif name == "getQuickStartPatterns":
        task = arguments["task"]
        
        patterns = {
            "create-app": """# Create New Amplify Gen 2 + Next.js App

Based on: https://github.com/aws-samples/amplify-next-template

```bash
npx create-next-app@14.2.10 my-app --typescript --app --tailwind
cd my-app
npm install aws-amplify@^6.6.0 @aws-amplify/ui-react@^6.5.0
npm install -D @aws-amplify/backend@^1.4.0 @aws-amplify/backend-cli@^1.2.0
```

Create your backend configuration in `amplify/backend.ts` and start with `npx ampx sandbox`.""",

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

            "crud-forms": """# CRUD Form Generation
## Automatic Form Generation from Data Models

Amplify Gen 2 provides Connected Forms that automatically generate CRUD interfaces from your data models.

## 1. Install Amplify UI:
```bash
npm install @aws-amplify/ui-react
```

## 2. Generate Forms from Schema:
```tsx
// app/admin/products/page.tsx
'use client';
import { FormBuilder } from '@aws-amplify/ui-react';
import { generateClient } from 'aws-amplify/data';
import type { Schema } from '@/amplify/data/resource';

const client = generateClient<Schema>();

export default function ProductAdmin() {
  return (
    <div>
      <h1>Product Management</h1>
      
      {/* Auto-generated Create Form */}
      <FormBuilder.Product.CreateForm
        onSuccess={(product) => {
          console.log('Product created:', product);
        }}
      />
      
      {/* Auto-generated Update Form */}
      <FormBuilder.Product.UpdateForm
        product={existingProduct}
        onSuccess={(product) => {
          console.log('Product updated:', product);
        }}
      />
    </div>
  );
}
```

## 3. Customize Generated Forms:
```tsx
<FormBuilder.Product.CreateForm
  fields={{
    name: {
      label: 'Product Name',
      placeholder: 'Enter product name',
      required: true,
    },
    price: {
      label: 'Price (USD)',
      type: 'number',
      min: 0,
      step: 0.01,
    },
    category: {
      label: 'Category',
      type: 'select',
      options: ['Electronics', 'Clothing', 'Food'],
    },
  }}
  onValidate={{
    price: (value) => {
      if (value < 0) return 'Price must be positive';
      return null;
    },
  }}
/>
```

## 4. List View with Actions:
```tsx
import { Collection, Card, Button } from '@aws-amplify/ui-react';

export function ProductList() {
  const { data: products } = await client.models.Product.list();
  
  return (
    <Collection
      items={products}
      type="list"
      direction="column"
      gap="20px"
    >
      {(product, index) => (
        <Card key={index}>
          <h3>{product.name}</h3>
          <p>${product.price}</p>
          <Button onClick={() => editProduct(product)}>
            Edit
          </Button>
          <Button onClick={() => deleteProduct(product.id)}>
            Delete
          </Button>
        </Card>
      )}
    </Collection>
  );
}
```

## 5. Advanced Form Features:
- **File Uploads**: Integrate with Storage
- **Relationships**: Handle nested data
- **Validation**: Custom business rules
- **Conditional Fields**: Show/hide based on values

Note: CRUD form generation is a core Amplify Gen 2 feature that significantly reduces boilerplate code for admin interfaces and data management screens.""",
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
            text=validate_response(f"{pattern}\n\n💡 **Next Steps:**\nUse `searchDocs` for more details on any specific topic mentioned above.")
        )]
    
    elif name == "getCleanStarterConfig":
        # Get parameters with defaults
        include_auth = arguments.get("includeAuth", True)
        include_storage = arguments.get("includeStorage", False)
        include_data = arguments.get("includeData", False)
        styling = arguments.get("styling", "css")
        
        # Check if user query suggests project creation
        if 'arguments' in locals() and 'user_query' in arguments:
            user_query = arguments['user_query']
            if should_provide_project_setup(user_query):
                return [types.TextContent(
                    type="text",
                    text=validate_response(generate_project_setup_response(user_query))
                )]
        
        # Build the response
        response_text = """# Create Your Amplify Gen 2 + Next.js App

## Setup Instructions

### 1. Create Next.js App
```bash
npx create-next-app@14.2.10 my-app --typescript --app
cd my-app
```

### 2. Install Amplify Dependencies (exact versions from AWS template)
```bash
npm install aws-amplify@^6.6.0 @aws-amplify/ui-react@^6.5.0
npm install -D @aws-amplify/backend@^1.4.0 @aws-amplify/backend-cli@^1.2.0
```
"""

        if styling == "tailwind":
            response_text += """
### 3. Install Tailwind CSS (Optional)
```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```
"""

        response_text += f"""
### {4 if styling == "tailwind" else 3}. Create Amplify Backend Structure
```bash"""
        
        # Build mkdir commands based on what's included
        mkdir_commands = []
        if include_auth:
            mkdir_commands.append("mkdir -p amplify/auth")
        if include_data:
            mkdir_commands.append("mkdir -p amplify/data")
        if include_storage:
            mkdir_commands.append("mkdir -p amplify/storage")
        
        if mkdir_commands:
            response_text += "\n" + "\n".join(mkdir_commands)
        else:
            response_text += "\nmkdir -p amplify"  # At least create the amplify directory
            
        response_text += """
```

## Configuration Files

### 📦 package.json (based on AWS template)
```json
{
  "name": "my-amplify-app",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "@aws-amplify/ui-react": "6.5.5",
    "aws-amplify": "6.6.6",
    "next": "14.2.10",
    "react": "^18",
    "react-dom": "^18"
  },
  "devDependencies": {
    "@aws-amplify/backend": "1.5.1",
    "@aws-amplify/backend-cli": "1.3.0",
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "aws-cdk": "^2",
    "aws-cdk-lib": "^2",
    "constructs": "^10.3.0",
    "esbuild": "^0.23.1",
    "tsx": "^4.19.0",
    "typescript": "5.6.2"
  }
}
```

### 🔧 amplify/backend.ts
```typescript
import { defineBackend } from '@aws-amplify/backend';"""

        if include_auth:
            response_text += "\nimport { auth } from './auth/resource';"
        if include_data:
            response_text += "\nimport { data } from './data/resource';"
        if include_storage:
            response_text += "\nimport { storage } from './storage/resource';"
            
        response_text += "\n\nexport const backend = defineBackend({"
        
        backends = []
        if include_auth:
            backends.append("  auth")
        if include_data:
            backends.append("  data")
        if include_storage:
            backends.append("  storage")
            
        response_text += "\n" + ",\n".join(backends) + "\n});\n```"
        
        if include_auth:
            response_text += """

### 🔐 amplify/auth/resource.ts
```typescript
import { defineAuth } from '@aws-amplify/backend';

export const auth = defineAuth({
  loginWith: {
    email: true,
  },
});
```"""

        if include_data:
            response_text += """

### 📊 amplify/data/resource.ts
```typescript
import { type ClientSchema, a, defineData } from '@aws-amplify/backend';

const schema = a.schema({
  // Define your models here
  // Example:
  // Item: a
  //   .model({
  //     name: a.string(),
  //     description: a.string(),
  //   })
  //   .authorization(allow => [allow.owner()]),
});

export type Schema = ClientSchema<typeof schema>;

export const data = defineData({
  schema,
  authorizationModes: {
    defaultAuthorizationMode: 'userPool',
  },
});
```"""

        if include_storage:
            response_text += """

### 📁 amplify/storage/resource.ts
```typescript
import { defineStorage } from '@aws-amplify/backend';

export const storage = defineStorage({
  name: 'myAppStorage',
  access: (allow) => ({
    'public/*': [
      allow.guest.to(['read']),
      allow.authenticated.to(['read', 'write', 'delete'])
    ],
    'protected/{entity_id}/*': [
      allow.authenticated.to(['read', 'write', 'delete'])
    ],
    'private/{entity_id}/*': [
      allow.entity('identity').to(['read', 'write', 'delete'])
    ]
  })
});
```"""

        response_text += """

### 📐 tsconfig.json (from AWS template)
```json
{
  "compilerOptions": {
    "target": "es5",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [
      {
        "name": "next"
      }
    ],
    "paths": {
      "@/*": ["./*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules", "amplify"]
}
```

### 📐 amplify/tsconfig.json
```json
{
  "compilerOptions": {
    "target": "es2022",
    "module": "es2022",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "strict": true,
    "skipLibCheck": true,
    "paths": {
      "$amplify/*": ["./*"]
    }
  }
}
```

### 🏗️ app/layout.tsx
```typescript
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import ConfigureAmplifyClientSide from "./ConfigureAmplifyClientSide";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Amplify Gen 2 + Next.js App",
  description: "Built with AWS Amplify Gen 2 and Next.js",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <ConfigureAmplifyClientSide />
        {children}
      </body>
    </html>
  );
}
```

### ⚙️ app/ConfigureAmplifyClientSide.tsx
```typescript
"use client";

import { Amplify } from "aws-amplify";
import outputs from "@/amplify_outputs.json";

Amplify.configure(outputs, { ssr: true });

export default function ConfigureAmplifyClientSide() {
  return null;
}
```

### 🏠 app/page.tsx
```typescript"""

        if include_auth:
            response_text += """
"use client";

import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';

export default function Home() {
  return (
    <Authenticator>
      {({ signOut, user }) => (
        <main className="flex min-h-screen flex-col items-center justify-center p-24">
          <h1 className="text-4xl font-bold mb-8">
            Welcome {user?.username}!
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Your Amplify Gen 2 + Next.js app is ready
          </p>
          <button
            onClick={signOut}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Sign out
          </button>
        </main>
      )}
    </Authenticator>
  );
}
```"""
        else:
            response_text += """
export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <h1 className="text-4xl font-bold mb-8">
        Welcome to Amplify Gen 2 + Next.js
      </h1>
      <p className="text-xl text-gray-600">
        Your app is ready. Start building!
      </p>
    </main>
  );
}
```"""

        response_text += "\n\n### 🎨 app/globals.css\n```css"
        
        if styling == "tailwind":
            response_text += """
@tailwind base;
@tailwind components;
@tailwind utilities;
```
"""
            if styling == "tailwind":
                response_text += """
### 🎨 tailwind.config.js
```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```"""
        elif styling == "css":
            response_text += """
* {
  box-sizing: border-box;
  padding: 0;
  margin: 0;
}

html,
body {
  max-width: 100vw;
  overflow-x: hidden;
  font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Oxygen,
    Ubuntu, Cantarell, Fira Sans, Droid Sans, Helvetica Neue, sans-serif;
}

a {
  color: inherit;
  text-decoration: none;
}

main {
  min-height: 100vh;
  padding: 4rem 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}
```"""
        else:  # none
            response_text += """
/* Add your custom styles here */
```"""

        response_text += """

## 🚀 Start Development

```bash
# Start the Amplify sandbox (local backend)
npx ampx sandbox

# In another terminal, start Next.js
npm run dev
```

Visit http://localhost:3000 to see your app!

## 📌 What You Get

✅ **Ready to Build**: Start coding immediately
✅ **Type Safety**: Full TypeScript configuration
✅ **Latest Versions**: Compatible, tested package versions
✅ **Modular**: Only includes what you need"""

        if include_auth:
            response_text += "\n✅ **Authentication**: Email/password auth ready to use"
        if include_data:
            response_text += "\n✅ **Data Layer**: Schema-based data modeling with real-time"
        if include_storage:
            response_text += "\n✅ **File Storage**: S3 storage with access controls"

        response_text += """

## 🎯 Next Steps

1. **Customize Auth** (if included):
   - Add social providers in `amplify/auth/resource.ts`
   - Customize the Authenticator component styling

2. **Define Data Models** (if included):
   - Add your models to `amplify/data/resource.ts`
   - Generate typed client with `npx ampx generate graphql-client-code`

3. **Add Storage Features** (if included):
   - Use `FileUploader` component for uploads
   - Use `StorageImage` for displaying S3 images

4. **Deploy to AWS**:
   ```bash
   npx ampx pipeline-deploy --branch main --app-id YOUR_APP_ID
   ```

## 🔗 Useful Commands

- `npx ampx sandbox` - Start local backend
- `npx ampx generate outputs` - Regenerate amplify_outputs.json
- `npx ampx status` - Check backend status
- `npm run build` - Build for production

## 📚 Learn More

- [Amplify Gen 2 Docs](https://docs.amplify.aws/nextjs)
- [Next.js Documentation](https://nextjs.org/docs)
- [Amplify UI Components](https://ui.docs.amplify.aws)

---

💡 **Tip**: This configuration provides exactly what you need to start building!
"""
        
        return [types.TextContent(
            type="text",
            text=validate_response(response_text)
        )]
    
    elif name == "getContextualWarnings":
        # Get context from arguments
        context = {
            'currentFile': arguments.get('currentFile', ''),
            'lastError': arguments.get('lastError', ''),
            'searchQuery': arguments.get('searchQuery', '')
        }
        
        # Get warnings based on context
        warnings = get_contextual_warnings(context)
        
        if not warnings:
            return [types.TextContent(
                type="text",
                text="✅ No issues detected in current context. You're following best practices!"
            )]
        
        # Build response
        response_text = "⚠️ **Contextual Warnings:**\n\n"
        
        # Group warnings by severity
        high_severity = [w for w in warnings if w.get('severity') == 'high']
        medium_severity = [w for w in warnings if w.get('severity') == 'medium']
        low_severity = [w for w in warnings if w.get('severity') == 'low']
        
        if high_severity:
            response_text += "🔴 **High Priority:**\n"
            for warning in high_severity:
                response_text += f"- {warning['message']}\n"
            response_text += "\n"
        
        if medium_severity:
            response_text += "🟡 **Medium Priority:**\n"
            for warning in medium_severity:
                response_text += f"- {warning['message']}\n"
            response_text += "\n"
        
        if low_severity:
            response_text += "🟢 **Low Priority:**\n"
            for warning in low_severity:
                response_text += f"- {warning['message']}\n"
            response_text += "\n"
        
        # Add suggestions based on warning types
        warning_types = set(w['type'] for w in warnings)
        
        response_text += "💡 **Helpful Resources:**\n"
        if 'setup' in warning_types:
            response_text += "- Use `quickHelp({task: 'create-app'})` for correct setup\n"
        if 'auth' in warning_types:
            response_text += "- Use `searchDocs({query: 'authorization patterns'})` for auth examples\n"
        if 'data' in warning_types:
            response_text += "- Use `quickHelp({task: 'data-field-types'})` for field type reference\n"
        if 'imports' in warning_types:
            response_text += "- Search for 'TypeScript imports' for correct import syntax\n"
        
        return [types.TextContent(
            type="text",
            text=validate_response(response_text)
        )]
    
    else:
        return [types.TextContent(
            type="text",
            text=validate_response(f"Unknown tool: {name}")
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