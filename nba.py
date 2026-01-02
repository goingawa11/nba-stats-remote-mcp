from typing import Any
from fastmcp import FastMCP
from nba_api.stats.endpoints import scoreboardv2, boxscoretraditionalv2, boxscorefourfactorsv2, playbyplayv2, leaguegamefinder, playergamelog, playercareerstats, leaguedashplayerstats, leaguedashteamstats
from nba_api.stats.static import players
from nba_api.live.nba.endpoints import scoreboard as live_scoreboard
import pandas as pd

# Initialize FastMCP server
mcp = FastMCP("nba")
pd.set_option('display.max_rows', None)

# Health check endpoint for Railway
from starlette.responses import PlainTextResponse
from starlette.requests import Request

@mcp.custom_route("/", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    return PlainTextResponse("NBA MCP Server is running!")

def get_game_ids(game_date: str = None) -> set:
    if(game_date is None):
        s = scoreboardv2.ScoreboardV2(day_offset=-1)
    else:
        s = scoreboardv2.ScoreboardV2(game_date=game_date)
    games = None
    for r in s.get_dict()['resultSets']:
        if r['name'] == 'LineScore':
            games = r
    dataframe = pd.DataFrame(games['rowSet'], columns = games['headers']) 
    return set(dataframe['GAME_ID'])

def get_game_box_score(game_id: int) -> Any:
    game = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id).get_dict()['resultSets'][0]
    dataframe = pd.DataFrame(game['rowSet'], columns = game['headers']) 
    return dataframe 

def get_final_score(game: Any) -> dict:
    teams = set (game['TEAM_ABBREVIATION'] )
    team_1_name = teams.pop()
    team_2_name = teams.pop()
    team_1 = game[game['TEAM_ABBREVIATION'] == team_1_name]
    team_2 = game[game['TEAM_ABBREVIATION'] == team_2_name]
    team_1_pts = int(team_1['PTS'].sum())
    team_2_pts = int(team_2['PTS'].sum())
    return {team_1_name: team_1_pts, team_2_name: team_2_pts}

def get_play_by_play_data(game_id: str) -> Any:
    data = playbyplayv2.PlayByPlayV2(game_id=game_id).get_dict()['resultSets'][0]
    dataframe = pd.DataFrame(data['rowSet'], columns = data['headers'])
    return dataframe[['WCTIMESTRING', 'HOMEDESCRIPTION', 'NEUTRALDESCRIPTION', 'VISITORDESCRIPTION', 'SCORE']]


def filter_to_pra_columns(game: Any) -> Any:
    return game[['PLAYER_NAME', 'TEAM_CITY', 'PTS', 'REB', 'AST']]

def filter_to_full_columns(game: Any) -> Any:
    return game[['PLAYER_NAME', 'TEAM_CITY', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PLUS_MINUS', 'MIN']]


# Note: The old tools (get_game_ids_tool, get_game_scores, get_four_factors, get_pra_breakdown, get_full_breakdown)
# have been removed because they relied on scoreboardv2 which doesn't have 2025-26 season data.
# Use get_recent_scores + get_box_score instead for current season data.

@mcp.tool()
async def get_recent_scores(game_date: str, claude_summary=False) -> list:
    """Get scores for games on a specific date using LeagueGameFinder (works for recent 2025-26 season games).
    The game_date should be in MM/DD/YYYY format (e.g., '12/28/2025').
    Returns matchups and final scores for all games on that date.
    It can take an optional boolean, claude_summary, if this is false claude should only provide the scores and no other information, if it is true claude should give a little blurb."""
    games_df = leaguegamefinder.LeagueGameFinder(
        date_from_nullable=game_date,
        date_to_nullable=game_date,
        league_id_nullable='00'
    ).get_data_frames()[0]

    # Group by game to get both teams' scores
    results = []
    seen_games = set()
    for _, row in games_df.iterrows():
        game_id = row['GAME_ID']
        if game_id in seen_games:
            continue

        # Get both rows for this game
        game_rows = games_df[games_df['GAME_ID'] == game_id]
        if len(game_rows) == 2:
            seen_games.add(game_id)
            team1 = game_rows.iloc[0]
            team2 = game_rows.iloc[1]

            # Determine home/away from MATCHUP (@ = away, vs. = home)
            if '@' in team1['MATCHUP']:
                away, home = team1, team2
            else:
                home, away = team1, team2

            results.append({
                'game_id': game_id,
                'game_date': row['GAME_DATE'],
                'home_team': home['TEAM_NAME'],
                'home_score': int(home['PTS']),
                'away_team': away['TEAM_NAME'],
                'away_score': int(away['PTS']),
                'matchup': f"{away['TEAM_ABBREVIATION']} @ {home['TEAM_ABBREVIATION']}"
            })

    return results

@mcp.tool()
async def get_todays_scores(claude_summary=False) -> list:
    """Get live scores for today's NBA games using the live API endpoint.
    Returns current scores for games in progress, final scores for completed games, and scheduled times for upcoming games.
    It can take an optional boolean, claude_summary, if this is false claude should only provide the scores and no other information, if it is true claude should give a little blurb."""
    games_data = live_scoreboard.ScoreBoard().get_dict()
    games = games_data.get('scoreboard', {}).get('games', [])

    results = []
    for game in games:
        home_team = game['homeTeam']
        away_team = game['awayTeam']
        game_status = game['gameStatus']  # 1=scheduled, 2=in progress, 3=final

        result = {
            'home_team': f"{home_team['teamCity']} {home_team['teamName']}",
            'home_tricode': home_team['teamTricode'],
            'home_score': home_team['score'],
            'home_record': f"{home_team['wins']}-{home_team['losses']}",
            'away_team': f"{away_team['teamCity']} {away_team['teamName']}",
            'away_tricode': away_team['teamTricode'],
            'away_score': away_team['score'],
            'away_record': f"{away_team['wins']}-{away_team['losses']}",
            'game_status': game['gameStatusText'],
            'game_id': game['gameId']
        }
        results.append(result)

    return results

@mcp.tool()
async def get_player_game_log(player_name: str, num_games: int = 10, season: str = '2025-26') -> list:
    """Get the game log for a specific player showing their recent games.
    Args:
        player_name: The player's full name (e.g., 'LeBron James', 'Luka Doncic')
        num_games: Number of recent games to return (default 10)
        season: The season in YYYY-YY format (default '2025-26')
    Returns stats for each game including date, matchup, points, rebounds, assists, steals, blocks, turnovers, and minutes."""
    # Find player ID
    player_matches = players.find_players_by_full_name(player_name)
    if not player_matches:
        return [{"error": f"Player '{player_name}' not found"}]

    player_id = player_matches[0]['id']
    player_full_name = player_matches[0]['full_name']

    # Get game log
    gamelog = playergamelog.PlayerGameLog(player_id=player_id, season=season)
    df = gamelog.get_data_frames()[0]

    if df.empty:
        return [{"error": f"No games found for {player_full_name} in {season}"}]

    # Get requested number of games
    df = df.head(num_games)

    results = []
    for _, row in df.iterrows():
        results.append({
            'player': player_full_name,
            'date': row['GAME_DATE'],
            'matchup': row['MATCHUP'],
            'result': row['WL'],
            'min': row['MIN'],
            'pts': int(row['PTS']),
            'reb': int(row['REB']),
            'ast': int(row['AST']),
            'stl': int(row['STL']),
            'blk': int(row['BLK']),
            'tov': int(row['TOV']),
            'fg': f"{row['FGM']}-{row['FGA']}",
            'fg_pct': row['FG_PCT'],
            'three_pt': f"{row['FG3M']}-{row['FG3A']}",
            'ft': f"{row['FTM']}-{row['FTA']}",
            'plus_minus': row['PLUS_MINUS']
        })

    return results

@mcp.tool()
async def get_player_season_stats(player_name: str, season: str = '2025-26') -> list:
    """Get a player's season stats (totals and per-game averages) using the PlayerCareerStats endpoint.
    Args:
        player_name: The player's full name (e.g., 'LeBron James', 'Luka Doncic')
        season: The season in YYYY-YY format (default '2025-26')
    Returns season totals and per-game averages for points, rebounds, assists, steals, blocks, and shooting percentages."""
    # Find player ID
    player_matches = players.find_players_by_full_name(player_name)
    if not player_matches:
        return [{"error": f"Player '{player_name}' not found"}]

    player_id = player_matches[0]['id']
    player_full_name = player_matches[0]['full_name']

    # Get career stats
    career = playercareerstats.PlayerCareerStats(player_id=player_id)
    df = career.get_data_frames()[0]  # SeasonTotalsRegularSeason

    # Filter to requested season
    season_df = df[df['SEASON_ID'] == season]

    if season_df.empty:
        return [{"error": f"No stats found for {player_full_name} in {season}"}]

    results = []
    for _, row in season_df.iterrows():
        gp = row['GP']
        results.append({
            'player': player_full_name,
            'season': row['SEASON_ID'],
            'team': row['TEAM_ABBREVIATION'],
            'games_played': gp,
            'minutes_total': row['MIN'],
            'mpg': round(row['MIN'] / gp, 1) if gp > 0 else 0,
            'pts_total': row['PTS'],
            'ppg': round(row['PTS'] / gp, 1) if gp > 0 else 0,
            'reb_total': row['REB'],
            'rpg': round(row['REB'] / gp, 1) if gp > 0 else 0,
            'ast_total': row['AST'],
            'apg': round(row['AST'] / gp, 1) if gp > 0 else 0,
            'stl_total': row['STL'],
            'spg': round(row['STL'] / gp, 1) if gp > 0 else 0,
            'blk_total': row['BLK'],
            'bpg': round(row['BLK'] / gp, 1) if gp > 0 else 0,
            'tov_total': row['TOV'],
            'topg': round(row['TOV'] / gp, 1) if gp > 0 else 0,
            'fg_pct': row['FG_PCT'],
            'fg3_pct': row['FG3_PCT'],
            'ft_pct': row['FT_PCT']
        })

    return results

@mcp.tool()
async def get_league_leaders(
    stat: str = 'PTS',
    season: str = '2025-26',
    season_type: str = 'Regular Season',
    per_mode: str = 'PerGame',
    top_n: int = 20,
    position: str = None,
    conference: str = None,
    division: str = None,
    experience: str = None,
    starter_bench: str = None,
    last_n_games: int = 0,
    month: int = 0,
    location: str = None,
    outcome: str = None,
    shot_clock_range: str = None,
    college: str = None,
    country: str = None,
    draft_year: str = None,
    draft_pick: str = None
) -> list:
    """Get league leaders for any stat with extensive filtering options.

    Args:
        stat: Stat to sort by - PTS, REB, AST, STL, BLK, FG_PCT, FG3_PCT, FT_PCT, MIN, TOV, PLUS_MINUS, etc. (default 'PTS')
        season: Season in YYYY-YY format (default '2025-26')
        season_type: 'Regular Season', 'Playoffs', 'Pre Season', 'All Star' (default 'Regular Season')
        per_mode: 'PerGame', 'Totals', 'Per36', 'Per48' (default 'PerGame')
        top_n: Number of players to return (default 20)
        position: 'G' (Guard), 'F' (Forward), 'C' (Center), 'G-F', 'F-G', 'F-C', 'C-F' (default None)
        conference: 'East' or 'West' (default None)
        division: 'Atlantic', 'Central', 'Southeast', 'Northwest', 'Pacific', 'Southwest' (default None)
        experience: 'Rookie', 'Sophomore', 'Veteran' (default None)
        starter_bench: 'Starters' or 'Bench' (default None)
        last_n_games: Filter to last N games only, e.g. 5, 10, 15, 20 (default 0 = all games)
        month: Month number 1-12 (default 0 = all months)
        location: 'Home' or 'Road' (default None)
        outcome: 'W' or 'L' - stats only in wins or losses (default None)
        shot_clock_range: '24-22', '22-18 Very Early', '18-15 Early', '15-7 Average', '7-4 Late', '4-0 Very Late' (default None)
        college: Filter by college name, e.g. 'Duke', 'Kentucky' (default None)
        country: Filter by country, e.g. 'USA', 'France', 'Serbia' (default None)
        draft_year: Filter by draft year, e.g. '2020' (default None)
        draft_pick: '1st Round', '2nd Round', 'Undrafted' (default None)

    Returns list of player stats sorted by the specified stat."""

    # Build the API call with filters
    stats = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season,
        season_type_all_star=season_type,
        per_mode_detailed=per_mode,
        last_n_games=last_n_games,
        month=month,
        player_position_abbreviation_nullable=position or '',
        conference_nullable=conference or '',
        division_simple_nullable=division or '',
        player_experience_nullable=experience or '',
        starter_bench_nullable=starter_bench or '',
        location_nullable=location or '',
        outcome_nullable=outcome or '',
        shot_clock_range_nullable=shot_clock_range or '',
        college_nullable=college or '',
        country_nullable=country or '',
        draft_year_nullable=draft_year or '',
        draft_pick_nullable=draft_pick or ''
    )

    df = stats.get_data_frames()[0]

    # Handle empty results
    if df.empty:
        return [{"error": "No players found matching the specified filters"}]

    # Sort by requested stat (descending for most stats)
    ascending = stat in ['TOV']  # Turnovers lower is better
    df = df.nlargest(top_n, stat) if not ascending else df.nsmallest(top_n, stat)

    results = []
    for _, row in df.iterrows():
        results.append({
            'rank': len(results) + 1,
            'player': row['PLAYER_NAME'],
            'team': row['TEAM_ABBREVIATION'],
            'age': row['AGE'],
            'gp': row['GP'],
            'min': row['MIN'],
            'pts': row['PTS'],
            'reb': row['REB'],
            'ast': row['AST'],
            'stl': row['STL'],
            'blk': row['BLK'],
            'tov': row['TOV'],
            'fg_pct': row['FG_PCT'],
            'fg3_pct': row['FG3_PCT'],
            'ft_pct': row['FT_PCT'],
            'plus_minus': row['PLUS_MINUS']
        })

    return results

@mcp.tool()
async def get_box_score(game_id: str) -> list:
    """Get the full box score for a specific game by game ID.
    Use get_recent_scores first to find the game_id for a specific game.
    Args:
        game_id: The NBA game ID (e.g., '0022500460')
    Returns full player stats including points, rebounds, assists, steals, blocks, turnovers, and minutes."""
    try:
        box = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
        data = box.get_dict()

        # Get player stats (first resultSet)
        player_stats = data['resultSets'][0]
        df = pd.DataFrame(player_stats['rowSet'], columns=player_stats['headers'])

        if df.empty:
            return [{"error": f"No box score data found for game {game_id}"}]

        results = []
        for _, row in df.iterrows():
            results.append({
                'player': row['PLAYER_NAME'],
                'team': row['TEAM_ABBREVIATION'],
                'team_city': row['TEAM_CITY'],
                'position': row['START_POSITION'] if row['START_POSITION'] else 'Bench',
                'min': row['MIN'],
                'pts': int(row['PTS']) if pd.notna(row['PTS']) else 0,
                'reb': int(row['REB']) if pd.notna(row['REB']) else 0,
                'ast': int(row['AST']) if pd.notna(row['AST']) else 0,
                'stl': int(row['STL']) if pd.notna(row['STL']) else 0,
                'blk': int(row['BLK']) if pd.notna(row['BLK']) else 0,
                'tov': int(row['TO']) if pd.notna(row['TO']) else 0,
                'pf': int(row['PF']) if pd.notna(row['PF']) else 0,
                'plus_minus': row['PLUS_MINUS'],
                'fg': f"{int(row['FGM']) if pd.notna(row['FGM']) else 0}-{int(row['FGA']) if pd.notna(row['FGA']) else 0}",
                'fg_pct': row['FG_PCT'],
                'fg3': f"{int(row['FG3M']) if pd.notna(row['FG3M']) else 0}-{int(row['FG3A']) if pd.notna(row['FG3A']) else 0}",
                'fg3_pct': row['FG3_PCT'],
                'ft': f"{int(row['FTM']) if pd.notna(row['FTM']) else 0}-{int(row['FTA']) if pd.notna(row['FTA']) else 0}",
                'ft_pct': row['FT_PCT']
            })

        return results
    except Exception as e:
        return [{"error": f"Failed to get box score: {str(e)}"}]

@mcp.tool()
async def get_team_stats(
    season: str = '2025-26',
    season_type: str = 'Regular Season',
    measure_type: str = 'Advanced',
    per_mode: str = 'PerGame',
    conference: str = None,
    division: str = None,
    top_n: int = 30,
    sort_by: str = 'NET_RATING'
) -> list:
    """Get team statistics including advanced metrics like offensive/defensive rating, pace, and net rating.

    Args:
        season: Season in YYYY-YY format (default '2025-26')
        season_type: 'Regular Season', 'Playoffs', 'Pre Season' (default 'Regular Season')
        measure_type: 'Base', 'Advanced', 'Misc', 'Four Factors', 'Scoring', 'Opponent' (default 'Advanced')
        per_mode: 'PerGame', 'Totals', 'Per100Possessions' (default 'PerGame')
        conference: 'East' or 'West' (default None = all teams)
        division: 'Atlantic', 'Central', 'Southeast', 'Northwest', 'Pacific', 'Southwest' (default None)
        top_n: Number of teams to return (default 30 = all teams)
        sort_by: Stat to sort by - for Advanced: NET_RATING, OFF_RATING, DEF_RATING, PACE, PIE, etc. (default 'NET_RATING')

    Returns team stats sorted by the specified stat. Advanced stats include:
        - OFF_RATING: Points scored per 100 possessions
        - DEF_RATING: Points allowed per 100 possessions
        - NET_RATING: Difference between offensive and defensive rating
        - PACE: Possessions per 48 minutes
        - PIE: Player Impact Estimate (team level)
        - AST_PCT, AST_TO, AST_RATIO, OREB_PCT, DREB_PCT, REB_PCT, EFG_PCT, TS_PCT, etc."""
    try:
        stats = leaguedashteamstats.LeagueDashTeamStats(
            season=season,
            season_type_all_star=season_type,
            measure_type_detailed_defense=measure_type,
            per_mode_detailed=per_mode,
            conference_nullable=conference or '',
            division_simple_nullable=division or ''
        )

        df = stats.get_data_frames()[0]

        if df.empty:
            return [{"error": "No team stats found matching the specified filters"}]

        # Sort by requested stat (descending for most stats, ascending for DEF_RATING)
        ascending = sort_by in ['DEF_RATING']  # Lower defensive rating is better
        if sort_by in df.columns:
            df = df.nlargest(top_n, sort_by) if not ascending else df.nsmallest(top_n, sort_by)
        else:
            df = df.head(top_n)

        results = []
        for _, row in df.iterrows():
            team_data = {
                'rank': len(results) + 1,
                'team': row['TEAM_NAME'],
                'team_abbr': row['TEAM_ABBREVIATION'],
                'gp': row['GP'],
                'wins': row['W'],
                'losses': row['L'],
                'win_pct': row['W_PCT'],
                'min': row['MIN']
            }

            # Add stats based on measure type
            if measure_type == 'Advanced':
                team_data.update({
                    'off_rating': round(row['OFF_RATING'], 1) if 'OFF_RATING' in row else None,
                    'def_rating': round(row['DEF_RATING'], 1) if 'DEF_RATING' in row else None,
                    'net_rating': round(row['NET_RATING'], 1) if 'NET_RATING' in row else None,
                    'pace': round(row['PACE'], 1) if 'PACE' in row else None,
                    'pie': round(row['PIE'], 3) if 'PIE' in row else None,
                    'ast_pct': round(row['AST_PCT'], 3) if 'AST_PCT' in row else None,
                    'ast_to': round(row['AST_TO'], 2) if 'AST_TO' in row else None,
                    'oreb_pct': round(row['OREB_PCT'], 3) if 'OREB_PCT' in row else None,
                    'dreb_pct': round(row['DREB_PCT'], 3) if 'DREB_PCT' in row else None,
                    'reb_pct': round(row['REB_PCT'], 3) if 'REB_PCT' in row else None,
                    'efg_pct': round(row['EFG_PCT'], 3) if 'EFG_PCT' in row else None,
                    'ts_pct': round(row['TS_PCT'], 3) if 'TS_PCT' in row else None,
                })
            elif measure_type == 'Base':
                team_data.update({
                    'pts': row['PTS'],
                    'reb': row['REB'],
                    'ast': row['AST'],
                    'stl': row['STL'],
                    'blk': row['BLK'],
                    'tov': row['TOV'],
                    'fg_pct': row['FG_PCT'],
                    'fg3_pct': row['FG3_PCT'],
                    'ft_pct': row['FT_PCT'],
                    'plus_minus': row['PLUS_MINUS']
                })
            elif measure_type == 'Four Factors':
                team_data.update({
                    'efg_pct': row.get('EFG_PCT'),
                    'fta_rate': row.get('FTA_RATE'),
                    'tov_pct': row.get('TM_TOV_PCT'),
                    'oreb_pct': row.get('OREB_PCT'),
                    'opp_efg_pct': row.get('OPP_EFG_PCT'),
                    'opp_fta_rate': row.get('OPP_FTA_RATE'),
                    'opp_tov_pct': row.get('OPP_TOV_PCT'),
                    'opp_oreb_pct': row.get('OPP_OREB_PCT')
                })
            else:
                # For other measure types, include common available columns
                for col in ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG_PCT', 'FG3_PCT', 'FT_PCT']:
                    if col in row:
                        team_data[col.lower()] = row[col]

            results.append(team_data)

        return results
    except Exception as e:
        return [{"error": f"Failed to get team stats: {str(e)}"}]

@mcp.tool()
async def get_play_by_play(game_id: str) -> list:
    """Returns the play by play data from a game.
    Use get_recent_scores first to find the game_id.
    Args:
        game_id: The NBA game ID (e.g., '0022500460')"""
    try:
        pbp = playbyplayv2.PlayByPlayV2(game_id=game_id)
        data = pbp.get_dict()

        plays_data = data['resultSets'][0]
        df = pd.DataFrame(plays_data['rowSet'], columns=plays_data['headers'])

        if df.empty:
            return [{"error": f"No play-by-play data found for game {game_id}"}]

        results = []
        for _, row in df.iterrows():
            play = {
                'period': row['PERIOD'],
                'time': row['PCTIMESTRING'],
                'score': row['SCORE'],
                'margin': row['SCOREMARGIN']
            }
            # Add description based on which team made the play
            if pd.notna(row['HOMEDESCRIPTION']) and row['HOMEDESCRIPTION']:
                play['description'] = row['HOMEDESCRIPTION']
                play['team'] = 'HOME'
            elif pd.notna(row['VISITORDESCRIPTION']) and row['VISITORDESCRIPTION']:
                play['description'] = row['VISITORDESCRIPTION']
                play['team'] = 'AWAY'
            elif pd.notna(row['NEUTRALDESCRIPTION']) and row['NEUTRALDESCRIPTION']:
                play['description'] = row['NEUTRALDESCRIPTION']
                play['team'] = 'NEUTRAL'
            else:
                continue  # Skip empty plays

            results.append(play)

        return results
    except Exception as e:
        return [{"error": f"Failed to get play-by-play: {str(e)}"}]


if __name__ == "__main__":
    import os
    import sys

    # Force unbuffered output for Railway logs
    sys.stdout.reconfigure(line_buffering=True)

    print("NBA MCP Server starting...")
    print(f"Python version: {sys.version}")
    print(f"MCP_TRANSPORT: {os.getenv('MCP_TRANSPORT', 'not set')}")
    print(f"PORT: {os.getenv('PORT', 'not set')}")

    # Use HTTP transport for remote deployment, stdio for local
    # Default to HTTP if PORT is set (Railway sets PORT automatically)
    if os.getenv("PORT"):
        transport = os.getenv("MCP_TRANSPORT", "http")  # Default to http when PORT exists
    else:
        transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "http":
        # Remote server mode
        port = int(os.getenv("PORT", 8080))
        print(f"Starting HTTP server on 0.0.0.0:{port}...")
        sys.stdout.flush()
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=port
        )
    else:
        # Local mode (default)
        print("Starting in stdio mode...")
        mcp.run(transport='stdio')