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
    pro_debut = pd.read_excel(DATA_DIR / "pro_career_paths.xlsx", sheet_name="Pro debiut")
    pro_detail = pd.read_excel(DATA_DIR / "pro_career_paths.xlsx", sheet_name="Detale")
    return cand_ranking, pro_debut, pro_detail


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
    cand_ranking, pro_debut, pro_detail = load_data()
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


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

st.sidebar.title("⚽ Career Paths")
page = st.sidebar.radio(
    "Strona",
    ["📊 Ranking kandydatów", "🔍 Szczegóły kandydata", "📚 Encyklopedia pro"],
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
# STRONA 1: RANKING
# ══════════════════════════════════════════════════════════════════════════════

if page == "📊 Ranking kandydatów":
    st.title("Ranking kandydatów")

    # Filtry
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        age_range = st.slider("Wiek", 15, 26, (15, 26))
    with c2:
        min_ocena = st.slider("Min. ocena", 0, 100, 50)
    with c3:
        levels = sorted(cand_ranking["Obecny poziom"].dropna().unique().tolist())
        sel_levels = st.multiselect("Obecny poziom", levels, default=levels)
    with c4:
        activities = sorted(cand_ranking["Aktywność"].dropna().unique().tolist())
        sel_act = st.multiselect("Aktywność", activities, default=activities)

    df = cand_ranking[
        (cand_ranking["Wiek"] >= age_range[0]) &
        (cand_ranking["Wiek"] <= age_range[1]) &
        (cand_ranking["Ocena"] >= min_ocena) &
        (cand_ranking["Obecny poziom"].isin(sel_levels)) &
        (cand_ranking["Aktywność"].isin(sel_act))
    ].copy()

    st.caption(f"Po filtrach: **{len(df)} kandydatów**")

    # Pokaż tylko kluczowe kolumny + % total (resztę da się zobaczyć w xlsx)
    show_cols = [
        "#", "Zawodnik", "Klub", "Wiek", "Obecny poziom",
        "Minuty", "Mecze", "Score", "Aktywność",
        "Ocena", "Status",
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

    st.divider()

    # ── Panel 1: Karta 4 kolumn (kandydat + 3 pro) ────────────────────────────
    st.subheader("📋 Karta porównawcza")

    # Sprawdź czy są backupy
    main_name = cand.get("Match #1 (główny)")
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

    # Dane kandydata: wszystkie sezony z candidates_raw, najwyższy poziom per sezon
    def get_player_trajectory(df, player_name):
        """Zwraca DataFrame: age, level, minutes, score, leagues_str dla każdego sezonu."""
        # df: candidates_raw lub pro_paths_raw
        p = df[df["player_name"] == player_name].copy()
        if len(p) == 0:
            return pd.DataFrame()
        # Per sezon: najwyższy level + suma minut + średni score + lista lig
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

else:
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
