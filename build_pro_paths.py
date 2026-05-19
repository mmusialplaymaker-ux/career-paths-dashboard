"""
build_pro_paths.py (v3)
───────────────────────
Buduje data/pro_paths.csv.

FIXY v3 vs v2:
  • debut_season_id liczone POPRAWNIE: pierwszy sezon w którym był mecz
    w lidze centralnej (E/1L/2L) z minutes>0 i is_keeper=false
  • years_before_debut liczymy względem POZYCJI sezonu w karierze,
    nie z (age_at_debut - age_in_season). Sezony są sortowane chronologicznie
    i numerowane: debut=0, sezon przed=1, dwa wcześniej=2 itd.
  • last_match_date per (player, season, league) — żeby później Python
    wiedział który klub był chronologicznie ostatni
  • debut_league_level (11/12/13) — jednoznacznie wiadomo co to za debiut

Wyjście (kolumny):
  player_id, player_name, age_at_debut, debut_season_id, debut_league_level,
  season_id, season_index (= years_before_debut), age_in_season,
  league_id, league_name, league_level, is_junior_league,
  club_id, club_name, team_id, team_name,
  total_minutes, matches_played, avg_score,
  pct_max_minutes, activity_status,
  first_match_date, last_match_date

Wymaga: config.py + .env
"""

import os
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import (
    CENTRAL_IN, CENTRAL_LEAGUES,
    TRACKED_LEAGUES_IN, LEAGUE_LEVEL_CASE,
    JUNIOR_IN, sql_in_clause,
)

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5433")
DB_NAME     = os.getenv("DB_NAME", "")
DB_USER     = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

OUTPUT_PATH = Path("data/pro_paths.csv")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
BATCH_SIZE = 500

if not all([DB_NAME, DB_USER, DB_PASSWORD]):
    raise SystemExit("BŁĄD: brakuje DB_NAME/DB_USER/DB_PASSWORD w .env")

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    connect_args={"connect_timeout": 30},
)

print("Łączenie z bazą...")
with engine.connect() as conn:
    conn.execute(text("SELECT 1"))
print("OK\n")

# ══════════════════════════════════════════════════════════════════════════════
# KROK 1: Lista pro-graczy + DEBIUT_SEASON_ID (pierwszy sezon w E/1L/2L)
# ══════════════════════════════════════════════════════════════════════════════

print("Krok 1: Lista pro-graczy + debut_season_id...")
q_debut = f"""
    WITH debut_meczes AS (
        SELECT
            m.player_id,
            m.season_id,
            m.match_date,
            sc.age,
            -- najwyższa liga centralna w której grał w tym meczu (wiele lig na mecz nie ma)
            CASE m.league_id
                WHEN '337bb869-0b42-484f-8eca-0c8842a13ec9' THEN 13
                WHEN '50e40483-e8dc-4e4b-9f58-a83f93a54d9a' THEN 12
                WHEN '5f26d625-e72e-4aa5-9ffe-451025c18e3a' THEN 11
            END AS league_level
        FROM pm_player_match_stats m
        JOIN pm_player_match_score sc
            ON m.match_id  = sc.match_id
           AND m.player_id = sc.player_id
        JOIN players p ON m.player_id = p._id
        WHERE m.league_id IN ({CENTRAL_IN})
          AND m.minutes > 0
          AND m.is_keeper = false
          AND p.is_keeper = false
    ),
    first_debut AS (
        SELECT DISTINCT ON (player_id)
            player_id,
            season_id      AS debut_season_id,
            match_date     AS debut_match_date,
            age            AS age_at_debut,
            league_level   AS debut_league_level
        FROM debut_meczes
        ORDER BY player_id, match_date ASC NULLS LAST
    )
    SELECT
        fd.player_id,
        p.firstname || ' ' || p.lastname AS player_name,
        fd.debut_season_id,
        fd.debut_match_date,
        fd.age_at_debut,
        fd.debut_league_level
    FROM first_debut fd
    JOIN players p ON fd.player_id = p._id
"""
with engine.connect() as conn:
    debuts = pd.read_sql(text(q_debut), conn)
print(f"  Znaleziono {len(debuts)} pro-graczy\n")

# ══════════════════════════════════════════════════════════════════════════════
# KROK 2: Max minut sezonu per liga
# ══════════════════════════════════════════════════════════════════════════════

print("Krok 2: Max minut sezonu per liga...")
q_max = f"""
    WITH per_player AS (
        SELECT player_id, league_id, season_id, SUM(minutes) AS total
        FROM pm_player_match_stats
        WHERE minutes > 0
          AND is_keeper = false
          AND league_id IN ({TRACKED_LEAGUES_IN})
        GROUP BY player_id, league_id, season_id
    )
    SELECT
        league_id,
        season_id,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total) AS max_minutes
    FROM per_player
    GROUP BY league_id, season_id
"""
with engine.connect() as conn:
    max_min = pd.read_sql(text(q_max), conn)
print(f"  {len(max_min)} rekordów (liga × sezon)\n")

# ══════════════════════════════════════════════════════════════════════════════
# KROK 3: Historia kariery — partiami
# ══════════════════════════════════════════════════════════════════════════════
# UWAGA: years_before_debut liczymy POŹNIEJ w Pythonie z chronologii sezonów
# (jeden sezon = jeden numer, nie wiele wierszy z tym samym numerem).

print(f"Krok 3: Historia kariery (partiami po {BATCH_SIZE})...")

LEVEL_CASE_H = LEAGUE_LEVEL_CASE.replace("m.league_id", "h.league_id")

player_ids    = debuts["player_id"].tolist()
all_history   = []
total_batches = (len(player_ids) + BATCH_SIZE - 1) // BATCH_SIZE

for i in range(0, len(player_ids), BATCH_SIZE):
    batch     = player_ids[i:i + BATCH_SIZE]
    batch_in  = sql_in_clause(batch)
    batch_num = i // BATCH_SIZE + 1

    q_history = f"""
        WITH history_agg AS (
            SELECT
                m.player_id,
                m.season_id,
                m.league_id,
                MAX(sc.age)                     AS age_in_season,
                SUM(m.minutes)                  AS total_minutes,
                COUNT(DISTINCT m.match_id)      AS matches_played,
                AVG(CASE WHEN sc.score = 'NaN'::double precision
                         THEN NULL ELSE sc.score END) AS avg_score,
                (ARRAY_AGG(m.club_id ORDER BY m.minutes DESC NULLS LAST))[1] AS dominant_club_id,
                (ARRAY_AGG(m.team_id ORDER BY m.minutes DESC NULLS LAST))[1] AS dominant_team_id,
                (ARRAY_AGG(m.club_id ORDER BY m.match_date DESC NULLS LAST))[1] AS last_club_id,
                (ARRAY_AGG(m.team_id ORDER BY m.match_date DESC NULLS LAST))[1] AS last_team_id,
                MIN(m.match_date) AS first_match_date,
                MAX(m.match_date) AS last_match_date
            FROM pm_player_match_stats m
            JOIN pm_player_match_score sc
                ON m.match_id  = sc.match_id
               AND m.player_id = sc.player_id
            WHERE m.player_id IN ({batch_in})
              AND m.minutes > 0
              AND m.is_keeper = false
              AND m.league_id IN ({TRACKED_LEAGUES_IN})
            GROUP BY m.player_id, m.season_id, m.league_id
        )
        SELECT
            h.player_id,
            h.season_id,
            h.age_in_season,
            h.league_id,
            l.name                                 AS league_name,
            {LEVEL_CASE_H}                         AS league_level,
            CASE WHEN h.league_id IN ({JUNIOR_IN}) THEN true ELSE false END AS is_junior_league,
            h.dominant_club_id                     AS club_id,
            c1.name                                AS club_name_dominant,
            h.dominant_team_id                     AS team_id,
            t1.name                                AS team_name_dominant,
            h.last_club_id,
            c2.name                                AS club_name_last,
            h.last_team_id,
            t2.name                                AS team_name_last,
            h.total_minutes,
            h.matches_played,
            ROUND(h.avg_score::numeric, 4)         AS avg_score,
            h.first_match_date,
            h.last_match_date
        FROM history_agg h
        JOIN leagues l ON h.league_id = l._id
        LEFT JOIN clubs c1 ON h.dominant_club_id = c1._id
        LEFT JOIN teams t1 ON h.dominant_team_id = t1._id
        LEFT JOIN clubs c2 ON h.last_club_id = c2._id
        LEFT JOIN teams t2 ON h.last_team_id = t2._id
        ORDER BY h.player_id, h.season_id, h.league_id
    """

    t0 = time.time()
    try:
        with engine.connect() as conn:
            batch_df = pd.read_sql(text(q_history), conn)
        all_history.append(batch_df)
        print(f"  Partia {batch_num}/{total_batches}: {len(batch_df):>5} wierszy  |  {time.time()-t0:5.1f}s")
    except Exception as e:
        print(f"  BŁĄD w partii {batch_num}: {e}")
        continue

# ══════════════════════════════════════════════════════════════════════════════
# KROK 4: Scalanie + DOROBIENIE years_before_debut w Pythonie + % max + activity
# ══════════════════════════════════════════════════════════════════════════════

print("\nKrok 4: Scalanie + years_before_debut + % max minut...")

if not all_history:
    raise SystemExit("BŁĄD: brak danych")

pro_paths = pd.concat(all_history, ignore_index=True)
pro_paths = pro_paths.merge(
    debuts, on="player_id", how="left",
)

# Dla każdego (player, season) → wyznacz porządek chronologiczny
# Sezony przed debiutem dostają years_before_debut=1,2,3..., debiut=0
# Sezony po debiucie dostają -1, -2... (ale i tak filtrujemy potem)

# Najpierw policz minimum first_match_date per (player, season)
season_dates = (
    pro_paths.groupby(["player_id", "season_id"], as_index=False)["first_match_date"]
    .min()
    .rename(columns={"first_match_date": "season_first_date"})
)

# Dołącz datę debiutu i posortuj sezony chronologicznie per player
season_dates = season_dates.merge(
    debuts[["player_id", "debut_season_id", "debut_match_date"]],
    on="player_id", how="left",
)
season_dates = season_dates.sort_values(
    ["player_id", "season_first_date"], ascending=[True, True]
).reset_index(drop=True)

# Indeks porządkowy: rosnący od najstarszego sezonu; debiut to indeks debiutowy
season_dates["chron_idx"] = season_dates.groupby("player_id").cumcount()

# Znajdź chron_idx sezonu debiutu per player
debut_idx = (
    season_dates[season_dates["season_id"] == season_dates["debut_season_id"]]
    [["player_id", "chron_idx"]]
    .rename(columns={"chron_idx": "debut_chron_idx"})
)
season_dates = season_dates.merge(debut_idx, on="player_id", how="left")

# years_before_debut = debut_chron_idx - chron_idx (debiut → 0, wcześniejsze → 1,2,3..)
season_dates["years_before_debut"] = (
    season_dates["debut_chron_idx"] - season_dates["chron_idx"]
)

# Dołącz do pro_paths
pro_paths = pro_paths.merge(
    season_dates[["player_id", "season_id", "years_before_debut"]],
    on=["player_id", "season_id"], how="left",
)

# Filtruj: tylko sezony przed debiutem (włącznie z sezonem debiutu)
# Bierzemy też debiutowy sezon, bo chcemy widzieć "co się wydarzyło w sezonie debiutu"
pro_paths = pro_paths[pro_paths["years_before_debut"].between(0, 10)].copy()

# % max minut + activity
pro_paths = pro_paths.merge(max_min, on=["league_id", "season_id"], how="left")
pro_paths["pct_max_minutes"] = (
    pro_paths["total_minutes"] / pro_paths["max_minutes"] * 100
).round(1).clip(0, 100)

def activity(pct):
    if pd.isna(pct):  return "nieznana"
    if pct >= 70:     return "podstawowy"
    if pct >= 40:     return "regularny"
    if pct >= 15:     return "rezerwowy"
    return "sporadyczny"

pro_paths["activity_status"] = pro_paths["pct_max_minutes"].apply(activity)

print(f"  Wierszy: {len(pro_paths)}")
print(f"  Pro-graczy: {pro_paths['player_id'].nunique()}")
print(f"  Sezonów per pro (mediana): {pro_paths.groupby('player_id')['season_id'].nunique().median():.0f}")
print(f"  Rozkład activity: {pro_paths['activity_status'].value_counts().to_dict()}")

# Wybierz finalny club_name/team_name: domyślnie 'last' (chronologicznie),
# ale jak NaN to fallback do 'dominant'
pro_paths["club_name"] = pro_paths["club_name_last"].fillna(pro_paths["club_name_dominant"])
pro_paths["team_name"] = pro_paths["team_name_last"].fillna(pro_paths["team_name_dominant"])

# ══════════════════════════════════════════════════════════════════════════════
# ZAPIS
# ══════════════════════════════════════════════════════════════════════════════

out_cols = [
    "player_id", "player_name", "age_at_debut",
    "debut_season_id", "debut_league_level",
    "season_id", "years_before_debut", "age_in_season",
    "league_id", "league_name", "league_level", "is_junior_league",
    "club_id", "club_name", "team_id", "team_name",
    "total_minutes", "matches_played", "avg_score",
    "pct_max_minutes", "activity_status",
    "first_match_date", "last_match_date",
]
out_cols = [c for c in out_cols if c in pro_paths.columns]
pro_paths[out_cols].to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

print(f"\nZapisano: {OUTPUT_PATH}")
print("Następnie: candidates.sql v4 (z match_date), potem python build_reports.py")
