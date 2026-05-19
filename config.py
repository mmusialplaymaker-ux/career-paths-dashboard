"""
config.py
─────────
Wspólne stałe dla całego pipeline'u. Jedno źródło prawdy:
  • Mapowanie league_id → level (1–13)
  • Lista lig "kraj/CLJ" (te liczą się do ścieżki kariery)
  • Lista 3 lig "centralnych" (Ekstraklasa, 1L, 2L) jako debiut pro
  • Helper funkcje do generowania SQL CASE WHEN

Zmieniasz tutaj — i SQL-e + Python automatycznie dostają nowe wartości
(o ile używasz helperów _sql_case_expr / _sql_in_clause).
"""

# ══════════════════════════════════════════════════════════════════════════════
# 3 LIGI CENTRALNE — debiut pro (Ekstraklasa + 1. Liga + 2. Liga)
# ══════════════════════════════════════════════════════════════════════════════

CENTRAL_LEAGUES = {
    '337bb869-0b42-484f-8eca-0c8842a13ec9': 13,  # Ekstraklasa
    '50e40483-e8dc-4e4b-9f58-a83f93a54d9a': 12,  # 1. Liga
    '5f26d625-e72e-4aa5-9ffe-451025c18e3a': 11,  # 2. Liga
}

# ══════════════════════════════════════════════════════════════════════════════
# PEŁNE MAPOWANIE league_id → POZIOM (1–13)
# ══════════════════════════════════════════════════════════════════════════════
# Skala: 13=Ekstraklasa, 12=1L, 11=2L, 10=3L, 9=4L/CLJ U-19, 8=5L/CLJ U-18,
#        7=Okręg/CLJ U-17, 6=A Klasa/A2, 5=B Klasa/A1/CLJ U-15, 4=C Klasa/B1/B2,
#        3=C1/C2, 2=D1/D2, 1=E1/E2
#
# Wartości juniorskie wyliczone z rank_p_ranked (uśrednione per league_id).
# Skala seniorska zgodna z user feedback (CLJ U-19 = 4. Liga itd.).

LEAGUE_LEVELS = {
    # ── SENIORSKIE ────────────────────────────────────────────────────────────
    '337bb869-0b42-484f-8eca-0c8842a13ec9': 13,  # Ekstraklasa
    '50e40483-e8dc-4e4b-9f58-a83f93a54d9a': 12,  # 1. Liga
    '5f26d625-e72e-4aa5-9ffe-451025c18e3a': 11,  # 2. Liga
    '5cc45e5f-744b-428c-b8af-cdefca38de29': 10,  # 3. Liga
    'c164ca31-22e4-43fc-9e30-4f3bcc2b7d72': 9,   # 4. Liga
    'a0583713-115c-4aa5-90f2-140f6eaece15': 8,   # 5. Liga
    'c5afdf4b-b449-4ef3-acf5-dded47fc5f58': 7,   # Klasa Okręgowa
    '63d04023-727a-4c0c-a8c6-4154fe1104b7': 6,   # Klasa A
    'b7d2c55b-e2af-44e2-9df2-3f6e05dc1768': 5,   # Klasa B
    '895016b3-4fa6-4a68-aa41-5035f9ebef8e': 4,   # Klasa C
    # ── JUNIORSKIE ────────────────────────────────────────────────────────────
    'bf74d613-4cc6-4115-ad03-fac139dee351': 9,   # CLJ U-19         = 4. Liga
    '8e70e715-3f0f-4481-a01d-51fb7b9aee90': 9,   # Liga Makro U-19  = 4. Liga
    '279a6c2b-0504-4be3-9386-3c1ca785d11d': 8,   # CLJ U-18         = 5. Liga
    '8104ee44-740c-4f6c-8fc3-3bbcf2b3b0e7': 7,   # CLJ U-17         = Okręg.
    '436dc4c6-bc94-4d30-ae92-1113d6d4eee3': 5,   # CLJ U-15         = Klasa B
    '5b788871-3d38-4073-9500-fcfa4d1b4270': 5,   # A1 junior        = Klasa B
    'f19d92f4-14f7-45ab-884f-90da0d03f4a0': 6,   # A2 junior        = Klasa A
    '823a45df-052b-4cd5-a060-32ed52921992': 4,   # B1 junior        = Klasa C
    '75b51f36-93fd-49cb-86d3-6086dc88081b': 4,   # B2 junior        = Klasa C
    '317d1eb3-4873-4749-91b5-edb2d0cd4375': 3,   # C1 junior
    'adf4ca7f-46ef-4aff-a7a0-3e7cc614c59d': 3,   # C2 junior
    '7c5a509a-2dac-46a7-9a37-54d48719758b': 2,   # D1 junior
    '9d41a9e1-aa66-4e2c-9f33-6f4b01139837': 2,   # D2 junior
    '811e1235-dc60-4db3-bf68-ee9b43d8370c': 1,   # E1 junior
    'bf404c9a-f13c-4835-885a-43ba3774850c': 1,   # E2 junior
}

# Ligi juniorskie (potrzebne by zaznaczyć is_junior w analizie)
JUNIOR_LEAGUES = {
    'bf74d613-4cc6-4115-ad03-fac139dee351',  # CLJ U-19
    '8e70e715-3f0f-4481-a01d-51fb7b9aee90',  # Liga Makro U-19
    '279a6c2b-0504-4be3-9386-3c1ca785d11d',  # CLJ U-18
    '8104ee44-740c-4f6c-8fc3-3bbcf2b3b0e7',  # CLJ U-17
    '436dc4c6-bc94-4d30-ae92-1113d6d4eee3',  # CLJ U-15
    '5b788871-3d38-4073-9500-fcfa4d1b4270',  # A1
    'f19d92f4-14f7-45ab-884f-90da0d03f4a0',  # A2
    '823a45df-052b-4cd5-a060-32ed52921992',  # B1
    '75b51f36-93fd-49cb-86d3-6086dc88081b',  # B2
    '317d1eb3-4873-4749-91b5-edb2d0cd4375',  # C1
    'adf4ca7f-46ef-4aff-a7a0-3e7cc614c59d',  # C2
    '7c5a509a-2dac-46a7-9a37-54d48719758b',  # D1
    '9d41a9e1-aa66-4e2c-9f33-6f4b01139837',  # D2
    '811e1235-dc60-4db3-bf68-ee9b43d8370c',  # E1
    'bf404c9a-f13c-4835-885a-43ba3774850c',  # E2
}

# Ligi seniorskie do filtra "current_level" (kandydaci ≥ Klasa C)
SENIOR_LEAGUES = {
    '337bb869-0b42-484f-8eca-0c8842a13ec9', '50e40483-e8dc-4e4b-9f58-a83f93a54d9a',
    '5f26d625-e72e-4aa5-9ffe-451025c18e3a', '5cc45e5f-744b-428c-b8af-cdefca38de29',
    'c164ca31-22e4-43fc-9e30-4f3bcc2b7d72', 'a0583713-115c-4aa5-90f2-140f6eaece15',
    'c5afdf4b-b449-4ef3-acf5-dded47fc5f58', '63d04023-727a-4c0c-a8c6-4154fe1104b7',
    'b7d2c55b-e2af-44e2-9df2-3f6e05dc1768', '895016b3-4fa6-4a68-aa41-5035f9ebef8e',
}

# Ligi kandydatów — wszystkie poniżej 1L u seniorów + juniorzy (do roli "candidate pool")
# Czyli: 3. Liga, 4. Liga, 5. Liga, Okręg, A, B, C + wszystkie juniorskie
CANDIDATE_LEAGUES = (SENIOR_LEAGUES - set(CENTRAL_LEAGUES.keys())) | JUNIOR_LEAGUES

# ══════════════════════════════════════════════════════════════════════════════
# CZYTELNE NAZWY POZIOMÓW (dla wyświetlania)
# ══════════════════════════════════════════════════════════════════════════════

LEVEL_NAMES = {
    13: "Ekstraklasa",
    12: "1. Liga",
    11: "2. Liga",
    10: "3. Liga",
    9:  "4. Liga / CLJ U-19",
    8:  "5. Liga / CLJ U-18",
    7:  "Okręgówka / CLJ U-17",
    6:  "Klasa A / A2",
    5:  "Klasa B / A1 / CLJ U-15",
    4:  "Klasa C / B1 / B2",
    3:  "C1 / C2",
    2:  "D1 / D2",
    1:  "E1 / E2",
}

# ══════════════════════════════════════════════════════════════════════════════
# SEZONY EKSTRAKLASY (do filtrowania top_score, candidates)
# ══════════════════════════════════════════════════════════════════════════════

RECENT_SEASONS = [
    'e9d66181-d03e-4bb3-b889-4da848f4831d',  # 25/26
    '4be7b40c-84ff-4e5a-96e5-875d7f13483a',  # 24/25
    '29d748c8-3e54-4a3d-8f94-368614f481a4',  # 23/24
    'b004c86c-3a95-47a7-b377-dde26bf2138b',  # 22/23
]
CURRENT_SEASON = 'e9d66181-d03e-4bb3-b889-4da848f4831d'

# ══════════════════════════════════════════════════════════════════════════════
# HELPERY DO GENEROWANIA SQL
# ══════════════════════════════════════════════════════════════════════════════

def sql_in_clause(uuids):
    """('uuid1','uuid2',...) — do wstrzyknięcia w IN()."""
    return ", ".join(f"'{u}'" for u in uuids)


def sql_case_expr(mapping, column="m.league_id"):
    """CASE WHEN ... THEN N ... ELSE NULL END z dict-a {uuid: level}."""
    whens = "\n        ".join(f"WHEN '{k}' THEN {v}" for k, v in mapping.items())
    return f"CASE {column}\n        {whens}\n        ELSE NULL\n    END"


CENTRAL_IN          = sql_in_clause(CENTRAL_LEAGUES.keys())
TRACKED_LEAGUES_IN  = sql_in_clause(LEAGUE_LEVELS.keys())   # wszystkie 26 lig które śledzimy
LEAGUE_LEVEL_CASE   = sql_case_expr(LEAGUE_LEVELS)
JUNIOR_IN           = sql_in_clause(JUNIOR_LEAGUES)
CANDIDATE_LEAGUES_IN = sql_in_clause(CANDIDATE_LEAGUES)


if __name__ == "__main__":
    # Quick sanity check
    print(f"3 ligi centralne:    {len(CENTRAL_LEAGUES)}")
    print(f"Wszystkie tracked:   {len(LEAGUE_LEVELS)}")
    print(f"Juniorskie:          {len(JUNIOR_LEAGUES)}")
    print(f"Seniorskie:          {len(SENIOR_LEAGUES)}")
    print(f"Kandydackie (pool):  {len(CANDIDATE_LEAGUES)}")
    print(f"\nPodgląd CASE expression:")
    print(LEAGUE_LEVEL_CASE)
