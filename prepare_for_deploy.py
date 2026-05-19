"""
prepare_for_deploy.py
─────────────────────
Przygotowuje lekkie pliki do publikacji na Streamlit Cloud.

Bierze TOP N kandydatów (po Ocenie) z candidate_matches.xlsx
i ich pełne dane sezonowe z candidates.csv.

Wynik: data/candidates_deploy.csv + data/candidate_matches_deploy.xlsx
"""

from pathlib import Path
import pandas as pd
from openpyxl import load_workbook

DATA_DIR = Path("data")

# Ile zawodników zachować w dashboardzie publikowanym
TOP_N = 20000

print(f"Wczytuję ranking i wybieram TOP {TOP_N}...")
ranking = pd.read_excel(DATA_DIR / "candidate_matches.xlsx", sheet_name="Ranking")
ranking_top = ranking.sort_values("Ocena", ascending=False).head(TOP_N).copy()
top_names = set(ranking_top["Zawodnik"].dropna().unique())
print(f"  TOP {TOP_N}: {len(top_names)} unikalnych zawodników")

# ── Lekki candidates.csv ──────────────────────────────────────────────────────
print("\nFiltruję candidates.csv...")
candidates = pd.read_csv(DATA_DIR / "candidates.csv", encoding="utf-8-sig", dtype=str)
candidates_small = candidates[candidates["player_name"].isin(top_names)].copy()

out_cand = DATA_DIR / "candidates_deploy.csv"
candidates_small.to_csv(out_cand, index=False, encoding="utf-8-sig")
size_mb = out_cand.stat().st_size / 1024 / 1024
print(f"  Zapisano: {out_cand} ({size_mb:.1f} MB, {len(candidates_small)} wierszy)")

# ── Lekki candidate_matches.xlsx (też tylko TOP N) ────────────────────────────
print("\nTworzę lekki candidate_matches_deploy.xlsx...")
src = load_workbook(DATA_DIR / "candidate_matches.xlsx")

# Arkusz Ranking — tylko TOP N
ranking_top.to_excel(DATA_DIR / "candidate_matches_deploy.xlsx",
                     sheet_name="Ranking", index=False)

# Top 100 szczegóły jest już mały (100 zawodników) — przepisz arkusz wprost
# (openpyxl to wymaga skomplikowanego kopiowania — pomijamy, dashboard używa
# Rankingu + pro_paths.csv do wykresów, więc Top 100 szczegóły jest opcjonalne)
print(f"  Zapisano: data/candidate_matches_deploy.xlsx")
print(f"\nGotowe. Streamlit będzie czytał '*_deploy' jeśli istnieją.")
print(f"Sprawdź rozmiary plików w data/ — wszystko powinno być < 25 MB.")
