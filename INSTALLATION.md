# Installation Guide for amplify-gen-2-nextjs-docs MCP Server

This MCP server provides AWS Amplify Gen 2 documentation access for Claude Desktop and Claude Code.

## Prerequisites

- Python 3.12 or higher
- uv (Python package manager): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Claude Desktop and/or Claude Code installed

## Step 1: Clone the Repository

```bash
# Create MCP servers directory if it doesn't exist
mkdir -p ~/mcp-servers

# Clone the repository
cd ~/mcp-servers
git clone https://github.com/your-username/amplify-gen-2-nextjs-docs.git
cd amplify-gen-2-nextjs-docs
```

## Step 2: Set Up Python Environment

```bash
# Create virtual environment and install dependencies
uv venv
uv sync

# Initialize the documentation database (one-time setup)
uv run python amplify_docs_server.py
# Press Ctrl+C after it starts successfully
```

## Step 3: Create Wrapper Script

Create a wrapper script to ensure the server runs in the correct directory:

```bash
cat > run_amplify_mcp.sh << 'EOF'
#!/bin/bash
cd ~/mcp-servers/amplify-gen-2-nextjs-docs
~/.local/bin/uv run python amplify_docs_server.py
EOF

chmod +x run_amplify_mcp.sh
```

## Installation for Claude Desktop

### Option 1: Manual Configuration

1. Open Claude Desktop settings
2. Navigate to Developer → Edit Config
3. Add the following to your configuration:

```json
{
  "mcpServers": {
    "amplify-gen-2-nextjs-docs": {
      "command": "/Users/YOUR_USERNAME/.local/bin/uv",
      "args": [
        "--directory",
        "/Users/YOUR_USERNAME/mcp-servers/amplify-gen-2-nextjs-docs",
        "run",
        "python",
        "amplify_docs_server.py"
      ]
    }
  }
}
```

Replace `YOUR_USERNAME` with your actual username.

### Option 2: Use the Provided Config

```bash
# Copy the provided config (after updating paths)
cp claude_desktop_config.json ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

4. Restart Claude Desktop
5. Check the server status in Developer → MCP Servers

## Installation for Claude Code

Run the following command from any directory:

```bash
# Add the server globally (accessible from any project)
claude mcp add -s user amplify-gen-2-nextjs-docs ~/mcp-servers/amplify-gen-2-nextjs-docs/run_amplify_mcp.sh

# Verify installation
claude mcp list
```

You should see:
```
amplify-gen-2-nextjs-docs: ~/mcp-servers/amplify-gen-2-nextjs-docs/run_amplify_mcp.sh - ✓ Connected
```

## Using the Server

### In Claude Desktop

1. Start a new conversation
2. The server tools are automatically available
3. Claude will use them when answering Amplify-related questions

### In Claude Code

1. Type `/mcp` in the chat
2. Select `amplify-gen-2-nextjs-docs` from the list
3. Available tools:
   - `searchDocs` - Search Amplify documentation
   - `getDocument` - Retrieve specific documents
   - `listCategories` - List documentation categories
   - `getStats` - Get documentation statistics
   - `findPatterns` - Find code patterns
   - `getCreateCommand` - Get the correct Amplify + Next.js creation command

## Troubleshooting

### Server Not Connecting

1. Check Python installation:
   ```bash
   python --version  # Should be 3.12+
   ```

2. Check uv installation:
   ```bash
   which uv  # Should show path like ~/.local/bin/uv
   ```

3. Test the server manually:
   ```bash
   cd ~/mcp-servers/amplify-gen-2-nextjs-docs
   uv run python amplify_docs_server.py
   ```
   You should see no errors. Press Ctrl+C to stop.

### Claude Desktop Issues

1. Check logs:
   - Open Claude Desktop
   - Go to Developer → Open Logs Folder
   - Look for error messages

2. Verify paths in configuration match your system

### Claude Code Issues

1. Remove and re-add the server:
   ```bash
   claude mcp remove amplify-gen-2-nextjs-docs
   claude mcp add -s user amplify-gen-2-nextjs-docs ~/mcp-servers/amplify-gen-2-nextjs-docs/run_amplify_mcp.sh
   ```

2. Ensure you're using the user scope (`-s user`) for global access

## Updating the Documentation

The server comes with pre-indexed documentation. To update:

```bash
cd ~/mcp-servers/amplify-gen-2-nextjs-docs
uv run python -c "
from amplify_docs_server import AmplifyDocsScraper, AmplifyDocsDatabase
import asyncio

async def update():
    async with AmplifyDocsScraper() as scraper:
        await scraper.scrape_docs(force_refresh=True)

asyncio.run(update())
"
```

## Features

- **Fast Search**: Search across all Amplify Gen 2 documentation
- **Pattern Finding**: Discover common implementation patterns
- **Category Browsing**: Browse docs by category (backend, frontend, deployment, etc.)
- **Direct Document Access**: Retrieve specific documentation pages
- **Version Information**: Get compatible versions for Amplify and Next.js

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs in Claude Desktop/Code
3. Open an issue on the GitHub repository