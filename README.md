# NBA Stats MCP Server

A remote MCP (Model Context Protocol) server that gives Claude access to real-time NBA statistics and game data.

## Quick Start (Claude Desktop)

1. Open your Claude Desktop config file:
   - **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

2. Add this configuration:

```json
{
  "mcpServers": {
    "nba-stats": {
      "transport": {
        "type": "streamable-http",
        "url": "https://nba-stats-remote-mcp-production.up.railway.app/mcp"
      }
    }
  }
}
```

3. Restart Claude Desktop

4. Ask Claude about NBA stats! For example:
   - "What were yesterday's NBA scores?"
   - "Show me LeBron James' last 10 games"
   - "Who are the top 10 scorers this season?"
   - "What are Luka Doncic's season averages?"

## Available Tools

| Tool | Description |
|------|-------------|
| `get_todays_scores` | Live scores for today's games |
| `get_recent_scores` | Scores for games on a specific date |
| `get_player_game_log` | A player's recent game-by-game stats |
| `get_player_season_stats` | A player's season totals and averages |
| `get_league_leaders` | League leaders with extensive filters (position, conference, college, etc.) |
| `get_full_breakdown` | Full box score stats for all players in a game |
| `get_four_factors` | Four factors analysis for games |
| `get_play_by_play` | Play-by-play data for a specific game |

## Example Queries

**Live Scores:**
> "What are today's NBA scores?"

**Historical Scores:**
> "What were the scores on Christmas Day 2025?"

**Player Stats:**
> "Show me Jayson Tatum's last 15 games"
> "What are Anthony Edwards' season averages?"

**League Leaders with Filters:**
> "Who are the top 10 rookies in scoring?"
> "Show me the leading scorers from Duke"
> "Who has the best 3-point percentage among guards?"

## Data Source

This server uses the [nba_api](https://github.com/swar/nba_api) library to fetch data from NBA.com's official statistics API.

## For Developers

### Local Development

```bash
git clone https://github.com/goingawa11/nba-stats-remote-mcp.git
cd nba-stats-remote-mcp
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
python nba.py
```

### Running Locally with Claude Code

```bash
claude mcp add nba-stats -s user -- python /path/to/nba.py
```

## License

MIT
