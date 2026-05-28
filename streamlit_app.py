"""
streamlit_app.py (v2)
─────────────────────
Dashboard do interaktywnego porównania kandydatów i pro-graczy.

FIXY vs v1:
  • KeyError: 'Match score' → kolumna nazywa się teraz 'Score'
  • Strona "Szczegóły kandydata" PRZEBUDOWANA:
      - Karta 4-kolumnowa: kandydat + 3 pro bok-w-bok
      - Wykres trajektorii (poziom ligi) sezon po sezonie
      - Wykres minut sezon po sezonie
      - Wykres score sezon po sezonie
      - Tabela rozbicia % zgodności per match
      - Drill-down: pełna historia każdego z 3 pro

Uruchom:
    pip install streamlit plotly openpyxl
    streamlit run streamlit_app.py
"""

from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

DATA_DIR = Path("data")

st.set_page_config(page_title="Career Paths", layout="wide")


# ══════════════════════════════════════════════════════════════════════════════
# WCZYTAJ DANE (cached)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data
def load_data():
    """Preferuj wersje '_deploy' (mniejsze) dla publikacji na Streamlit Cloud."""
    cand_path = DATA_DIR / "candidate_matches_deploy.xlsx"
    if not cand_path.exists():
        cand_path = DATA_DIR / "candidate_matches.xlsx"
    cand_ranking = pd.read_excel(cand_path, sheet_name="Ranking")
    # Arkusz powracających (opcjonalny — może nie istnieć w starych plikach)
    try:
        returning = pd.read_excel(cand_path, sheet_name="Powracający (1L-2L)")
    except Exception:
        returning = None
    # Arkusz składowych oceny (do bar chartu w Dashboard i Szczegóły)
    try:
        drivers = pd.read_excel(cand_path, sheet_name="Składowe oceny")
    except Exception:
        drivers = None
    pro_debut = pd.read_excel(DATA_DIR / "pro_career_paths.xlsx", sheet_name="Pro debiut")
    pro_detail = pd.read_excel(DATA_DIR / "pro_career_paths.xlsx", sheet_name="Detale")
    return cand_ranking, returning, drivers, pro_debut, pro_detail


@st.cache_data
def load_pro_paths_raw():
    """Surowy pro_paths.csv żeby mieć dane sezonowe dla wykresów."""
    df = pd.read_csv(DATA_DIR / "pro_paths.csv", encoding="utf-8-sig")
    return df


@st.cache_data
def load_candidates_raw():
    """Surowy candidates.csv żeby mieć dane sezonowe.
    
    Preferuj wersję 'deploy' (mniejsza) jeśli istnieje — używana przy
    publikacji na Streamlit Cloud gdzie 138 MB candidates.csv nie wchodzi
    na GitHub (limit 100 MB)."""
    deploy_path = DATA_DIR / "candidates_deploy.csv"
    full_path = DATA_DIR / "candidates.csv"
    path = deploy_path if deploy_path.exists() else full_path
    df = pd.read_csv(path, encoding="utf-8-sig")
    return df


try:
    cand_ranking, returning, drivers, pro_debut, pro_detail = load_data()
    pro_paths_raw = load_pro_paths_raw()
    candidates_raw = load_candidates_raw()
except FileNotFoundError as e:
    st.error(f"Brakuje pliku: {e}. Uruchom najpierw `python build_reports.py`.")
    st.stop()


# Mapowanie poziomu → nazwa (dla wykresów)
LEVEL_NAMES = {
    13: "Ekstraklasa", 12: "1. Liga", 11: "2. Liga", 10: "3. Liga",
    9: "4. Liga / CLJ U-19", 8: "5. Liga / CLJ U-18",
    7: "Okręg / CLJ U-17", 6: "Klasa A / A2", 5: "Klasa B / A1 / CLJ U-15",
    4: "Klasa C / B1/B2", 3: "C1/C2", 2: "D1/D2", 1: "E1/E2",
}


def lvl_name(n):
    if pd.isna(n):
        return "—"
    return LEVEL_NAMES.get(int(n), f"poziom {int(n)}")


def calibrated_probability(ocena):
    """Szacowana szansa debiutu (%) — z backtestu 21/22, 22/23, 23/24."""
    if ocena >= 85:  return 18.9
    if ocena >= 80:  return 3.5
    if ocena >= 75:  return 3.1
    if ocena >= 70:  return 1.5
    if ocena >= 60:  return 0.7
    return 0.4


def auto_summary(cand_row, main_pro_name=None, pct_total=None, traj_df=None):
    """
    Wygeneruj 3-zdaniowe podsumowanie zawodnika z danych.
    cand_row: wiersz z cand_ranking (Series)
    main_pro_name: nazwa głównego match'a (string)
    pct_total: % zgodności z głównym match'em
    traj_df: DataFrame z trajektorią (kolumny: age_in_season, level, leagues)
    """
    name = cand_row["Zawodnik"]
    wiek = int(cand_row["Wiek"])
    poziom = cand_row["Obecny poziom"]
    klub = cand_row["Klub"]
    szansa = calibrated_probability(cand_row["Ocena"])

    # Zdanie 1: kim jest
    s1 = f"**{name}**, {wiek} lat, gra w {klub} ({poziom})."

    # Zdanie 2: dynamika rozwoju z trajektorii
    s2 = None
    if traj_df is not None and len(traj_df) >= 2:
        t = traj_df.sort_values("age_in_season").reset_index(drop=True)
        first = t.iloc[0]
        last = t.iloc[-1]
        diff = int(last["level"] - first["level"])
        n_seasons = len(t)
        if diff >= 3:
            s2 = (f"Skok o **{diff} poziomy** w ostatnich {n_seasons} sezonach "
                  f"(wiek {int(first['age_in_season'])} → {int(last['age_in_season'])}).")
        elif diff >= 1:
            s2 = (f"Wzrost o {diff} poziom(y) w ostatnich {n_seasons} sezonach "
                  f"(stabilna progresja).")
        elif diff == 0:
            s2 = f"Stabilny poziom przez ostatnie {n_seasons} sezony."
        else:
            s2 = f"Spadek o {abs(diff)} poziom(y) — wymaga uwagi."

    # Zdanie 3: match z pro + szansa
    s3_parts = []
    if main_pro_name and pd.notna(main_pro_name) and main_pro_name != "—":
        if pct_total is not None and pd.notna(pct_total):
            try:
                pct_val = float(str(pct_total).replace(",", "."))
                s3_parts.append(f"Ścieżka **{pct_val:.0f}% zgodna** z {main_pro_name}")
            except (ValueError, TypeError):
                s3_parts.append(f"Najbliższa ścieżka: {main_pro_name}")
        else:
            s3_parts.append(f"Najbliższa ścieżka: {main_pro_name}")
    s3_parts.append(f"szacowana szansa na centralny **~{szansa}%**")
    s3 = ". ".join(s3_parts) + "."

    return " ".join(filter(None, [s1, s2, s3]))


def driver_components(zawodnik_name, drivers_df):
    """
    Zwróć słownik składowych oceny z arkusza 'Składowe oceny'.
    Jeśli arkusz nie ma zawodnika → None (dashboard pokaże fallback).
    """
    if drivers_df is None:
        return None
    row = drivers_df[drivers_df["Zawodnik"] == zawodnik_name]
    if len(row) == 0:
        return None
    r = row.iloc[0]
    return {
        "Poziom (25%)":      float(r["Poziom"]),
        "Minuty (20%)":      float(r["Minuty"]),
        "Score (15%)":       float(r["Score"]),
        "Aktywność (15%)":   float(r["Aktywność"]),
        "Trajektoria (25%)": float(r["Trajektoria"]),
    }


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

st.sidebar.title("⚽ Career Paths")
page = st.sidebar.radio(
    "Strona",
    ["🏠 Dashboard", "📊 Ranking kandydatów", "🔍 Szczegóły kandydata",
     "📚 Encyklopedia pro", "✅ Walidacja modelu"],
)
st.sidebar.divider()
st.sidebar.caption(f"Kandydaci: {len(cand_ranking)}")
st.sidebar.caption(f"Pro-gracze: {len(pro_debut)}")

with st.sidebar.expander("ℹ️ Jak to działa"):
    st.markdown("""
**Cel:** identyfikacja kandydatów na poziom centralny (Ekstraklasa / 1L / 2L) 
przez porównanie ich ścieżki kariery do zawodników którzy już to osiągnęli.

**Skala lig (1–13):**
13 = Ekstraklasa · 12 = 1. Liga · 11 = 2. Liga · 10 = 3. Liga · 
9 = 4. Liga / CLJ U-19 · 8 = 5. Liga / CLJ U-18 · 7 = Okręg / CLJ U-17 · 
6 = Kl. A / A2 · 5 = Kl. B / A1 / CLJ U-15 · 4 = Kl. C / B1 / B2 · 
3 = C1/C2 · 2 = D1/D2 · 1 = E1/E2

**Aktywność:** wyliczana z % maks. minut sezonu w danej lidze (P95):
podstawowy (≥70%) · regularny (40–70%) · rezerwowy (15–40%) · sporadyczny (<15%)

**Matching (kandydat → pro):** porównanie *wiek-do-wieku* na 4 ostatnich sezonach.
Dla każdej trójki (poziom, minuty, score) liczymy procent zgodności:
- **% level** — różnica poziomów lig (max 13)
- **% min** — różnica minut (cap 2000/sezon)
- **% score** — różnica match score (cap 0.7)
- **% total** — średnia z powyższych

**Pula referencyjna:** TOP-1000 pro-graczy wg `overall_score` z 4 ostatnich 
sezonów Ekstraklasy, z minimum 3 sezonami historii przed debiutem.

**Filtry kandydatów:** wiek 15–26, ≥600 min w sezonie 25/26, w pulu kandydackiej
(3. Liga → Klasa C u seniorów + CLJ/A1/A2/B1/B2 u juniorów).

**Ocena (0–100):** ważona kombinacja obecnego poziomu (25%), minut (20%), score (15%),
aktywności (15%) i jakości matcha z pro (25%).
    """)


# ══════════════════════════════════════════════════════════════════════════════
# STRONA 0: DASHBOARD — pierwsza co skaut widzi
# ══════════════════════════════════════════════════════════════════════════════

if page == "🏠 Dashboard":
    st.title("Dashboard — przegląd")

    # ── Kluczowe metryki ──────────────────────────────────────────────────────
    n_total = len(cand_ranking)
    n_wyj = (cand_ranking["Status"] == "★★★ Wyjątkowy").sum()
    n_wys = (cand_ranking["Status"] == "★★ Wysoki").sum()
    n_obi = (cand_ranking["Status"] == "★ Obiecujący").sum()
    avg_szansa_top10 = cand_ranking.sort_values("Ocena", ascending=False).head(10)
    avg_szansa_top10 = avg_szansa_top10["Szansa %"].str.replace("~","").str.replace("%","").astype(float).mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Wyjątkowi", n_wyj, help="Ocena ≥ 85, szansa ~18.9%")
    c2.metric("Wysocy", n_wys, help="Ocena 80–85, szansa ~3.5%")
    c3.metric("Obiecujący", n_obi, help="Ocena 75–80, szansa ~3.1%")
    c4.metric("Średnia szansa TOP10", f"{avg_szansa_top10:.1f}%")

    st.divider()

    # ── TOP 3 zawodników do obejrzenia ────────────────────────────────────────
    st.subheader("🎯 Top 3 do obejrzenia w tym tygodniu")
    st.caption("Najwyżej ocenieni kandydaci — czysta czołówka. Kliknij szczegóły poniżej żeby zobaczyć ścieżkę.")

    top3 = cand_ranking.sort_values("Ocena", ascending=False).head(3)
    cols = st.columns(3)
    medals = ["🥇", "🥈", "🥉"]

    for i, (col, (_, r)) in enumerate(zip(cols, top3.iterrows())):
        with col:
            st.markdown(f"### {medals[i]} {r['Zawodnik']}")
            st.markdown(f"**{int(r['Wiek'])} lat** · {r['Obecny poziom']}")
            st.markdown(f"*{r['Klub']}*")
            # Wyróżnik: szansa jako duży zielony box
            szansa_val = float(str(r['Szansa %']).replace("~","").replace("%",""))
            if szansa_val >= 10:
                st.success(f"**Szansa: {r['Szansa %']}**  \n{r['Status']}")
            elif szansa_val >= 3:
                st.info(f"**Szansa: {r['Szansa %']}**  \n{r['Status']}")
            else:
                st.warning(f"**Szansa: {r['Szansa %']}**  \n{r['Status']}")
            # Mini info
            st.caption(f"Minuty: {int(r['Minuty'])} · Mecze: {int(r['Mecze'])} · Score: {r['Score']:.3f}")
            st.caption(f"Match: {r['Match #1 (główny)']} (% total: {r.get('% total', '—')})")

    st.divider()

    # ── Tabela "Awansowali" / top czołówka rankingu ───────────────────────────
    st.subheader("📈 Top 20 ze statusem Wyjątkowy / Wysoki")
    wyjatkowi_top = cand_ranking[cand_ranking["Status"].isin(["★★★ Wyjątkowy", "★★ Wysoki"])]\
                    .sort_values("Ocena", ascending=False).head(20)
    show_cols = ["#", "Zawodnik", "Wiek", "Klub", "Obecny poziom",
                 "Ocena", "Status", "Szansa %", "Match #1 (główny)", "% total"]
    show_cols = [c for c in show_cols if c in wyjatkowi_top.columns]
    st.dataframe(wyjatkowi_top[show_cols], width="stretch", hide_index=True)

    st.divider()

    # ── Rozkład statusów ──────────────────────────────────────────────────────
    st.subheader("📊 Rozkład statusów wśród wszystkich kandydatów")
    status_counts = cand_ranking["Status"].value_counts()
    # Posortuj wg hierarchii statusów
    status_order = ["★★★ Wyjątkowy", "★★ Wysoki", "★ Obiecujący", "Obserwacja", "Tło"]
    status_counts = status_counts.reindex([s for s in status_order if s in status_counts.index])

    colors_map = {"★★★ Wyjątkowy": "#2ECC71", "★★ Wysoki": "#3498DB",
                  "★ Obiecujący": "#F39C12", "Obserwacja": "#95A5A6", "Tło": "#BDC3C7"}
    colors_list = [colors_map.get(s, "#BDC3C7") for s in status_counts.index]

    fig = go.Figure(go.Bar(
        x=status_counts.values,
        y=status_counts.index,
        orientation="h",
        marker=dict(color=colors_list),
        text=status_counts.values,
        textposition="outside",
    ))
    fig.update_layout(
        height=300,
        xaxis_title="Liczba kandydatów",
        margin=dict(l=120, r=40, t=20, b=30),
        showlegend=False,
    )
    st.plotly_chart(fig, width="stretch")

    st.info("💡 **Wskazówka:** ranking jest długi, ale realna wartość to ~67 Wyjątkowych "
            "i ~293 Wysokich. Skup się na tej grupie, reszta to bazowy szum.")


# ══════════════════════════════════════════════════════════════════════════════
# STRONA 1: RANKING
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📊 Ranking kandydatów":
    st.title("Ranking kandydatów")

    # Przełącznik kategorii
    if returning is not None and len(returning) > 0:
        kategoria = st.radio(
            "Kategoria:",
            ["🌱 Debiutanci (nigdy nie grali w E/1L/2L)",
             f"🔄 Powracający (byli już w 1L/2L) — {len(returning)}"],
            horizontal=True,
        )
        source_df = cand_ranking if kategoria.startswith("🌱") else returning
        if kategoria.startswith("🔄"):
            st.info("To zawodnicy którzy **już grali** w 1./2. lidze, dziś są niżej. "
                    "To nie są prognozy pierwszego debiutu — to potencjalne powroty.")
    else:
        source_df = cand_ranking

    # Filtry
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        age_range = st.slider("Wiek", 15, 26, (15, 26))
    with c2:
        min_ocena = st.slider("Min. ocena", 0, 100, 50)
    with c3:
        levels = sorted(source_df["Obecny poziom"].dropna().unique().tolist())
        sel_levels = st.multiselect("Obecny poziom", levels, default=levels)
    with c4:
        activities = sorted(source_df["Aktywność"].dropna().unique().tolist())
        sel_act = st.multiselect("Aktywność", activities, default=activities)

    df = source_df[
        (source_df["Wiek"] >= age_range[0]) &
        (source_df["Wiek"] <= age_range[1]) &
        (source_df["Ocena"] >= min_ocena) &
        (source_df["Obecny poziom"].isin(sel_levels)) &
        (source_df["Aktywność"].isin(sel_act))
    ].copy()

    st.caption(f"Po filtrach: **{len(df)} kandydatów**")

    # Pokaż tylko kluczowe kolumny + % total (resztę da się zobaczyć w xlsx)
    show_cols = [
        "#", "Zawodnik", "Klub", "Wiek", "Obecny poziom",
        "Minuty", "Mecze", "Score", "Aktywność",
        "Ocena", "Status", "Szansa %",
        "Match #1 (główny)", "% level", "% min", "% score", "% total",
        "Match #2 (backup)", "Match #3 (backup)",
    ]
    show_cols = [c for c in show_cols if c in df.columns]
    st.dataframe(df[show_cols], width="stretch", hide_index=True)

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 Pobierz przefiltrowane jako CSV", csv,
                       file_name="kandydaci_filtered.csv", mime="text/csv")


# ══════════════════════════════════════════════════════════════════════════════
# STRONA 2: SZCZEGÓŁY KANDYDATA — przebudowane bok-w-bok + wykresy
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🔍 Szczegóły kandydata":
    st.title("Szczegóły kandydata vs pro-gracze")

    # ── Wybór kandydata ───────────────────────────────────────────────────────
    sort_by = st.radio("Sortuj listę po:", ["Oceniei (od najlepszej)", "% total (od najwyższego)", "Alfabetycznie"],
                       horizontal=True)
    sorted_ranking = cand_ranking.copy()
    if sort_by.startswith("Oceniei"):
        sorted_ranking = sorted_ranking.sort_values("Ocena", ascending=False)
    elif sort_by.startswith("% total"):
        # % total jest stringiem czasem ("—"), więc to_numeric
        sorted_ranking["_total_num"] = pd.to_numeric(sorted_ranking["% total"], errors="coerce")
        sorted_ranking = sorted_ranking.sort_values("_total_num", ascending=False, na_position="last")
    else:
        sorted_ranking = sorted_ranking.sort_values("Zawodnik")

    cand_names = sorted_ranking["Zawodnik"].tolist()
    selected = st.selectbox("Kandydat:", options=cand_names, index=0)
    cand = cand_ranking[cand_ranking["Zawodnik"] == selected].iloc[0]

    # Trajektoria kandydata — potrzebna do auto-summary i wykresów niżej
    def get_player_trajectory(df, player_name):
        """Zwraca DataFrame: age, level, minutes, score, leagues_str dla każdego sezonu."""
        p = df[df["player_name"] == player_name].copy()
        if len(p) == 0:
            return pd.DataFrame()
        p["league_label"] = p["league_name"] + " (" + p["total_minutes"].astype(int).astype(str) + " min)"
        agg = p.groupby(["season_id", "age_in_season"]).agg(
            level=("league_level", "max"),
            minutes=("total_minutes", "sum"),
            matches=("matches_played", "sum"),
            score=("avg_score", "mean"),
            leagues=("league_label", lambda s: " + ".join(sorted(s.unique()))),
        ).reset_index().sort_values("age_in_season")
        return agg

    cand_traj = get_player_trajectory(candidates_raw, selected)

    st.divider()

    # ── Panel 0: Auto-summary (3 zdania w nagłówku) ───────────────────────────
    main_name = cand.get("Match #1 (główny)")
    pct_total = cand.get("% total")
    summary_text = auto_summary(
        cand_row=cand,
        main_pro_name=main_name if pd.notna(main_name) and main_name != "—" else None,
        pct_total=pct_total,
        traj_df=cand_traj,
    )
    st.markdown(f"### {summary_text}")

    # ── Panel 0b: Bar chart "co napędza ocenę" ────────────────────────────────
    components = driver_components(selected, drivers)
    if components is not None:
        st.markdown("**Co napędza ocenę:**")
        comp_df = pd.DataFrame({
            "Składowa": list(components.keys()),
            "Wkład w ocenę": list(components.values()),
        })
        # Kolory: zielony dla dużych, czerwony dla małych
        max_possible = {"Poziom (25%)": 25, "Minuty (20%)": 20, "Score (15%)": 15,
                        "Aktywność (15%)": 15, "Trajektoria (25%)": 25}
        comp_df["pct_max"] = comp_df.apply(
            lambda r: r["Wkład w ocenę"] / max_possible[r["Składowa"]] * 100, axis=1
        )
        comp_df["color"] = comp_df["pct_max"].apply(
            lambda p: "#2ECC71" if p >= 60 else ("#F39C12" if p >= 35 else "#E74C3C")
        )

        fig_drv = go.Figure(go.Bar(
            x=comp_df["Wkład w ocenę"],
            y=comp_df["Składowa"],
            orientation="h",
            marker=dict(color=comp_df["color"]),
            text=[f"{v:.1f} pkt ({p:.0f}% max)" for v, p in zip(comp_df["Wkład w ocenę"], comp_df["pct_max"])],
            textposition="outside",
        ))
        fig_drv.update_layout(
            height=260,
            xaxis_title=f"Wkład w ocenę {cand['Ocena']:.1f}",
            margin=dict(l=130, r=120, t=10, b=30),
            showlegend=False,
        )
        st.plotly_chart(fig_drv, width="stretch")
        st.caption("🟢 ≥60% maksymalnego wkładu · 🟠 35–60% · 🔴 <35%. "
                   "Pokazuje DLACZEGO ten zawodnik dostał taką ocenę.")

    st.divider()

    # ── Panel 1: Karta 4 kolumn (kandydat + 3 pro) ────────────────────────────
    st.subheader("📋 Karta porównawcza")

    # Sprawdź czy są backupy
    b1_name = cand.get("Match #2 (backup)")
    b2_name = cand.get("Match #3 (backup)")

    # Helper: znajdź pro w pro_debut
    def find_pro(name):
        rows = pro_debut[pro_debut["Imię i nazwisko"] == name]
        if len(rows) == 0:
            return None
        return rows.iloc[0]

    main_pro = find_pro(main_name) if pd.notna(main_name) and main_name != "—" else None
    b1_pro = find_pro(b1_name) if pd.notna(b1_name) and b1_name != "—" else None
    b2_pro = find_pro(b2_name) if pd.notna(b2_name) and b2_name != "—" else None

    cols = st.columns(4)

    # KANDYDAT
    with cols[0]:
        st.markdown(f"### 🎯 {selected}")
        st.markdown(f"**Wiek:** {cand['Wiek']}")
        st.markdown(f"**Poziom:** {cand['Obecny poziom']}")
        st.markdown(f"**Klub:** {cand['Klub']}")
        st.markdown(f"**Minuty:** {cand['Minuty']}")
        st.markdown(f"**Mecze:** {cand['Mecze']}")
        st.markdown(f"**Aktywność:** {cand['Aktywność']}")
        st.markdown(f"**Score:** {cand['Score']}")
        st.markdown(f"**Ocena:** {cand['Ocena']} / 100")
        st.markdown(f"**Status:** {cand['Status']}")
        _szansa = calibrated_probability(cand["Ocena"])
        st.success(f"**Szacowana szansa na centralny: ~{_szansa}%**")

    def render_pro_card(col, pro_row, label, cand):
        with col:
            if pro_row is None:
                st.markdown(f"### {label}")
                st.info("Brak match'a")
                return
            st.markdown(f"### {label}")
            st.markdown(f"**{pro_row['Imię i nazwisko']}**")
            st.markdown(f"**Wiek debiutu:** {int(pro_row['Wiek debiutu'])}")
            st.markdown(f"**Liga debiutu:** {pro_row['Liga debiutu']}")
            st.markdown(f"**Klub debiutu:** {pro_row['Klub debiutu']}")
            st.markdown(f"**Liczba sezonów:** {int(pro_row['Liczba sezonów'])}")
            # Pokaż % zgodności tylko dla main (mamy je w cand)
            if label.startswith("🥇"):
                st.markdown("---")
                st.markdown(f"**% level:** {cand['% level']}")
                st.markdown(f"**% min:** {cand['% min']}")
                st.markdown(f"**% score:** {cand['% score']}")
                st.markdown(f"**% total:** {cand['% total']}")

    render_pro_card(cols[1], main_pro, "🥇 MAIN MATCH", cand)
    render_pro_card(cols[2], b1_pro, "🥈 BACKUP #1", cand)
    render_pro_card(cols[3], b2_pro, "🥉 BACKUP #2", cand)

    st.divider()

    # ── Panel 2-4: Wykresy ────────────────────────────────────────────────────
    st.subheader("📈 Trajektoria sezon po sezonie")

    # Trajektorie pro (cand_traj jest już policzona wyżej)
    main_traj = get_player_trajectory(pro_paths_raw, main_name) if main_pro is not None else pd.DataFrame()
    b1_traj = get_player_trajectory(pro_paths_raw, b1_name) if b1_pro is not None else pd.DataFrame()
    b2_traj = get_player_trajectory(pro_paths_raw, b2_name) if b2_pro is not None else pd.DataFrame()

    # ── WYKRES 1: Poziom ligi ─────────────────────────────────────────────────
    fig_level = go.Figure()

    def add_traj(fig, traj, name, color, yfield, hovertemplate=None):
        if len(traj) == 0:
            return
        fig.add_trace(go.Scatter(
            x=traj["age_in_season"],
            y=traj[yfield],
            mode="lines+markers",
            name=name,
            line=dict(color=color, width=3 if name.startswith("🎯") else 2),
            marker=dict(size=10 if name.startswith("🎯") else 8),
            customdata=traj[["leagues", "minutes", "matches", "score"]].values,
            hovertemplate=hovertemplate or (
                "<b>%{fullData.name}</b><br>" +
                "Wiek: %{x}<br>" +
                "Poziom: %{y}<br>" +
                "Liga: %{customdata[0]}<br>" +
                "Min: %{customdata[1]} | Mecze: %{customdata[2]}<br>" +
                "Score: %{customdata[3]:.3f}<extra></extra>"
            ),
        ))

    add_traj(fig_level, cand_traj, f"🎯 {selected} (kandydat)", "#FFA500", "level")
    if main_pro is not None:
        add_traj(fig_level, main_traj, f"🥇 {main_name}", "#1F77B4", "level")
        # Pionowa linia — wiek debiutu MAIN
        debut_age_main = int(main_pro["Wiek debiutu"])
        fig_level.add_vline(x=debut_age_main, line=dict(color="#1F77B4", dash="dash", width=1),
                            annotation_text=f"debiut {main_name.split()[0]}", annotation_position="top right")
    if b1_pro is not None:
        add_traj(fig_level, b1_traj, f"🥈 {b1_name}", "#7F7F7F", "level")
    if b2_pro is not None:
        add_traj(fig_level, b2_traj, f"🥉 {b2_name}", "#BCBD22", "level")

    fig_level.update_layout(
        title="Poziom ligi vs wiek",
        xaxis_title="Wiek (lat)",
        yaxis_title="Poziom ligi (1 = niski, 13 = Ekstraklasa)",
        yaxis=dict(range=[0, 14], tickmode="array",
                   tickvals=list(LEVEL_NAMES.keys()),
                   ticktext=[f"{v} {LEVEL_NAMES[v][:18]}" for v in LEVEL_NAMES]),
        hovermode="x unified",
        height=500,
    )
    st.plotly_chart(fig_level, width="stretch")

    # ── WYKRES 2: Minuty ──────────────────────────────────────────────────────
    fig_min = go.Figure()
    add_traj(fig_min, cand_traj, f"🎯 {selected}", "#FFA500", "minutes")
    if main_pro is not None:
        add_traj(fig_min, main_traj, f"🥇 {main_name}", "#1F77B4", "minutes")
    if b1_pro is not None:
        add_traj(fig_min, b1_traj, f"🥈 {b1_name}", "#7F7F7F", "minutes")
    if b2_pro is not None:
        add_traj(fig_min, b2_traj, f"🥉 {b2_name}", "#BCBD22", "minutes")
    fig_min.update_layout(
        title="Minuty rozegrane w sezonie",
        xaxis_title="Wiek (lat)",
        yaxis_title="Minuty",
        hovermode="x unified",
        height=400,
    )
    st.plotly_chart(fig_min, width="stretch")

    # ── WYKRES 3: Score ───────────────────────────────────────────────────────
    fig_score = go.Figure()
    add_traj(fig_score, cand_traj, f"🎯 {selected}", "#FFA500", "score")
    if main_pro is not None:
        add_traj(fig_score, main_traj, f"🥇 {main_name}", "#1F77B4", "score")
    if b1_pro is not None:
        add_traj(fig_score, b1_traj, f"🥈 {b1_name}", "#7F7F7F", "score")
    if b2_pro is not None:
        add_traj(fig_score, b2_traj, f"🥉 {b2_name}", "#BCBD22", "score")
    fig_score.update_layout(
        title="Average match score",
        xaxis_title="Wiek (lat)",
        yaxis_title="Score",
        hovermode="x unified",
        height=400,
    )
    st.plotly_chart(fig_score, width="stretch")

    st.divider()

    # ── Panel 5: Tabele sezon-po-sezonie ──────────────────────────────────────
    st.subheader("📋 Pełne dane sezonowe")
    tabs = st.tabs([f"🎯 {selected} (kandydat)"] +
                   ([f"🥇 {main_name}"] if main_pro is not None else []) +
                   ([f"🥈 {b1_name}"] if b1_pro is not None else []) +
                   ([f"🥉 {b2_name}"] if b2_pro is not None else []))

    def show_traj_table(tab, traj, who):
        with tab:
            if len(traj) == 0:
                st.info(f"Brak danych dla {who}")
                return
            display = traj.copy()
            display["level_name"] = display["level"].apply(lvl_name)
            display = display[["age_in_season", "level_name", "leagues",
                              "minutes", "matches", "score"]]
            display.columns = ["Wiek", "Poziom", "Liga(i)", "Min", "Mecze", "Score"]
            display["Score"] = display["Score"].round(3)
            st.dataframe(display, width="stretch", hide_index=True)

    show_traj_table(tabs[0], cand_traj, selected)
    next_tab = 1
    if main_pro is not None:
        show_traj_table(tabs[next_tab], main_traj, main_name)
        next_tab += 1
    if b1_pro is not None:
        show_traj_table(tabs[next_tab], b1_traj, b1_name)
        next_tab += 1
    if b2_pro is not None:
        show_traj_table(tabs[next_tab], b2_traj, b2_name)


# ══════════════════════════════════════════════════════════════════════════════
# STRONA 3: ENCYKLOPEDIA PRO — uproszczona
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📚 Encyklopedia pro":
    st.title("Encyklopedia pro-graczy")
    st.caption("Wszyscy zawodnicy z debiutem w Ekstraklasie / 1. Lidze / 2. Lidze (≥3 sezony historii)")

    # Filtry
    c1, c2, c3 = st.columns(3)
    with c1:
        age_d = st.slider("Wiek debiutu", 15, 30, (15, 25))
    with c2:
        leagues_d = sorted(pro_debut["Liga debiutu"].dropna().unique().tolist())
        sel_leagues = st.multiselect("Liga debiutu", leagues_d, default=leagues_d)
    with c3:
        min_seasons = st.slider("Min. sezonów historii", 3, 8, 3)

    search = st.text_input("Szukaj (zawodnik lub klub)", "")

    df = pro_debut[
        (pro_debut["Wiek debiutu"] >= age_d[0]) &
        (pro_debut["Wiek debiutu"] <= age_d[1]) &
        (pro_debut["Liga debiutu"].isin(sel_leagues)) &
        (pro_debut["Liczba sezonów"] >= min_seasons)
    ].copy()
    if search:
        mask = (
            df["Imię i nazwisko"].str.contains(search, case=False, na=False) |
            df["Klub debiutu"].str.contains(search, case=False, na=False)
        )
        df = df[mask]

    st.caption(f"Po filtrach: **{len(df)} pro-graczy**")

    # Pokazuj tylko najważniejsze kolumny w głównej tabeli
    main_cols = ["Imię i nazwisko", "Wiek debiutu", "Klub debiutu", "Liga debiutu", "Liczba sezonów"]
    main_cols = [c for c in main_cols if c in df.columns]
    st.dataframe(df[main_cols], width="stretch", hide_index=True)

    # Drill-down
    if len(df) > 0:
        st.divider()
        st.subheader("🔍 Szczegółowa trajektoria")
        sel_pro = st.selectbox("Wybierz zawodnika:", df["Imię i nazwisko"].tolist())

        # Tabela sezonów
        full = pro_detail[pro_detail["Imię i nazwisko"] == sel_pro].copy()
        full = full.sort_values("Lat przed debiutem", ascending=False)
        if len(full) > 0:
            display = full[["Lat przed debiutem", "Wiek w sezonie", "Liga(i)",
                          "Łącznie min", "Mecze", "Aktywność", "Klub", "Match score"]]
            st.dataframe(display, width="stretch", hide_index=True)

            # Wykres trajektorii pojedynczego pro
            pro_traj = pro_paths_raw[pro_paths_raw["player_name"] == sel_pro].copy()
            if len(pro_traj) > 0:
                agg = pro_traj.groupby("age_in_season").agg(
                    level=("league_level", "max"),
                    minutes=("total_minutes", "sum"),
                    score=("avg_score", "mean"),
                ).reset_index()
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=agg["age_in_season"], y=agg["level"],
                    mode="lines+markers", name="Poziom",
                    line=dict(color="#1F77B4", width=3),
                ))
                fig.update_layout(
                    title=f"Trajektoria {sel_pro}",
                    xaxis_title="Wiek", yaxis_title="Poziom ligi",
                    yaxis=dict(range=[0, 14]),
                    height=400,
                )
                st.plotly_chart(fig, width="stretch")


# ══════════════════════════════════════════════════════════════════════════════
# STRONA 4: WALIDACJA MODELU
# ══════════════════════════════════════════════════════════════════════════════

elif page == "✅ Walidacja modelu":
    st.title("Walidacja modelu — backtest")
    st.markdown("""
Model sprawdzono metodą **retrospekcji**: cofamy się do końca danego sezonu,
generujemy predykcję widząc TYLKO dane do tego momentu, a potem sprawdzamy
w pełnych danych ilu z wytypowanych zawodników **faktycznie zadebiutowało**
na szczeblu centralnym (Ekstraklasa / 1. Liga / 2. Liga) w kolejnych sezonach.
""")

    # Spróbuj wczytać pliki backtestów
    backtests = {}
    for label, fname, n_seasons in [
        ("21/22", "backtest_21_22.csv", 4),
        ("22/23", "backtest_22_23.csv", 3),
        ("23/24", "backtest_23_24.csv", 2),
    ]:
        p = DATA_DIR / fname
        if p.exists():
            backtests[label] = (pd.read_csv(p, encoding="utf-8-sig"), n_seasons)

    if not backtests:
        st.warning("Brak plików backtest_*.csv w folderze data/. "
                   "Uruchom `python backtest.py 21/22` itd.")
        st.stop()

    # ── Precision @ K ─────────────────────────────────────────────────────────
    st.subheader("🎯 Precision @ K — trafność czołówki rankingu")
    st.caption("Z TOP-K rekomendacji ilu % faktycznie zadebiutowało. "
               "Bazowy odsetek (losowy zawodnik) to ~0.5–0.8%.")

    rows = []
    for label, (df, n_seasons) in backtests.items():
        df = df.sort_values("ocena", ascending=False).reset_index(drop=True)
        base = df["debuted_after"].mean()
        for k in [10, 25, 50, 100, 250]:
            if k > len(df):
                continue
            prec = df.head(k)["debuted_after"].mean()
            rows.append({
                "Cutoff": label,
                "Okno (sezony)": n_seasons,
                "TOP K": k,
                "Trafność %": round(prec * 100, 1),
                "Lift": f"{prec/base:.0f}x" if base > 0 else "—",
            })
    prec_df = pd.DataFrame(rows)
    st.dataframe(prec_df, width="stretch", hide_index=True)

    # Wykres precision@K
    fig = go.Figure()
    for label, (df, _) in backtests.items():
        df = df.sort_values("ocena", ascending=False).reset_index(drop=True)
        ks = [10, 25, 50, 100, 250, 500]
        precs = [df.head(k)["debuted_after"].mean() * 100 for k in ks if k <= len(df)]
        fig.add_trace(go.Scatter(x=ks[:len(precs)], y=precs, mode="lines+markers",
                                 name=f"Cutoff {label}"))
    fig.update_layout(title="Precision @ K dla 3 punktów odcięcia",
                      xaxis_title="TOP K rekomendacji", yaxis_title="% zadebiutowało",
                      height=400)
    st.plotly_chart(fig, width="stretch")

    # ── Kalibracja ────────────────────────────────────────────────────────────
    st.subheader("📊 Kalibracja — ocena vs realna szansa debiutu")
    st.caption("Łączymy wszystkie 3 backtesty. To podstawa kolumny 'Szansa %'.")

    allb = pd.concat([df for df, _ in backtests.values()], ignore_index=True)
    bins = [0, 30, 40, 50, 60, 70, 75, 80, 85, 100]
    allb["bin"] = pd.cut(allb["ocena"], bins)
    calib = allb.groupby("bin", observed=True).agg(
        N=("debuted_after", "size"),
        debiut_pct=("debuted_after", lambda s: round(s.mean() * 100, 1)),
    ).reset_index()
    calib["bin"] = calib["bin"].astype(str)
    calib.columns = ["Przedział oceny", "N", "Debiut %"]
    st.dataframe(calib, width="stretch", hide_index=True)

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=calib["Przedział oceny"], y=calib["Debiut %"]))
    fig2.update_layout(title="Im wyższa ocena, tym wyższa realna szansa debiutu",
                       xaxis_title="Przedział oceny", yaxis_title="% zadebiutowało",
                       height=400)
    st.plotly_chart(fig2, width="stretch")

    # ── Trafność wg wieku ─────────────────────────────────────────────────────
    st.subheader("👶 Trafność wg wieku")
    st.caption("Młodsi mają mniej czasu na debiut (cenzurowanie), ale i tak "
               "model najlepiej typuje właśnie młodych.")
    age_rows = []
    for label, (df, _) in backtests.items():
        for lo, hi, lbl in [(15, 18, "15-18"), (19, 21, "19-21"), (22, 26, "22-26")]:
            sub = df[(df["age"] >= lo) & (df["age"] <= hi)]
            top = sub.sort_values("ocena", ascending=False).head(max(1, len(sub) // 20))  # top 5%
            if len(sub) == 0:
                continue
            age_rows.append({
                "Cutoff": label, "Wiek": lbl,
                "Cała grupa %": round(sub["debuted_after"].mean() * 100, 1),
                "TOP 5% grupy %": round(top["debuted_after"].mean() * 100, 1),
            })
    st.dataframe(pd.DataFrame(age_rows), width="stretch", hide_index=True)

    st.info("""
**Wniosek:** czołówka rankingu trafia 25–50× lepiej niż losowe typowanie,
i wzorzec powtarza się na 3 niezależnych punktach w czasie. Model ma realną
moc predykcyjną — szczególnie dla młodych zawodników. Pełna szansa nawet dla
najlepszych to ~19%, bo dotarcie na szczebel centralny jest po prostu rzadkie
(bazowo <1%).
""")