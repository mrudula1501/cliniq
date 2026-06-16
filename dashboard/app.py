"""
ClinIQ — Live Analytics Dashboard
===================================
Streamlit dashboard connecting to Snowflake CLINIQ.DBT_DEV.
Run: streamlit run dashboard/app.py
"""

import os
import sys
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv
import snowflake.connector

# ── Config ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

st.set_page_config(
    page_title="ClinIQ | Clinical Quality Gap Analytics",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Brand colours ─────────────────────────────────────────────────────────────
BLUE   = "#1F6FEB"
RED    = "#E53935"
GREEN  = "#2E7D32"
AMBER  = "#F57F17"
LIGHT  = "#F8FAFC"

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Background */
  .main { background-color: #F0F4F8; }
  /* KPI cards */
  .kpi-card {
      background: white;
      border-radius: 12px;
      padding: 20px 24px;
      box-shadow: 0 1px 4px rgba(0,0,0,.08);
      text-align: center;
  }
  .kpi-label { font-size: 13px; color: #64748B; font-weight: 600; letter-spacing: .5px; text-transform: uppercase; }
  .kpi-value { font-size: 40px; font-weight: 700; margin: 4px 0; }
  .kpi-sub   { font-size: 13px; color: #94A3B8; }
  /* Header */
  .cliniq-header {
      background: linear-gradient(135deg, #1F6FEB 0%, #0EA5E9 100%);
      border-radius: 16px;
      padding: 28px 36px;
      color: white;
      margin-bottom: 24px;
  }
  .cliniq-header h1 { margin: 0; font-size: 32px; font-weight: 800; }
  .cliniq-header p  { margin: 6px 0 0; font-size: 15px; opacity: .85; }
  /* Section headers */
  .section-title { font-size: 18px; font-weight: 700; color: #1E293B; margin: 24px 0 12px; }
</style>
""", unsafe_allow_html=True)


# ── Snowflake connection ──────────────────────────────────────────────────────
def _secret(key, default=None):
    """Read from st.secrets (Streamlit Cloud) with fallback to os.getenv (local)."""
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

@st.cache_resource(show_spinner=False)
def get_conn():
    return snowflake.connector.connect(
        account  = _secret("SNOWFLAKE_ACCOUNT"),
        user     = _secret("SNOWFLAKE_USER"),
        password = _secret("SNOWFLAKE_PASSWORD"),
        warehouse= _secret("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database = "CLINIQ",
        schema   = "DBT_DEV",
        role     = _secret("SNOWFLAKE_ROLE", "SYSADMIN"),
    )

@st.cache_data(ttl=300, show_spinner=False)
def query(sql: str) -> pd.DataFrame:
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(sql)
    cols = [c[0] for c in cur.description]
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner("Loading live data from Snowflake…"):
    try:
        gap  = query("SELECT * FROM MART_GAP_REGISTRY")
        summ = query("SELECT * FROM MART_QUALITY_SUMMARY")
        ok   = True
    except Exception as e:
        ok  = False
        err = str(e)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="cliniq-header">
  <h1>🏥 ClinIQ — Clinical Quality Gap Analytics</h1>
  <p>Heart Failure · Guideline-Directed Medical Therapy (GDMT) Gap Detection · Live from Snowflake</p>
</div>
""", unsafe_allow_html=True)

if not ok:
    st.error(f"Could not connect to Snowflake: {err}")
    st.stop()

# Normalise column names to lower-case for safety
gap.columns  = [c.lower() for c in gap.columns]
summ.columns = [c.lower() for c in summ.columns]

# ── Sidebar filters ───────────────────────────────────────────────────────────
st.sidebar.image("https://img.icons8.com/color/96/hospital.png", width=64)
st.sidebar.title("ClinIQ Filters")

genders   = ["All"] + sorted(gap["gender"].dropna().unique().tolist())
sel_gender = st.sidebar.selectbox("Gender", genders)

races = ["All"] + sorted(gap["race"].dropna().unique().tolist())
sel_race = st.sidebar.selectbox("Race / Ethnicity", races)

age_min, age_max = int(gap["age"].min()), int(gap["age"].max())
sel_age = st.sidebar.slider("Age Range", age_min, age_max, (age_min, age_max))

gap_filter = st.sidebar.radio("Gap Status", ["All Patients", "Care Gap Only", "On GDMT"])

st.sidebar.markdown("---")
st.sidebar.caption("Data refreshes every 5 minutes from **CLINIQ.DBT_DEV**")

# Apply filters
df = gap.copy()
if sel_gender != "All":
    df = df[df["gender"] == sel_gender]
if sel_race != "All":
    df = df[df["race"] == sel_race]
df = df[(df["age"] >= sel_age[0]) & (df["age"] <= sel_age[1])]
if gap_filter == "Care Gap Only":
    df = df[df["has_care_gap"] == True]
elif gap_filter == "On GDMT":
    df = df[df["has_care_gap"] == False]

# ── KPI cards ─────────────────────────────────────────────────────────────────
total   = len(df)
n_gap   = int(df["has_care_gap"].sum()) if "has_care_gap" in df.columns else 0
n_gdmt  = total - n_gap
gap_pct = round(n_gap / total * 100, 1) if total > 0 else 0
bb_pct  = round(df["on_beta_blocker"].sum() / total * 100, 1) if total > 0 else 0
aa_pct  = round(df["on_ace_arb"].sum() / total * 100, 1) if total > 0 else 0

c1, c2, c3, c4, c5 = st.columns(5)
cards = [
    (c1, str(total),         "HF Patients",           "#1F6FEB", "in filtered cohort"),
    (c2, f"{n_gap}",         "Care Gaps Identified",  "#E53935", f"{gap_pct}% of cohort"),
    (c3, f"{n_gdmt}",        "Receiving Full GDMT",   "#2E7D32", f"{100-gap_pct}% of cohort"),
    (c4, f"{bb_pct}%",       "On Beta-Blocker",       "#0284C7", "carvedilol / metoprolol / bisoprolol"),
    (c5, f"{aa_pct}%",       "On ACE/ARB",            "#7C3AED", "lisinopril / enalapril / losartan"),
]
for col, val, label, color, sub in cards:
    col.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value" style="color:{color}">{val}</div>
      <div class="kpi-sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Row 1: Gap reason breakdown + Gender gap rate ─────────────────────────────
col_a, col_b = st.columns([3, 2])

with col_a:
    st.markdown('<div class="section-title">Gap Reason Breakdown</div>', unsafe_allow_html=True)
    reason_df = (
        df[df["has_care_gap"] == True]["gap_reason"]
        .value_counts()
        .reset_index()
    )
    reason_df.columns = ["gap_reason", "count"]
    fig_reason = px.bar(
        reason_df, x="count", y="gap_reason", orientation="h",
        color="count",
        color_continuous_scale=[[0, "#FCA5A5"], [1, "#E53935"]],
        labels={"count": "Patients", "gap_reason": ""},
        text="count",
    )
    fig_reason.update_traces(textposition="outside")
    fig_reason.update_layout(
        height=260, margin=dict(l=0, r=20, t=0, b=0),
        showlegend=False, coloraxis_showscale=False,
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig_reason, use_container_width=True)

with col_b:
    st.markdown('<div class="section-title">Gap Rate by Gender</div>', unsafe_allow_html=True)
    gen_df = (
        df.groupby("gender")["has_care_gap"]
        .agg(gap_count="sum", total="count")
        .reset_index()
    )
    gen_df["gap_rate"] = (gen_df["gap_count"] / gen_df["total"] * 100).round(1)
    fig_gen = px.bar(
        gen_df, x="gender", y="gap_rate",
        color="gender",
        color_discrete_map={"M": "#1F6FEB", "F": "#EC4899"},
        labels={"gap_rate": "Gap Rate (%)", "gender": ""},
        text=gen_df["gap_rate"].astype(str) + "%",
    )
    fig_gen.update_traces(textposition="outside")
    fig_gen.update_layout(
        height=260, margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        plot_bgcolor="white", paper_bgcolor="white",
        yaxis=dict(range=[0, 100]),
    )
    st.plotly_chart(fig_gen, use_container_width=True)

# ── Row 2: Age distribution + Race gap rates ──────────────────────────────────
col_c, col_d = st.columns([2, 3])

with col_c:
    st.markdown('<div class="section-title">Age Distribution</div>', unsafe_allow_html=True)
    fig_age = px.histogram(
        df, x="age", color="has_care_gap",
        color_discrete_map={True: "#E53935", False: "#2E7D32"},
        labels={"age": "Age", "has_care_gap": "Care Gap"},
        barmode="overlay", nbins=20, opacity=0.75,
    )
    fig_age.update_layout(
        height=260, margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(title="", orientation="h", yanchor="top", y=1.1),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig_age, use_container_width=True)

with col_d:
    st.markdown('<div class="section-title">Gap Rate by Race</div>', unsafe_allow_html=True)
    race_df = (
        df.groupby("race")["has_care_gap"]
        .agg(gap_count="sum", total="count")
        .reset_index()
    )
    race_df["gap_rate"] = (race_df["gap_count"] / race_df["total"] * 100).round(1)
    race_df = race_df.sort_values("gap_rate", ascending=True)
    fig_race = px.bar(
        race_df, x="gap_rate", y="race", orientation="h",
        color="gap_rate",
        color_continuous_scale=[[0, "#BBF7D0"], [0.5, "#FDE68A"], [1, "#E53935"]],
        labels={"gap_rate": "Gap Rate (%)", "race": ""},
        text=race_df["gap_rate"].astype(str) + "%",
    )
    fig_race.update_traces(textposition="outside")
    fig_race.update_layout(
        height=260, margin=dict(l=0, r=40, t=0, b=0),
        showlegend=False, coloraxis_showscale=False,
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig_race, use_container_width=True)

# ── Row 3: GDMT funnel + Therapy donut ───────────────────────────────────────
col_e, col_f = st.columns([2, 3])

with col_e:
    st.markdown('<div class="section-title">Care Pathway Funnel</div>', unsafe_allow_html=True)
    diagnosed     = len(gap)          # total HF, unfiltered
    qualifying    = int(gap["has_qualifying_encounter"].sum()) if "has_qualifying_encounter" in gap.columns else diagnosed
    on_therapy    = int((~gap["has_care_gap"]).sum())
    stages = ["HF Diagnosed", "Qualifying Encounter", "Receiving Full GDMT"]
    vals   = [diagnosed, qualifying, on_therapy]
    fig_funnel = go.Figure(go.Funnel(
        y=stages, x=vals,
        textinfo="value+percent initial",
        marker=dict(color=["#1F6FEB", "#0EA5E9", "#2E7D32"]),
    ))
    fig_funnel.update_layout(
        height=260, margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig_funnel, use_container_width=True)

with col_f:
    st.markdown('<div class="section-title">Therapy Coverage</div>', unsafe_allow_html=True)
    bb_yes = int(df["on_beta_blocker"].sum())
    aa_yes = int(df["on_ace_arb"].sum())
    bb_no  = total - bb_yes
    aa_no  = total - aa_yes
    fig_donut = go.Figure()
    fig_donut.add_trace(go.Pie(
        labels=["On Beta-Blocker", "Missing Beta-Blocker"],
        values=[bb_yes, bb_no],
        hole=0.55, name="Beta-Blocker",
        domain={"x": [0, 0.45]},
        marker_colors=["#1F6FEB", "#DBEAFE"],
        textinfo="percent",
    ))
    fig_donut.add_trace(go.Pie(
        labels=["On ACE/ARB", "Missing ACE/ARB"],
        values=[aa_yes, aa_no],
        hole=0.55, name="ACE/ARB",
        domain={"x": [0.55, 1]},
        marker_colors=["#7C3AED", "#EDE9FE"],
        textinfo="percent",
    ))
    fig_donut.add_annotation(x=0.2, y=0.5, text="Beta-<br>Blocker", showarrow=False,
                             font=dict(size=11, color="#1E293B"), align="center")
    fig_donut.add_annotation(x=0.8, y=0.5, text="ACE/<br>ARB", showarrow=False,
                             font=dict(size=11, color="#1E293B"), align="center")
    fig_donut.update_layout(
        height=260, margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig_donut, use_container_width=True)

# ── Row 4: Patient-level table ────────────────────────────────────────────────
st.markdown('<div class="section-title">Patient-Level Gap Registry</div>', unsafe_allow_html=True)

display_cols = ["patient_id", "age", "gender", "race", "state",
                "on_beta_blocker", "on_ace_arb", "has_care_gap", "gap_reason"]
available = [c for c in display_cols if c in df.columns]
table_df  = df[available].copy()

# Friendly column names
rename = {
    "patient_id": "Patient ID", "age": "Age", "gender": "Gender",
    "race": "Race", "state": "State",
    "on_beta_blocker": "Beta-Blocker ✓", "on_ace_arb": "ACE/ARB ✓",
    "has_care_gap": "Care Gap", "gap_reason": "Gap Reason",
}
table_df = table_df.rename(columns=rename)

search = st.text_input("🔍 Search patient ID or gap reason", "")
if search:
    mask = table_df.apply(lambda col: col.astype(str).str.contains(search, case=False, na=False)).any(axis=1)
    table_df = table_df[mask]

st.dataframe(
    table_df,
    use_container_width=True,
    height=350,
    column_config={
        "Care Gap":       st.column_config.CheckboxColumn("Care Gap"),
        "Beta-Blocker ✓": st.column_config.CheckboxColumn("Beta-Blocker ✓"),
        "ACE/ARB ✓":      st.column_config.CheckboxColumn("ACE/ARB ✓"),
    },
)

st.caption(f"Showing {len(table_df):,} of {total:,} patients · Data: CLINIQ.DBT_DEV.MART_GAP_REGISTRY")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<small>ClinIQ — Disease-Agnostic Clinical Quality Gap Analytics Platform · "
    "Built with Streamlit + Snowflake + Python · "
    "[github.com/mrudula1501/cliniq](https://github.com/mrudula1501/cliniq)</small>",
    unsafe_allow_html=True,
)
