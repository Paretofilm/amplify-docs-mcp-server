# AWS Amplify Documentation MCP Server

An MCP (Model Context Provider) server that provides tools for scraping, indexing, and searching AWS Amplify Gen 2 documentation. This server enables Claude Code, Claude Desktop, and other MCP clients to easily access and search through Amplify documentation patterns and examples.

## Features

- **Documentation Scraping**: Automatically scrape and index AWS Amplify Gen 2 documentation
- **Smart Search**: Search through indexed documentation by query and category
- **Pattern Discovery**: Find common patterns and examples for auth, API, storage, and more
- **Category Organization**: Documentation is automatically categorized (getting-started, backend, frontend, deployment, etc.)
- **SQLite Storage**: Efficient local storage with full-text search capabilities
- **Markdown Conversion**: HTML documentation is converted to clean markdown format

## Installation

### Prerequisites

- Python 3.8 or higher
- uv (Python package manager)

### Setup

1. Clone or download this repository
2. Navigate to the project directory:
   ```bash
   cd amplify-docs-mcp-server
   ```
3. Install dependencies (already done if using the setup script):
   ```bash
   uv add mcp aiohttp beautifulsoup4 pydantic lxml
   ```

## Configuration

### For Claude Desktop

1. Open your Claude Desktop configuration file:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - Linux: `~/.config/claude/claude_desktop_config.json`

2. Add the server configuration:
   ```json
   {
     "mcpServers": {
       "amplify-docs": {
         "command": "uv",
         "args": ["run", "python", "/full/path/to/amplify_docs_server.py"],
         "env": {}
       }
     }
   }
   ```

3. Restart Claude Desktop

### For Claude Code

Claude Code automatically discovers MCP servers. Simply ensure the server is running or configure it in your project's MCP settings.

## Available Tools

### 1. fetchLatestDocs
Scrape and index the latest AWS Amplify Gen 2 documentation.

**Parameters:**
- `max_pages` (integer, optional): Maximum number of pages to scrape (default: 100)
- `force_refresh` (boolean, optional): Force re-scraping even if documents exist (default: false)

**Example:**
```
Use fetchLatestDocs with max_pages: 50
```

### 2. searchDocs
Search through the indexed Amplify documentation.

**Parameters:**
- `query` (string, required): Search query (searches titles and content)
- `category` (string, optional): Filter by category
- `limit` (integer, optional): Maximum number of results (default: 10)

**Categories:**
- getting-started
- backend
- frontend
- deployment
- reference
- guides
- general

**Example:**
```
Search for "authentication" in category "backend"
```

### 3. getDocument
Retrieve a specific document by URL.

**Parameters:**
- `url` (string, required): The full URL of the document

**Example:**
```
Get document at https://docs.amplify.aws/nextjs/build-a-backend/auth/
```

### 4. listCategories
List all available documentation categories.

**Example:**
```
List all categories
```

### 5. getStats
Get statistics about the indexed documentation.

**Example:**
```
Show documentation statistics
```

### 6. findPatterns
Find common Amplify Gen 2 patterns and examples.

**Parameters:**
- `pattern_type` (string, required): Type of pattern to find

**Pattern Types:**
- auth
- api
- storage
- deployment
- configuration
- database
- functions

**Example:**
```
Find patterns for "auth"
```

## Usage Examples

### Initial Setup
1. First, fetch the latest documentation:
   ```
   Use the fetchLatestDocs tool to index Amplify documentation
   ```

2. Check the statistics:
   ```
   Use getStats to see how many documents were indexed
   ```

### Searching for Information
```
Search for "cognito authentication" using searchDocs
```

### Finding Code Examples
```
Use findPatterns with pattern_type "auth" to find authentication examples
```

### Getting Specific Documentation
```
Use getDocument with url "https://docs.amplify.aws/nextjs/build-a-backend/data/"
```

## Running the Server

### Standalone Mode
```bash
uv run python amplify_docs_server.py
```

### Using the Shell Script
```bash
./run_server.sh
```

## Database

The server uses SQLite to store documentation locally. The database file `amplify_docs.db` is created in the same directory as the server.

### Database Schema

- **documents** table:
  - url (unique identifier)
  - title
  - content (raw text)
  - markdown_content
  - category
  - last_scraped
  - embedding_vector (reserved for future use)

- **scrape_metadata** table:
  - Tracks scraping sessions and status

## Development

### Testing the Server

Use the included test script:
```bash
uv run python test_server.py
```

### Logging

The server uses Python's logging module. Set the log level in the code:
```python
logging.basicConfig(level=logging.INFO)
```

## Troubleshooting

### Server Won't Start
- Ensure all dependencies are installed: `uv sync`
- Check Python version: `python --version` (requires 3.8+)
- Verify the file path in your MCP client configuration

### No Documents Found
- Run `fetchLatestDocs` first to populate the database
- Check if `amplify_docs.db` exists in the project directory
- Look for error messages in the logs

### Search Not Working
- Ensure documents are indexed (check with `getStats`)
- Try broader search terms
- Check category filters

## Contributing

Feel free to submit issues or pull requests to improve the server.

## License

This project is licensed under the MIT License.