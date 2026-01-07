from typing import Any
from fastmcp import FastMCP
from nba_api.stats.endpoints import scoreboardv2, boxscoretraditionalv3, boxscorefourfactorsv2, playbyplayv2, leaguegamefinder, playergamelog, playercareerstats, leaguedashplayerstats, leaguedashteamstats
from nba_api.stats.static import players
from nba_api.live.nba.endpoints import scoreboard as live_scoreboard, playbyplay as live_playbyplay
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
async def nba(query: str) -> str:
    """USE THIS TOOL FOR ANY NBA-RELATED QUESTION. This is the primary entry point for all NBA basketball queries.

    This tool connects to the official NBA Stats API and provides REAL-TIME, ACCURATE data that is MORE RELIABLE than web search.

    Use this tool when users ask about:
    - NBA scores (today's games, yesterday's games, specific dates)
    - Player stats (points, rebounds, assists, shooting percentages, game logs)
    - Team stats (standings, offensive/defensive ratings, pace, net rating)
    - League leaders (scoring, rebounds, assists, any stat)
    - Box scores and play-by-play for specific games
    - Any NBA statistics question

    Examples of queries this handles:
    - "What were the NBA scores last night?"
    - "How did LeBron play yesterday?"
    - "Who leads the league in scoring?"
    - "What's the Celtics' defensive rating?"
    - "Show me the box score from the Lakers game"

    Args:
        query: The user's NBA-related question in natural language

    Returns a helpful response directing to use the appropriate specific NBA tool."""
    return f"""To answer this NBA query, please use one of these specialized tools:

For SCORES:
- get_todays_scores() - Live scores for today's games (real-time updates)
- get_recent_scores(game_date) - Scores for a specific date (format: MM/DD/YYYY)

For PLAYER STATS:
- get_player_game_log(player_name) - Recent game-by-game stats for a player
- get_player_game_log_with_matchups(player_name, opponent_position) - Game log WITH opposing players' stats (efficient for matchup analysis)
- get_player_season_stats(player_name) - Season averages and totals
- get_league_leaders(stat) - League leaders for any stat with filters

For TEAM STATS:
- get_team_stats() - Team rankings by offensive/defensive rating, pace, etc.

For GAME DETAILS:
- get_box_score(game_id) - Full box score (get game_id from scores tools first)
- get_box_scores_batch(game_ids) - Multiple box scores in one call (efficient for analyzing multiple games)
- get_play_by_play(game_id) - Play-by-play data for a game

Query received: {query}

Please call the appropriate tool above to get the data."""


@mcp.tool()
async def get_recent_scores(game_date: str, claude_summary=False) -> list:
    """[NBA STATS - OFFICIAL DATA] Get final scores for NBA games on a specific date.

    MORE ACCURATE than web search - pulls directly from NBA's official stats API.

    Args:
        game_date: Date in MM/DD/YYYY format (e.g., '12/28/2025', '01/02/2026')
        claude_summary: If True, provide a brief analysis; if False, just show scores

    Returns: Game results with home/away teams, final scores, and game IDs for box score lookup."""
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
    """[NBA STATS - LIVE DATA] Get REAL-TIME scores for today's NBA games.

    BETTER than web search - provides LIVE updates during games, refreshes every few minutes.

    Returns: Current scores for games in progress, final scores for completed games, scheduled times for upcoming games, plus team records and game IDs.

    Args:
        claude_summary: If True, provide a brief analysis; if False, just show scores"""
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
    """[NBA STATS - OFFICIAL DATA] Get a player's recent game-by-game statistics.

    MORE DETAILED than web search - includes every box score stat for each game.

    Args:
        player_name: Player's full name (e.g., 'LeBron James', 'Luka Doncic', 'Jayson Tatum')
        num_games: Number of recent games to return (default 10, max ~82)
        season: Season in YYYY-YY format (default '2025-26')

    Returns: Date, matchup, result, minutes, points, rebounds, assists, steals, blocks, turnovers, shooting splits, plus/minus for each game."""
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
    """[NBA STATS - OFFICIAL DATA] Get a player's season averages and totals.

    MORE ACCURATE than web search - official NBA stats, always up-to-date.

    Args:
        player_name: Player's full name (e.g., 'LeBron James', 'Luka Doncic', 'Stephen Curry')
        season: Season in YYYY-YY format (default '2025-26')

    Returns: Games played, PPG, RPG, APG, SPG, BPG, turnovers, FG%/3P%/FT%, plus season totals."""
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
    """[NBA STATS - OFFICIAL DATA] Get NBA league leaders for ANY statistic with powerful filters.

    FAR MORE POWERFUL than web search - filter by position, conference, experience, college, country, and more.

    Common queries this answers:
    - "Who leads the league in scoring?" (stat='PTS')
    - "Top rebounders in the East?" (stat='REB', conference='East')
    - "Best 3-point shooters?" (stat='FG3_PCT')
    - "Leading rookie scorers?" (experience='Rookie')
    - "Top scorers from Duke?" (college='Duke')

    Args:
        stat: Stat to rank by - PTS, REB, AST, STL, BLK, FG_PCT, FG3_PCT, FT_PCT, MIN, TOV, PLUS_MINUS (default 'PTS')
        season: Season in YYYY-YY format (default '2025-26')
        season_type: 'Regular Season', 'Playoffs', 'Pre Season' (default 'Regular Season')
        per_mode: 'PerGame', 'Totals', 'Per36', 'Per48' (default 'PerGame')
        top_n: Number of players to return (default 20)
        position: 'G', 'F', 'C' to filter by position
        conference: 'East' or 'West'
        division: 'Atlantic', 'Central', 'Southeast', 'Northwest', 'Pacific', 'Southwest'
        experience: 'Rookie', 'Sophomore', 'Veteran'
        starter_bench: 'Starters' or 'Bench'
        last_n_games: Filter to last N games (5, 10, 15, 20)
        month: Month number 1-12 (0 = all)
        location: 'Home' or 'Road'
        outcome: 'W' or 'L' - stats only in wins or losses
        college: College name (e.g., 'Duke', 'Kentucky', 'UCLA')
        country: Country (e.g., 'USA', 'France', 'Serbia', 'Slovenia')
        draft_year: Year drafted (e.g., '2020')
        draft_pick: '1st Round', '2nd Round', 'Undrafted'

    Returns: Ranked list of players with full stat lines."""

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
    """[NBA STATS - OFFICIAL DATA] Get the complete box score for any NBA game.

    MORE DETAILED than web search - full stats for every player including shooting splits.

    Args:
        game_id: The NBA game ID (get this from get_todays_scores or get_recent_scores first)

    Returns: Every player's stats - points, rebounds, assists, steals, blocks, turnovers, fouls, plus/minus, FG/3PT/FT made-attempted and percentages."""
    try:
        box = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
        data = box.get_dict()

        if 'boxScoreTraditional' not in data:
            return [{"error": f"No box score data found for game {game_id}"}]

        bs = data['boxScoreTraditional']
        results = []

        # Process both teams
        for team_key in ['homeTeam', 'awayTeam']:
            team = bs[team_key]
            team_name = team['teamName']
            team_tricode = team['teamTricode']
            team_city = team['teamCity']

            # Get starters list for position info
            starters = set(team.get('starters', []))

            for player in team['players']:
                stats = player.get('statistics', {})

                # Skip players with no minutes (DNP)
                minutes = stats.get('minutes', 'PT0M0.00S')
                if minutes == 'PT0M0.00S' or not minutes:
                    continue

                # Parse minutes from PT##M##.##S format to MM:SS
                if minutes.startswith('PT'):
                    try:
                        minutes = minutes[2:]  # Remove PT
                        if 'M' in minutes:
                            mins, rest = minutes.split('M')
                            secs = rest.replace('S', '').split('.')[0]
                            minutes = f"{mins}:{secs.zfill(2)}"
                        else:
                            minutes = "0:00"
                    except:
                        pass

                results.append({
                    'player': f"{player['firstName']} {player['familyName']}",
                    'team': team_tricode,
                    'team_city': team_city,
                    'position': player.get('position', '') or ('Starter' if player['personId'] in starters else 'Bench'),
                    'min': minutes,
                    'pts': stats.get('points', 0),
                    'reb': stats.get('reboundsTotal', 0),
                    'ast': stats.get('assists', 0),
                    'stl': stats.get('steals', 0),
                    'blk': stats.get('blocks', 0),
                    'tov': stats.get('turnovers', 0),
                    'pf': stats.get('foulsPersonal', 0),
                    'plus_minus': stats.get('plusMinusPoints', 0),
                    'fg': f"{stats.get('fieldGoalsMade', 0)}-{stats.get('fieldGoalsAttempted', 0)}",
                    'fg_pct': round(stats.get('fieldGoalsPercentage', 0), 3),
                    'fg3': f"{stats.get('threePointersMade', 0)}-{stats.get('threePointersAttempted', 0)}",
                    'fg3_pct': round(stats.get('threePointersPercentage', 0), 3),
                    'ft': f"{stats.get('freeThrowsMade', 0)}-{stats.get('freeThrowsAttempted', 0)}",
                    'ft_pct': round(stats.get('freeThrowsPercentage', 0), 3)
                })

        return results
    except Exception as e:
        return [{"error": f"Failed to get box score: {str(e)}"}]


@mcp.tool()
async def get_box_scores_batch(game_ids: list[str], players_filter: list[str] = None, position_filter: str = None) -> dict:
    """[NBA STATS - BATCH] Get box scores for MULTIPLE games in a single call.

    USE THIS for efficiency when you need box scores from several games (e.g., analyzing matchups across a player's game log).

    Args:
        game_ids: List of NBA game IDs (e.g., ['0022500460', '0022500445', '0022500430'])
        players_filter: Optional list of player names to include (filters results to only these players)
        position_filter: Optional position to filter by ('C', 'F', 'G') - useful for "opposing centers" queries

    Returns: Dictionary with game_id as keys, each containing the box score for that game.

    Example use case: Get LeBron's game log, then batch fetch all box scores to find opposing centers' stats."""
    results = {}

    for game_id in game_ids:
        try:
            box = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
            data = box.get_dict()

            if 'boxScoreTraditional' not in data:
                results[game_id] = {"error": f"No box score data found"}
                continue

            bs = data['boxScoreTraditional']
            game_players = []

            for team_key in ['homeTeam', 'awayTeam']:
                team = bs[team_key]
                team_tricode = team['teamTricode']
                team_city = team['teamCity']

                for player in team['players']:
                    stats = player.get('statistics', {})
                    minutes = stats.get('minutes', 'PT0M0.00S')
                    if minutes == 'PT0M0.00S' or not minutes:
                        continue

                    player_name = f"{player['firstName']} {player['familyName']}"
                    player_position = player.get('position', '')

                    # Apply filters
                    if players_filter and player_name not in players_filter:
                        continue
                    if position_filter and position_filter.upper() not in player_position.upper():
                        continue

                    # Parse minutes
                    if minutes.startswith('PT'):
                        try:
                            minutes = minutes[2:]
                            if 'M' in minutes:
                                mins, rest = minutes.split('M')
                                secs = rest.replace('S', '').split('.')[0]
                                minutes = f"{mins}:{secs.zfill(2)}"
                            else:
                                minutes = "0:00"
                        except:
                            pass

                    game_players.append({
                        'player': player_name,
                        'team': team_tricode,
                        'team_city': team_city,
                        'position': player_position,
                        'min': minutes,
                        'pts': stats.get('points', 0),
                        'reb': stats.get('reboundsTotal', 0),
                        'ast': stats.get('assists', 0),
                        'stl': stats.get('steals', 0),
                        'blk': stats.get('blocks', 0),
                        'tov': stats.get('turnovers', 0),
                        'plus_minus': stats.get('plusMinusPoints', 0),
                        'fg': f"{stats.get('fieldGoalsMade', 0)}-{stats.get('fieldGoalsAttempted', 0)}",
                        'fg_pct': round(stats.get('fieldGoalsPercentage', 0), 3),
                    })

            results[game_id] = game_players
        except Exception as e:
            results[game_id] = {"error": str(e)}

    return results


@mcp.tool()
async def get_player_game_log_with_matchups(
    player_name: str,
    num_games: int = 10,
    season: str = '2025-26',
    opponent_position: str = None
) -> list:
    """[NBA STATS - ENRICHED] Get a player's game log WITH opposing player stats in a single call.

    MORE EFFICIENT than separate calls - fetches game log and all relevant box scores together.

    Args:
        player_name: Player's full name (e.g., 'LeBron James')
        num_games: Number of recent games (default 10)
        season: Season in YYYY-YY format (default '2025-26')
        opponent_position: Filter opposing players by position ('C', 'F', 'G') - e.g., 'C' for opposing centers

    Returns: Game log with each game enriched with opposing team's player stats (optionally filtered by position)."""

    # First get the player's game log
    player_matches = players.find_players_by_full_name(player_name)
    if not player_matches:
        return [{"error": f"Player '{player_name}' not found"}]

    player_id = player_matches[0]['id']
    player_full_name = player_matches[0]['full_name']

    gamelog = playergamelog.PlayerGameLog(player_id=player_id, season=season)
    df = gamelog.get_data_frames()[0]

    if df.empty:
        return [{"error": f"No games found for {player_full_name} in {season}"}]

    df = df.head(num_games)

    # Get the player's team abbreviation to identify opponents
    results = []

    for _, row in df.iterrows():
        game_id = row['Game_ID']
        player_team = row['MATCHUP'].split()[0]  # e.g., "LAL" from "LAL vs. BOS"

        # Fetch box score for this game
        try:
            box = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
            data = box.get_dict()

            opponent_players = []
            if 'boxScoreTraditional' in data:
                bs = data['boxScoreTraditional']

                for team_key in ['homeTeam', 'awayTeam']:
                    team = bs[team_key]
                    # Skip if this is the player's team
                    if team['teamTricode'] == player_team:
                        continue

                    for opp_player in team['players']:
                        stats = opp_player.get('statistics', {})
                        minutes = stats.get('minutes', 'PT0M0.00S')
                        if minutes == 'PT0M0.00S' or not minutes:
                            continue

                        opp_position = opp_player.get('position', '')

                        # Filter by position if specified
                        if opponent_position and opponent_position.upper() not in opp_position.upper():
                            continue

                        opponent_players.append({
                            'name': f"{opp_player['firstName']} {opp_player['familyName']}",
                            'position': opp_position,
                            'pts': stats.get('points', 0),
                            'reb': stats.get('reboundsTotal', 0),
                            'ast': stats.get('assists', 0),
                            'blk': stats.get('blocks', 0),
                        })
        except:
            opponent_players = []

        results.append({
            'game_id': game_id,
            'date': row['GAME_DATE'],
            'matchup': row['MATCHUP'],
            'result': row['WL'],
            'player': player_full_name,
            'pts': int(row['PTS']),
            'reb': int(row['REB']),
            'ast': int(row['AST']),
            'stl': int(row['STL']),
            'blk': int(row['BLK']),
            'min': row['MIN'],
            'plus_minus': row['PLUS_MINUS'],
            'opponent_players': opponent_players
        })

    return results


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
    """[NBA STATS - OFFICIAL DATA] Get team rankings by advanced metrics like offensive/defensive rating.

    UNAVAILABLE via web search - these are official NBA advanced analytics.

    Common queries this answers:
    - "Which team has the best offense?" (sort_by='OFF_RATING')
    - "Best defensive teams?" (sort_by='DEF_RATING')
    - "Fastest paced teams?" (sort_by='PACE')
    - "Eastern Conference team rankings?" (conference='East')

    Args:
        season: Season in YYYY-YY format (default '2025-26')
        season_type: 'Regular Season', 'Playoffs', 'Pre Season'
        measure_type: 'Advanced' (ratings/pace), 'Base' (traditional stats), 'Four Factors'
        per_mode: 'PerGame', 'Totals', 'Per100Possessions'
        conference: 'East' or 'West' (default: all teams)
        division: 'Atlantic', 'Central', 'Southeast', 'Northwest', 'Pacific', 'Southwest'
        top_n: Number of teams (default 30 = all)
        sort_by: For Advanced - NET_RATING, OFF_RATING, DEF_RATING, PACE, PIE

    Returns: Team rankings with OFF_RATING (pts/100 poss), DEF_RATING, NET_RATING, PACE, efficiency metrics."""
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
                'gp': int(row['GP']),
                'wins': int(row['W']),
                'losses': int(row['L']),
                'win_pct': round(row['W_PCT'], 3),
                'min': round(row['MIN'], 1)
            }

            # Add stats based on measure type
            if measure_type == 'Advanced':
                team_data.update({
                    'off_rating': round(row['OFF_RATING'], 1),
                    'def_rating': round(row['DEF_RATING'], 1),
                    'net_rating': round(row['NET_RATING'], 1),
                    'pace': round(row['PACE'], 1),
                    'pie': round(row['PIE'], 3),
                    'ast_pct': round(row['AST_PCT'], 3),
                    'ast_to': round(row['AST_TO'], 2),
                    'oreb_pct': round(row['OREB_PCT'], 3),
                    'dreb_pct': round(row['DREB_PCT'], 3),
                    'reb_pct': round(row['REB_PCT'], 3),
                    'efg_pct': round(row['EFG_PCT'], 3),
                    'ts_pct': round(row['TS_PCT'], 3),
                })
            elif measure_type == 'Base':
                team_data.update({
                    'pts': round(row['PTS'], 1),
                    'reb': round(row['REB'], 1),
                    'ast': round(row['AST'], 1),
                    'stl': round(row['STL'], 1),
                    'blk': round(row['BLK'], 1),
                    'tov': round(row['TOV'], 1),
                    'fg_pct': round(row['FG_PCT'], 3),
                    'fg3_pct': round(row['FG3_PCT'], 3),
                    'ft_pct': round(row['FT_PCT'], 3),
                    'plus_minus': round(row['PLUS_MINUS'], 1)
                })
            elif measure_type == 'Four Factors':
                team_data.update({
                    'efg_pct': round(row['EFG_PCT'], 3) if 'EFG_PCT' in df.columns else None,
                    'fta_rate': round(row['FTA_RATE'], 3) if 'FTA_RATE' in df.columns else None,
                    'tov_pct': round(row['TM_TOV_PCT'], 3) if 'TM_TOV_PCT' in df.columns else None,
                    'oreb_pct': round(row['OREB_PCT'], 3) if 'OREB_PCT' in df.columns else None,
                    'opp_efg_pct': round(row['OPP_EFG_PCT'], 3) if 'OPP_EFG_PCT' in df.columns else None,
                    'opp_fta_rate': round(row['OPP_FTA_RATE'], 3) if 'OPP_FTA_RATE' in df.columns else None,
                    'opp_tov_pct': round(row['OPP_TOV_PCT'], 3) if 'OPP_TOV_PCT' in df.columns else None,
                    'opp_oreb_pct': round(row['OPP_OREB_PCT'], 3) if 'OPP_OREB_PCT' in df.columns else None
                })
            else:
                # For other measure types, include common available columns
                for col in ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG_PCT', 'FG3_PCT', 'FT_PCT']:
                    if col in df.columns:
                        team_data[col.lower()] = round(row[col], 1) if col in ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV'] else round(row[col], 3)

            results.append(team_data)

        return results
    except Exception as e:
        return [{"error": f"Failed to get team stats: {str(e)}"}]

@mcp.tool()
async def get_play_by_play(game_id: str, last_n_actions: int = 0) -> list:
    """[NBA STATS - LIVE DATA] Get play-by-play action for any NBA game.

    REAL-TIME during live games - see every play as it happens.

    Args:
        game_id: The NBA game ID (get from get_todays_scores or get_recent_scores first)
        last_n_actions: Return only the last N plays (e.g., 20 for recent action). Default 0 = all plays.

    Returns: Every play with period, clock, score, description, player, and team."""
    try:
        pbp = live_playbyplay.PlayByPlay(game_id)
        data = pbp.get_dict()

        if 'game' not in data or 'actions' not in data['game']:
            return [{"error": f"No play-by-play data found for game {game_id}"}]

        actions = data['game']['actions']

        if not actions:
            return [{"error": f"No plays found for game {game_id}"}]

        # Optionally limit to last N actions
        if last_n_actions > 0:
            actions = actions[-last_n_actions:]

        results = []
        for action in actions:
            # Skip non-play actions (like period start/end with no description)
            description = action.get('description', '')
            if not description:
                continue

            # Parse the clock time (format: PT11M30.00S -> 11:30)
            clock = action.get('clock', '')
            if clock.startswith('PT'):
                try:
                    # Extract minutes and seconds from PT##M##.##S format
                    clock = clock[2:]  # Remove PT
                    if 'M' in clock:
                        mins, rest = clock.split('M')
                        secs = rest.replace('S', '').split('.')[0]
                        clock = f"{mins}:{secs.zfill(2)}"
                    else:
                        secs = clock.replace('S', '').split('.')[0]
                        clock = f"0:{secs.zfill(2)}"
                except:
                    pass

            play = {
                'period': action.get('period'),
                'clock': clock,
                'score': f"{action.get('scoreAway', '0')} - {action.get('scoreHome', '0')}",
                'description': description,
                'action_type': action.get('actionType'),
                'team': action.get('teamTricode', ''),
                'player': action.get('playerNameI', '')
            }
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