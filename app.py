import streamlit as st
import pandas as pd
import pyodbc
from streamlit_autorefresh import st_autorefresh
import plotly.express as px

# ============================
# VIEW AI CONFIG
# ============================

REFRESH_EVERY_MS = 5 * 60 * 1000  

st.set_page_config(
    page_title="View AI • Uptime Monitor",
    layout="wide",
)

st.markdown("""
<style>
.metric-box {
    padding: 18px;
    border-radius: 12px;
    background: linear-gradient(135deg,#1f2933,#111827);
    box-shadow: 0 0 15px rgba(0,0,0,.3);
    text-align:center;
}
.status-ok {color:#22c55e;font-weight:bold;}
.status-warn {color:#facc15;font-weight:bold;}
.status-stop {color:#ef4444;font-weight:bold;}
</style>
""", unsafe_allow_html=True)

st_autorefresh(interval=REFRESH_EVERY_MS, key="refresh")

# ============================
# HEADER
# ============================

st.title("🧠 View AI — Real Time Robot Monitor")
st.caption("Monitoramento de ingestão das inteligências artificiais")

# ============================
# CONEXÃO
# ============================

def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=equinox.assistia.local;"
        "DATABASE=dbcarglasssys;"
        "Trusted_Connection=yes;"
    )

# ============================
# QUERY
# ============================

QUERY = """
DECLARE @WindowMinutes FLOAT = 5;

WITH RoboBase AS (

    SELECT
        'MirrorGlass' AS Robo,
        MAX(CreationDate) AS LastReadDateTime,
        COUNT(CASE WHEN CreationDate >= DATEADD(MINUTE, -@WindowMinutes, GETDATE()) THEN 1 END) AS RowsLastWindow
    FROM IA.PhotoManipulationAnalysisMirrorGlass

    UNION ALL

    SELECT
        'SRO',
        MAX(CreationDate),
        COUNT(CASE WHEN CreationDate >= DATEADD(MINUTE, -@WindowMinutes, GETDATE()) THEN 1 END)
    FROM Log.tbComplaintResultIA

    UNION ALL

    SELECT
        'HeatGlass',
        MAX(AnalysisDateTime),
        COUNT(CASE WHEN AnalysisDateTime >= DATEADD(MINUTE, -@WindowMinutes, GETDATE()) THEN 1 END)
    FROM IA.tbAnalysisHeat
),

RoboStatus AS (

    SELECT
        Robo,
        LastReadDateTime,
        DATEDIFF(MINUTE, LastReadDateTime, GETDATE()) AS MinutesSinceLastRead,
        RowsLastWindow
    FROM RoboBase
)

SELECT
    Robo,
    LastReadDateTime,
    MinutesSinceLastRead,
    RowsLastWindow,
    CASE
        WHEN LastReadDateTime IS NULL THEN 'SEM DADOS'
        WHEN MinutesSinceLastRead <= 5 AND RowsLastWindow > 0 THEN 'OK'
        WHEN MinutesSinceLastRead <= 10 THEN 'ATRASANDO'
        ELSE 'PARADO'
    END AS Status
FROM RoboStatus
ORDER BY MinutesSinceLastRead;
"""

# ============================
# LOAD
# ============================

@st.cache_data(ttl=300)
def load_data():
    with get_connection() as conn:
        return pd.read_sql(QUERY, conn)

df = load_data()

# ============================
# METRICS
# ============================

c1, c2, c3 = st.columns(3)

total_events = df["RowsLastWindow"].sum()
ativos = (df["Status"] == "OK").sum()
parados = (df["Status"] == "PARADO").sum()

c1.metric("📥 Eventos últimos 5 min", total_events)
c2.metric("🟢 Robôs ativos", ativos)
c3.metric("🔴 Robôs parados", parados)

st.divider()

# ============================
# GRÁFICO
# ============================

fig = px.bar(
    df,
    x="Robo",
    y="RowsLastWindow",
    color="Status",
    title="Atividade por Robô (últimos 5 minutos)",
    text="RowsLastWindow",
)

fig.update_layout(height=420)

st.plotly_chart(fig, use_container_width=True)

# ============================
# TABELA BONITA
# ============================

def color_status(val):
    if val == "OK":
        return "color:#22c55e;font-weight:bold"
    if val == "ATRASANDO":
        return "color:#facc15;font-weight:bold"
    return "color:#ef4444;font-weight:bold"

styled = df.style.applymap(color_status, subset=["Status"])

st.subheader("📊 Detalhamento por IA")
st.dataframe(styled, use_container_width=True)

# ============================
# ALERTA INTELIGENTE
# ============================

if parados > 0:
    st.error("⚠ Existem robôs PARADOS. Verificar pipelines imediatamente.")
elif ativos == len(df):
    st.success("✅ Todos os robôs operando normalmente.")
else:
    st.warning("⚠ Alguns robôs apresentando atraso.")
