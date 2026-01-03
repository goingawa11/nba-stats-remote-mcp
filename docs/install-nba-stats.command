#!/bin/bash

# NBA Stats MCP Installer for Claude Desktop
# This script automatically configures Claude Desktop to use the NBA Stats server

clear
echo "=============================================="
echo "   NBA Stats for Claude Desktop - Installer"
echo "=============================================="
echo ""

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/Claude"
    CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"
    OS_NAME="macOS"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
    CONFIG_DIR="$APPDATA/Claude"
    CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"
    OS_NAME="Windows"
else
    echo "❌ Unsupported operating system: $OSTYPE"
    echo "   This installer supports macOS and Windows only."
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Detected OS: $OS_NAME"
echo ""

# Check for Node.js
echo "Checking prerequisites..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "✅ Node.js is installed ($NODE_VERSION)"
else
    echo "❌ Node.js is not installed!"
    echo ""
    echo "Node.js is required to connect Claude Desktop to NBA Stats."
    echo "Please install it from: https://nodejs.org/"
    echo "(Choose the LTS version)"
    echo ""
    if [[ "$OS_NAME" == "macOS" ]]; then
        read -p "Would you like to open the download page? (y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            open "https://nodejs.org/"
        fi
    fi
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Check for npx
if command -v npx &> /dev/null; then
    echo "✅ npx is available"
else
    echo "❌ npx is not available (should come with Node.js)"
    echo "   Try reinstalling Node.js from https://nodejs.org/"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo ""

# Check if Claude Desktop config directory exists
if [ ! -d "$CONFIG_DIR" ]; then
    echo "⚠️  Claude Desktop config directory not found."
    echo "   Have you installed and run Claude Desktop at least once?"
    echo ""
    echo "   Expected location: $CONFIG_DIR"
    echo ""
    read -p "Would you like to create the directory? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        mkdir -p "$CONFIG_DIR"
        echo "✅ Created config directory"
    else
        echo "Installation cancelled."
        read -p "Press Enter to exit..."
        exit 1
    fi
fi

echo "Config location: $CONFIG_FILE"
echo ""

# The NBA Stats MCP configuration
NBA_CONFIG='{
  "command": "npx",
  "args": [
    "mcp-remote",
    "https://nba-stats-remote-mcp-production.up.railway.app/mcp"
  ]
}'

# Check if config file exists
if [ -f "$CONFIG_FILE" ]; then
    echo "Found existing Claude Desktop configuration."

    # Check if nba-stats is already configured
    if grep -q "nba-stats" "$CONFIG_FILE"; then
        echo "✅ NBA Stats is already configured!"
        echo ""
        echo "If you're having issues, try:"
        echo "1. Completely quit Claude Desktop"
        echo "2. Reopen Claude Desktop"
        echo ""
        read -p "Press Enter to exit..."
        exit 0
    fi

    # Backup existing config
    BACKUP_FILE="$CONFIG_FILE.backup.$(date +%Y%m%d%H%M%S)"
    cp "$CONFIG_FILE" "$BACKUP_FILE"
    echo "✅ Backed up existing config to: $BACKUP_FILE"

    # Check if file has mcpServers
    if grep -q "mcpServers" "$CONFIG_FILE"; then
        echo ""
        echo "Your config already has MCP servers configured."
        echo "Adding NBA Stats to your existing configuration..."
        echo ""

        # Use Python to safely merge JSON (available on macOS by default)
        python3 << EOF
import json

config_file = "$CONFIG_FILE"

# Read existing config
with open(config_file, 'r') as f:
    config = json.load(f)

# Add nba-stats to mcpServers
if 'mcpServers' not in config:
    config['mcpServers'] = {}

config['mcpServers']['nba-stats'] = {
    "command": "npx",
    "args": [
        "mcp-remote",
        "https://nba-stats-remote-mcp-production.up.railway.app/mcp"
    ]
}

# Write updated config
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)

print("✅ Added NBA Stats to existing configuration")
EOF
    else
        # Config exists but no mcpServers, create fresh
        echo "Creating new MCP configuration..."
        cat > "$CONFIG_FILE" << 'CONFIGEOF'
{
  "mcpServers": {
    "nba-stats": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://nba-stats-remote-mcp-production.up.railway.app/mcp"
      ]
    }
  }
}
CONFIGEOF
        echo "✅ Configuration created"
    fi
else
    # No config file exists, create new one
    echo "Creating new Claude Desktop configuration..."
    cat > "$CONFIG_FILE" << 'CONFIGEOF'
{
  "mcpServers": {
    "nba-stats": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://nba-stats-remote-mcp-production.up.railway.app/mcp"
      ]
    }
  }
}
CONFIGEOF
    echo "✅ Configuration created"
fi

echo ""
echo "=============================================="
echo "   ✅ Installation Complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "1. Quit Claude Desktop completely (Cmd+Q on Mac)"
echo "2. Reopen Claude Desktop"
echo "3. Try asking: \"What were the NBA scores last night?\""
echo ""
echo "Features you can now use:"
echo "• Live NBA scores"
echo "• Player stats and game logs"
echo "• Team advanced analytics"
echo "• Box scores and play-by-play"
echo ""
read -p "Press Enter to exit..."
