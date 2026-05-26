"""
prepare_for_deploy.py
─────────────────────
Przygotowuje lekkie pliki do publikacji na Streamlit Cloud.

Bierze TOP N kandydatów (po Ocenie) z OBYDWU arkuszy:
  • "Ranking" (debiutanci)
  • "Powracający (1L-2L)"
plus ich pełne dane sezonowe z candidates.csv.

Wynik: data/candidates_deploy.csv + data/candidate_matches_deploy.xlsx
"""

from pathlib import Path
import pandas as pd

DATA_DIR = Path("data")

# Ile zawodników zachować w każdej kategorii
TOP_N = 10000           # debiutanci
TOP_N_RETURNING = 2000  # powracający (zwykle ich mniej)

SRC = DATA_DIR / "candidate_matches.xlsx"
RETURNING_SHEET = "Powracający (1L-2L)"

print(f"Wczytuję ranking i wybieram TOP {TOP_N}...")
ranking = pd.read_excel(SRC, sheet_name="Ranking")
ranking_top = ranking.sort_values("Ocena", ascending=False).head(TOP_N).copy()
top_names = set(ranking_top["Zawodnik"].dropna().unique())
print(f"  Debiutanci TOP {TOP_N}: {len(top_names)} zawodników")

# Arkusz powracających (jeśli istnieje)
returning_top = None
try:
    returning = pd.read_excel(SRC, sheet_name=RETURNING_SHEET)
    returning_top = returning.sort_values("Ocena", ascending=False).head(TOP_N_RETURNING).copy()
    top_names |= set(returning_top["Zawodnik"].dropna().unique())
    print(f"  Powracający TOP {TOP_N_RETURNING}: {len(returning_top)} zawodników")
except Exception as e:
    print(f"  (brak arkusza powracających: {e})")

# ── Lekki candidates.csv (oba zbiory) ─────────────────────────────────────────
print("\nFiltruję candidates.csv...")
candidates = pd.read_csv(DATA_DIR / "candidates.csv", encoding="utf-8-sig", dtype=str)
candidates_small = candidates[candidates["player_name"].isin(top_names)].copy()
out_cand = DATA_DIR / "candidates_deploy.csv"
candidates_small.to_csv(out_cand, index=False, encoding="utf-8-sig")
size_mb = out_cand.stat().st_size / 1024 / 1024
print(f"  Zapisano: {out_cand} ({size_mb:.1f} MB, {len(candidates_small)} wierszy)")

# ── Lekki candidate_matches_deploy.xlsx (oba arkusze) ─────────────────────────
print("\nTworzę lekki candidate_matches_deploy.xlsx...")
out_xlsx = DATA_DIR / "candidate_matches_deploy.xlsx"
with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
    ranking_top.to_excel(writer, sheet_name="Ranking", index=False)
    if returning_top is not None:
        returning_top.to_excel(writer, sheet_name=RETURNING_SHEET, index=False)
print(f"  Zapisano: {out_xlsx}")

size_xlsx = out_xlsx.stat().st_size / 1024 / 1024
print(f"\nGotowe. Rozmiary: candidates_deploy.csv {size_mb:.1f} MB, "
      f"candidate_matches_deploy.xlsx {size_xlsx:.1f} MB")
print("Streamlit będzie czytał '*_deploy' jeśli istnieją.")
if size_mb > 90:
    print("⚠ candidates_deploy.csv blisko limitu GitHub (100 MB) — rozważ niższy TOP_N")