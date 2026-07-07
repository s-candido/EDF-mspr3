"""
MLflow Experiments Explorer — Browse training experiments and compare model performance.

Use this page to:
- List every MODEL_EDF_* experiment with creation time
- Dive into a run and see the data timeline it was trained on
- Compare R2, RMSE, MAPE scores across experiments
- View best and fallback model names and hyperparameters
"""

import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="MLflow Experiments",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

MLFLOW_URL = os.environ.get("MLFLOW_URL", "http://mlflow:5000")




def _api_get(path):
    import requests
    resp = requests.get(f"{MLFLOW_URL}{path}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def _api_post(path, body):
    import requests
    resp = requests.post(f"{MLFLOW_URL}{path}", json=body, timeout=10)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=30)
def list_experiments():
    data = _api_get("/api/2.0/mlflow/experiments/list")
    exps = data.get("experiments", [])
    exps.sort(key=lambda e: e.get("creation_time", 0), reverse=True)
    return exps


@st.cache_data(ttl=30)
def search_runs(experiment_ids):
    data = _api_post("/api/2.0/mlflow/search/runs", {
        "experiment_ids": experiment_ids,
        "order_by": ["attribute.start_time DESC"],
        "max_results": 50,
    })
    return data.get("runs", [])




def _r2_color(val):
    if val is None:
        return "#888"
    if val >= 0.9:
        return "#2ecc71"
    if val >= 0.7:
        return "#27ae60"
    if val >= 0.5:
        return "#f39c12"
    return "#e74c3c"


def _mape_color(val):
    if val is None:
        return "#888"
    if val <= 10:
        return "#2ecc71"
    if val <= 20:
        return "#27ae60"
    if val <= 30:
        return "#f39c12"
    return "#e74c3c"


def _rmse_color(val):
    if val is None:
        return "#888"
    return "#3498db"




st.title("🧪 MLflow Experiments Explorer")
st.markdown("Browse every training experiment, inspect data timelines, and compare model performance.")

experiments = list_experiments()
edf_experiments = [e for e in experiments if e.get("name", "").startswith("MODEL_EDF_")]
other_experiments = [e for e in experiments if not e.get("name", "").startswith("MODEL_EDF_")]

if not experiments:
    st.warning("No experiments found on MLflow server. Run the training DAG first.")
    st.stop()



st.sidebar.header("🔬 Experiments")

all_label = f"All MODEL_EDF_* ({len(edf_experiments)})"
exp_names = [all_label] + [e["name"] for e in edf_experiments]
selected = st.sidebar.radio("Select an experiment", exp_names, index=0)

if selected == all_label:
    target_exps = edf_experiments
else:
    target_exps = [e for e in edf_experiments if e["name"] == selected]

if not target_exps:
    st.info("No MODEL_EDF_* experiments available. Run the training DAG first.")
    st.stop()


all_runs = []
for exp in target_exps:
    all_runs.extend(search_runs([exp["experiment_id"]]))

if not all_runs:
    st.info("No runs found in the selected experiments.")
    st.stop()




def _ts(ms):
    """Format millisecond epoch to readable datetime."""
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S") if ms else "—"


def _param(run, key, default="—"):
    for p in run.get("data", {}).get("params", []):
        if p["key"] == key:
            return p["value"]
    return default


def _metric(run, key):
    for m in run.get("data", {}).get("metrics", []):
        if m["key"] == key:
            return m["value"]
    return None


st.subheader(f"📋 {len(all_runs)} run(s) found")

for run in all_runs:
    info = run.get("info", {})
    run_id = info.get("run_id", "")
    run_name = info.get("run_name", run_id[:8])
    status = info.get("status", "UNKNOWN")
    start = info.get("start_time")
    end = info.get("end_time")

    r2 = _metric(run, "R2")
    rmse = _metric(run, "RMSE")
    mape = _metric(run, "MAPE")
    model_type = _param(run, "model_type")
    fallback_type = _param(run, "fallback_model_type")
    data_start = _param(run, "data_start_date")
    data_end = _param(run, "data_end_date")
    sel_years = _param(run, "selected_years")
    sel_months = _param(run, "selected_months")
    sel_days = _param(run, "selected_days")
    n_samples = _param(run, "n_samples")

    duration = ""
    if start and end:
        dur_s = (end - start) / 1000
        if dur_s >= 60:
            duration = f"{dur_s / 60:.1f} min"
        else:
            duration = f"{dur_s:.0f}s"

    status_icon = "✅" if status == "FINISHED" else "❌" if status == "FAILED" else "⏳"

    with st.container(border=True):
        cols = st.columns([2, 1, 1, 1, 1.5])
        with cols[0]:
            st.markdown(f"**{run_name}**  ")
            st.caption(f"`{run_id[:12]}…`  ·  {_ts(start)}")
        with cols[1]:
            st.markdown(f"{status_icon} {status}")
            st.caption(f"Duration: {duration}" if duration else "")
        with cols[2]:
            if r2 is not None:
                st.markdown(f"**R²**  \n`{r2:.4f}`")
        with cols[3]:
            if rmse is not None:
                st.markdown(f"**RMSE**  \n`{rmse:.2f}`")
        with cols[4]:
            if mape is not None:
                st.markdown(f"**MAPE**  \n`{mape:.1f}%`")

        
        expand_key = f"exp_{run_id}"
        if st.button("🔍 Details", key=expand_key):
            st.session_state[expand_key] = not st.session_state.get(expand_key, False)

        if st.session_state.get(expand_key, False):
            st.markdown("---")


            dcol1, dcol2 = st.columns([2, 1.5])
            with dcol1:
                st.markdown("**📅 Training data timeline**")
                if data_start and data_end and data_start != "—" and data_end != "—":
                    try:
                        ds = pd.to_datetime(data_start)
                        de = pd.to_datetime(data_end)
                        span_days = (de - ds).days

                        fig_timeline = go.Figure()
                        fig_timeline.add_trace(go.Scatter(
                            x=[ds, de],
                            y=[0, 0],
                            mode="lines+markers",
                            marker=dict(size=12, color="#2E86AB"),
                            line=dict(width=6, color="#2E86AB"),
                            showlegend=False,
                            hovertemplate="%{x|%Y-%m-%d}<extra></extra>",
                        ))
                        fig_timeline.add_annotation(
                            x=ds + (de - ds) / 2, y=0,
                            text=f"{span_days} days of data",
                            showarrow=False,
                            yshift=20,
                            font=dict(size=13),
                        )
                        fig_timeline.update_layout(
                            height=120,
                            margin=dict(l=10, r=10, t=30, b=10),
                            xaxis=dict(showgrid=False, zeroline=False, visible=True),
                            yaxis=dict(showgrid=False, zeroline=False, visible=False),
                        )
                        st.plotly_chart(fig_timeline, use_container_width=True)
                    except Exception:
                        st.write(f"`{data_start}` → `{data_end}`")
                else:
                    st.info("No data range logged for this run.")

            with dcol2:
                st.markdown("**🎯 Selected filters**")
                filt = {}
                if sel_years:
                    filt["Years"] = sel_years
                if sel_months:
                    filt["Months"] = sel_months
                if sel_days:
                    filt["Days"] = sel_days
                if filt:
                    for k, v in filt.items():
                        st.markdown(f"- **{k}**: {v}")
                if n_samples:
                    st.markdown(f"- **Samples**: {n_samples}")
                if model_type:
                    st.markdown(f"- **Features**: {_param(run, 'features', '—')}")


            st.markdown("**📊 Performance**")
            pcols = st.columns(3)
            with pcols[0]:
                if r2 is not None:
                    fig_r2 = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=r2,
                        number={"font": {"size": 28, "color": _r2_color(r2)}},
                        gauge={
                            "axis": {"range": [0, 1], "tickwidth": 1},
                            "bar": {"color": _r2_color(r2)},
                            "steps": [
                                {"range": [0, 0.5], "color": "#ffe6e6"},
                                {"range": [0.5, 0.7], "color": "#fff3cd"},
                                {"range": [0.7, 0.9], "color": "#d4edda"},
                                {"range": [0.9, 1], "color": "#c3e6cb"},
                            ],
                            "threshold": {
                                "line": {"color": "red", "width": 2},
                                "thickness": 0.75,
                                "value": 0.7,
                            },
                        },
                        title={"text": "R² Score"},
                    ))
                    fig_r2.update_layout(height=220, margin=dict(l=30, r=30, t=40, b=10))
                    st.plotly_chart(fig_r2, use_container_width=True)

            with pcols[1]:
                if rmse is not None:
                    fig_rmse = go.Figure(go.Indicator(
                        mode="number+delta",
                        value=rmse,
                        number={"font": {"size": 28, "color": _rmse_color(rmse)}},
                        delta={"reference": 0, "position": "top"},
                        title={"text": "RMSE (kWh)"},
                    ))
                    fig_rmse.update_layout(height=220, margin=dict(l=30, r=30, t=40, b=10))
                    st.plotly_chart(fig_rmse, use_container_width=True)

            with pcols[2]:
                if mape is not None:
                    fig_mape = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=mape,
                        number={"suffix": "%", "font": {"size": 28, "color": _mape_color(mape)}},
                        gauge={
                            "axis": {"range": [0, max(50, mape * 1.2)], "tickwidth": 1},
                            "bar": {"color": _mape_color(mape)},
                            "steps": [
                                {"range": [0, 10], "color": "#d4edda"},
                                {"range": [10, 20], "color": "#fff3cd"},
                                {"range": [20, 30], "color": "#ffe6e6"},
                                {"range": [30, max(50, mape * 1.2)], "color": "#f8d7da"},
                            ],
                            "threshold": {
                                "line": {"color": "red", "width": 2},
                                "thickness": 0.75,
                                "value": 10,
                            },
                        },
                        title={"text": "MAPE"},
                    ))
                    fig_mape.update_layout(height=220, margin=dict(l=30, r=30, t=40, b=10))
                    st.plotly_chart(fig_mape, use_container_width=True)


            st.markdown("**🤖 Models**")
            mcols = st.columns(2)
            with mcols[0]:
                st.markdown(f"##### 🏆 Best: `{model_type or '—'}`")
                if model_type:
                    best_hp = {p["key"].removeprefix("hp_"): p["value"]
                               for p in run.get("data", {}).get("params", [])
                               if p["key"].startswith("hp_")}
                    if best_hp:
                        st.json(best_hp, expanded=False)
                st.caption(f"Registered as `MODEL_EDF`")

            with mcols[1]:
                if fallback_type:
                    st.markdown(f"##### 🔄 Fallback: `{fallback_type}`")
                    fb_hp = {p["key"].removeprefix("fallback_hp_"): p["value"]
                             for p in run.get("data", {}).get("params", [])
                             if p["key"].startswith("fallback_hp_")}
                    if fb_hp:
                        st.json(fb_hp, expanded=False)
                    fb_reg = _param(run, "fallback_model_type", "")
                    st.caption(f"Registered as `fallback_{fb_reg}`")
                else:
                    st.markdown("##### 🔄 Fallback")
                    st.info("No fallback model in this run")


            st.markdown(
                f"🔗 [`runs:/{run_id}`]({MLFLOW_URL}/#/experiments/{info.get('experiment_id', '')}/"
                f"runs/{run_id}) — Open in MLflow UI"
            )



st.markdown("---")
st.subheader("📈 Experiment summary")

rows = []
for exp in edf_experiments[:20]:
    exp_runs = search_runs([exp["experiment_id"]])
    if exp_runs:
        r = exp_runs[0]
        rows.append({
            "Experiment": exp["name"],
            "Created": _ts(exp.get("creation_time")),
            "Best model": _param(r, "model_type"),
            "Fallback": _param(r, "fallback_model_type") or "—",
            "R²": _metric(r, "R2"),
            "RMSE": _metric(r, "RMSE"),
            "MAPE (%)": _metric(r, "MAPE"),
            "Data range": f"{_param(r, 'data_start_date', '?')} → {_param(r, 'data_end_date', '?')}",
            "Samples": _param(r, "n_samples", "—"),
        })

if rows:
    df_summary = pd.DataFrame(rows)

    def _highlight_r2(v):
        if isinstance(v, (int, float)):
            c = _r2_color(v)
            return f"color: {c}; font-weight: bold"
        return ""
    styled = df_summary.style.map(_highlight_r2, subset=["R²"])
    st.dataframe(styled, use_container_width=True, hide_index=True)
else:
    st.info("No experiment data yet.")
