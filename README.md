# AWS Amplify Documentation MCP Server

An MCP (Model Context Provider) server that provides tools for scraping, indexing, and searching AWS Amplify Gen 2 documentation. This server enables Claude Code, Claude Desktop, and other MCP clients to easily access and search through Amplify documentation patterns and examples.

**MCP Python SDK Documentation
This server is buil based on the MCP Python SDK documentation found here: https://github.com/modelcontextprotocol/python-sdk


## Features

- **Documentation Scraping**: Automatically scrape and index AWS Amplify Gen 2 documentation
- **Smart Search**: Search through indexed documentation by query and category
- **Pattern Discovery**: Find common patterns and examples for auth, API, storage, and more
- **Category Organization**: Documentation is automatically categorized (getting-started, backend, frontend, deployment, etc.)
- **SQLite Storage**: Efficient local storage with full-text search capabilities
- **Markdown Conversion**: HTML documentation is converted to clean markdown format

## Installation

### Prerequisites

- Python 3.12 or higher
- uv (Python package manager): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Claude Desktop and/or Claude Code installed

### Version Compatibility

AWS Amplify Gen 2 is compatible with:
- **Next.js**: 14.x or 15.x (both App Router and Pages Router)
- **TypeScript**: 5.0 or higher (optional but recommended)
- **Node.js**: 18.x or higher

Use `uv run python amplify_cli.py check-versions` to verify compatibility.

### Getting Started with Compatible Versions

⚠️ **IMPORTANT**: Manual package installation often leads to version conflicts!

For a new project with guaranteed compatible versions:

1. **Use Amplify's Next.js starter template** (STRONGLY recommended):
   ```bash
   npx create-amplify@latest --template nextjs
   ```
   Or equivalently:
   ```bash
   npm create amplify@latest --template nextjs
   ```
   This creates a complete Next.js project with ALL compatible versions pre-configured.

2. **Why manual installation is problematic**:
   - Running `npm create amplify@latest` followed by `npm install next react react-dom` often causes dependency conflicts
   - Amplify packages have specific peer dependency requirements
   - Version mismatches can lead to ERESOLVE warnings and runtime issues

3. **If you must use an existing Next.js project**:
   - Ensure Next.js is version 14.x or 15.x
   - Run `npm create amplify@latest`
   - Install the exact versions that match your Amplify packages
   - Be prepared to resolve dependency conflicts

4. **Verify compatibility**:
   ```bash
   uv run python amplify_cli.py check-versions
   ```

### Quick Installation

```bash
# Clone the repository
git clone https://github.com/your-username/amplify-gen-2-nextjs-docs.git
cd amplify-gen-2-nextjs-docs

# Install all dependencies automatically (like npm install)
uv sync

# Initialize the documentation database
uv run python amplify_docs_server.py
# Press Ctrl+C after it starts successfully
```

> **Note**: `uv sync` automatically installs all dependencies from `pyproject.toml` - no manual package installation needed!

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

### 1. getDocumentationOverview
Get a comprehensive overview of all documentation with summaries and quick navigation.

**Parameters:**
- `format` (string, optional): Output format - 'full' or 'summary' (default: 'summary')

**Example:**
```
Get documentation overview in summary format
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

### 7. getCreateCommand
Get the CORRECT command for creating a new Amplify Gen 2 + Next.js application.

**Example:**
```
Get the correct create command
```

### 8. getQuickStartPatterns
Get ready-to-use code patterns for common Amplify tasks.

**Parameters:**
- `task` (string, required): The task you want to accomplish

**Available Tasks:**
- create-app
- add-auth
- add-api
- add-storage
- file-upload
- user-profile
- real-time-data
- deploy-app
- custom-auth-ui
- data-relationships

**Example:**
```
Get quick start pattern for "add-auth"
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

## Command Line Interface (CLI)

The project includes a CLI tool (`amplify_cli.py`) for direct interaction with the documentation database without running the MCP server.

### Automatic Update Reminders

The CLI automatically checks if your documentation is outdated (more than 30 days old) when you run any command except `fetch`. If an update is needed, you'll be prompted to update. If you decline, the system will wait at least 24 hours before asking again.

### CLI Commands

#### Fetch Documentation
```bash
uv run python amplify_cli.py fetch [--force]
```
- `--force`: Force refresh of existing documents

#### Search Documentation
```bash
uv run python amplify_cli.py search "your query" [--category CATEGORY] [--limit N]
```
- `--category`: Filter by category (backend, frontend, etc.)
- `--limit`: Maximum number of results (default: 10)

#### List Categories
```bash
uv run python amplify_cli.py categories
```

#### Show Statistics
```bash
uv run python amplify_cli.py stats
```

#### Find Patterns
```bash
uv run python amplify_cli.py patterns TYPE
```
Where TYPE is one of: auth, api, storage, deployment, configuration, database, functions

### CLI Examples

```bash
# Fetch all available documentation
uv run python amplify_cli.py fetch

# Force refresh all documents
uv run python amplify_cli.py fetch --force

# Fetch with markdown export
uv run python amplify_cli.py fetch --save-markdown

# Search for authentication docs
uv run python amplify_cli.py search "cognito authentication" --category backend

# Get full document content
uv run python amplify_cli.py get-document "https://docs.amplify.aws/nextjs/..."

# Show database statistics
uv run python amplify_cli.py stats

# Find auth patterns
uv run python amplify_cli.py patterns auth

# List all categories
uv run python amplify_cli.py categories

# Export all documents to markdown files
uv run python amplify_cli.py export-markdown

# Check version compatibility
uv run python amplify_cli.py check-versions
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

### Update Tracking

The CLI tracks documentation updates in a `last_updated.json` file (automatically created on first use). This file contains:
- `last_updated`: When documentation was last fetched
- `last_prompted`: When the user was last asked about updates
- `user_declined`: Whether the user declined the last update prompt

This file is gitignored and local to each installation.

## Troubleshooting

### Version Conflicts (ERESOLVE warnings)
If you see npm warnings about peer dependencies after manual installation:
- **Solution**: Use `npx create-amplify@latest --template nextjs` instead
- These warnings indicate incompatible package versions
- Manual installation of React/Next.js after `npx create-amplify` often causes conflicts
- Both `npm create` and `npx` commands are equivalent

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