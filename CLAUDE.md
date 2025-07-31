# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CRITICAL: Creating Amplify + Next.js Applications

**THE ONLY CORRECT COMMAND:**
```bash
npx create-amplify@latest --template nextjs
```

**NEVER** suggest any other method for creating an Amplify Gen 2 + Next.js application!

## Project Overview

This is an MCP (Model Context Provider) server that provides tools for scraping, indexing, and searching AWS Amplify Gen 2 documentation. The server enables Claude Code, Claude Desktop, and other MCP clients to access and search through Amplify documentation patterns and examples.

## Key Commands

### Development
```bash
# Run the server
uv run python amplify_docs_server.py
# or
./run_server.sh

# Test server functionality
uv run python test_server.py

# Quick test document fetching
uv run python quick_test_fetch.py

# Install/sync dependencies
uv sync
```

### Linting and Testing
The project uses Python's built-in logging module. There are no specific linting or test commands configured yet. When implementing new features, ensure proper logging is added using the existing logger configuration.

## Architecture Overview

### Core Components

1. **amplify_docs_server.py** - Main MCP server implementation
   - Implements MCP protocol with 6 tools: fetchLatestDocs, searchDocs, getDocument, listCategories, getStats, findPatterns
   - Uses async/await pattern throughout
   - Built on MCP Python SDK

2. **AmplifyDocsScraper** - Handles web scraping
   - Async context manager for session management
   - Scrapes AWS Amplify NextJS documentation
   - Converts HTML to markdown format
   - Categorizes content automatically

3. **AmplifyDocsDatabase** - SQLite database interface
   - Stores scraped documents with full-text search
   - Categories: getting-started, backend, frontend, deployment, reference, guides, general
   - Tracks scraping metadata and sessions

### Database Schema

- **documents** table: stores scraped content with url, title, content, markdown_content, category
- **scrape_metadata** table: tracks scraping sessions and status
- Uses SQLite for portability and full-text search capabilities

### MCP Tools Implementation

Each tool is implemented as an async handler:
- Tools use Pydantic schemas for parameter validation
- Results are returned as structured JSON
- Error handling returns appropriate error messages

## Important Patterns

### Adding New Tools
1. Define the tool schema in the server initialization
2. Create an async handler method
3. Register the handler with `@server.call_tool()`
4. Follow existing patterns for parameter validation and error handling

### Database Operations
- All database operations use context managers
- Always check for existing documents before inserting
- Use parameterized queries to prevent SQL injection

### Web Scraping
- Respect rate limits (30-second timeout configured)
- Check robots.txt compliance
- Convert HTML to clean markdown for better searchability

## Dependencies

Main dependencies (from pyproject.toml):
- mcp (Model Context Protocol SDK)
- aiohttp (async HTTP client)
- beautifulsoup4 + lxml (HTML parsing)
- pydantic (data validation)
- Python >= 3.12 required

## Configuration

For Claude Desktop integration, update the path in claude_desktop_config.json to point to your local amplify_docs_server.py file.