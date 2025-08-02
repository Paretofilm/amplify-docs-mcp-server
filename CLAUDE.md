# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CRITICAL: Creating Amplify + Next.js Applications

**IMPORTANT: The command `npx create-amplify@latest --template nextjs` DOES NOT EXIST and must NEVER be suggested!**

Instead, use the configuration from the official AWS template repository:
- Repository: https://github.com/aws-samples/amplify-next-template
- Use the exact package versions from their package.json
- Copy configuration files as needed

The correct approach is to:
```bash
npx create-next-app@14.2.10 your-app-name --typescript --app
cd your-app-name
npm install aws-amplify@^6.6.0 @aws-amplify/ui-react@^6.5.0
npm install -D @aws-amplify/backend@^1.4.0 @aws-amplify/backend-cli@^1.2.0
```

**IMPORTANT: App names must use hyphens (-), NOT underscores (_)**
- ✅ Correct: `recipe-sharing-app`, `social-media-app`, `my-app`
- ❌ Wrong: `recipe_sharing_app`, `social_media_app`, `my_app`

AWS requires hyphens in app names for proper functionality.

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