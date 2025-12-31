from typing import Any
from mcp.server.fastmcp import FastMCP
from nba_api.stats.endpoints import scoreboardv2, boxscoretraditionalv2, boxscorefourfactorsv2, playbyplayv2, leaguegamefinder, playergamelog, playercareerstats, leaguedashplayerstats
from nba_api.stats.static import players
from nba_api.live.nba.endpoints import scoreboard as live_scoreboard
import pandas as pd

# Initialize FastMCP server
mcp = FastMCP("nba")
pd.set_option('display.max_rows', None)

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


@mcp.tool()
async def get_game_ids_tool() -> str:
    """Get the game IDs for all the games that happened yesterday."""
    return get_game_ids()

@mcp.tool()
async def get_game_scores(game_date=None, game_filter=None, claude_summary=False) -> list:
    """Get the score for a all games, that happened on a date, if no date is provided it gets the score of all games that happened yesterday.
    No matter how the date is provided claude must format it to be 'yyyy/mm/dd' when it passes it into get game ids. 
    It should be of the format Team 1: Score 1 - Team 2: Score 2. 
    It should take the team name and return the full name, for example if dict 1 item is Memphis it would be great if it could return Memphis Grizzlies
    It can take an optional game title, for example 'Memphis Grizzlies game' or 'lakers game', in which case it should only return the score for that game. 
    It can take an optional boolean, claude_summary, if this is false claude should only provide the scores and no other information, if it is true claude should give a little blurb."""
    game_scores = []
    for game_id in get_game_ids(game_date):
        game_scores.append(get_final_score(get_game_box_score(game_id)))

    return game_scores

@mcp.tool()
async def get_four_factors(game_filter=None, table_view=False, claude_summary=False) -> dict:
    """Get the score for all games that happened yesterday. 
    It should start with a bolded title of the two teams that played, for example Memphis Grizzles - Los Angles Lakers and then list the four factors underneath. 
    It can take an optional game title, for example 'Memphis Grizzlies game' or 'lakers game', in which case it should only return the four factors for that game.'
    It can take the option to display the data in a table view as well.
    It can take an optional boolean, claude_summary, if this is false claude should only provide the scores and no other information, if it is true claude should give a little blurb."""
    game_ids = get_game_ids()
    four_factors = []

    for game_id in game_ids:
        game = boxscorefourfactorsv2.BoxScoreFourFactorsV2(game_id=game_id).get_dict()['resultSets'][1]
        dataframe = pd.DataFrame(game['rowSet'], columns = game['headers'])
        filtered_dictionary = {}
        for index, row in dataframe.iterrows():
            filtered_dictionary[row['TEAM_ABBREVIATION']] = [row['EFG_PCT'], row['FTA_RATE'], row['TM_TOV_PCT'], row['OREB_PCT']]
        four_factors.append(filtered_dictionary)

    return four_factors

@mcp.tool()
async def get_pra_breakdown(game_date=None, game_filter=None, table_view=False, claude_summary=False) -> list:
    """Get the points rebounds and assists for all players that played in all games that happened yesterday. 
    It should start with a bolded title of the two teams that played, for example Memphis Grizzles - Los Angles Lakers and then list the four factors underneath. 
    It can take an optional game title, for example 'Memphis Grizzlies game' or 'lakers game', in which case it should only return the four factors for that game.'
    It can take the option to display the data in a table view as well, if it is a table view it should be two tables, one for each team.
    It can take an optional game date, which would be the day the games happened on. If it is not provided then we will fetch yesterdays games. No matter how the date is provided claude must format it to be 'yyyy/mm/dd' when it passes it into get game ids. 
    It can take an optional boolean, claude_summary, if this is false claude should only provide the scores and no other information, if it is true claude should give a little blurb."""
    games = []
    for game_id in get_game_ids(game_date):
        game = filter_to_pra_columns(get_game_box_score(game_id)).to_csv()
        games.append(game)

    return games

@mcp.tool()
async def get_full_breakdown(game_date=None, game_filter=None, table_view=False, claude_summary=False) -> list:
    """Returns the points rebounds, assists steals, blocks, plus minus, turn overs, personal fouls played for all players that played in all games that happened yesterday. 
    It should start with a bolded title of the two teams that played, for example Memphis Grizzles - Los Angles Lakers and then list the four factors underneath. 
    It can take an optional game title, for example 'Memphis Grizzlies game' or 'lakers game', in which case it should only return the four factors for that game.'
    It can take the option to display the data in a table view as well - defaults as False, if it is a table view it should be two tables, one for each team.
    It can take an optional boolean, claude_summary - DEFAULTS TO False, if this is false claude should only provide the scores and no other information, no notes or anything, if it is true claude should give a little blurb.
    It can take an optional game date, which would be the day the games happened on. If it is not provided then we will fetch yesterdays games. No matter how the date is provided claude must format it to be 'yyyy/mm/dd' when it passes it into get game ids. 
    """
    games = []
    for game_id in get_game_ids(game_date):
        game = filter_to_full_columns(get_game_box_score(game_id)).to_csv()
        games.append(game)

    return games

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

#This is still a WIP
@mcp.tool()
async def get_play_by_play(game_id: str) -> list:
    "Returns the play by play data from a game, Claude should serve this an easy to read format but it should serve the full data, it should not shorten it in any way"
    pbp = get_play_by_play_data(game_id)
    return pbp.to_csv()


if __name__ == "__main__":
    import os
    # Use HTTP transport for remote deployment, stdio for local
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "http":
        # Remote server mode
        port = int(os.getenv("PORT", 8080))
        print(f"Starting NBA MCP server on port {port}...")
        mcp.run(
            transport="streamable-http",
            host="0.0.0.0",
            port=port
        )
    else:
        # Local mode (default)
        mcp.run(transport='stdio')