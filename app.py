"""
MoM SMAX Analyst — Assignee performance dashboard

- Volume target: 140 tickets per assignee per month
- Resolution target: 85% of tickets created in a month in Completed status

Data: CSV with CreateTime (epoch ms), AssignedToPerson.Name, Status
"""

import pandas as pd
import streamlit as st
from pathlib import Path

# Targets (configurable via sidebar)
TICKET_TARGET = 140
RESOLUTION_TARGET_PCT = 0.85
COMPLETED_STATUS = "RequestStatusComplete"

DATE_COL = "CreateTime"
ASSIGNEE_COL = "AssignedToPerson.Name"
STATUS_COL = "Status"


def load_data(path: str) -> pd.DataFrame:
    """Load CSV and ensure required columns exist."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    df = pd.read_csv(p)
    for col in [DATE_COL, ASSIGNEE_COL, STATUS_COL]:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")
    return df


def parse_create_time(series: pd.Series) -> pd.Series:
    """Parse CreateTime: epoch milliseconds -> datetime."""
    numeric = pd.to_numeric(series, errors="coerce")
    return pd.to_datetime(numeric, unit="ms", errors="coerce")


def build_assignee_monthly(
    df: pd.DataFrame,
    ticket_target: int = TICKET_TARGET,
    resolution_target_pct: float = RESOLUTION_TARGET_PCT,
) -> pd.DataFrame:
    """
    Per assignee, per month (by creation):
    - tickets: count of tickets created that month
    - completed: count with Status == RequestStatusComplete
    - resolution_pct: completed / tickets (target >= 85%)
    """
    df = df.copy()
    df["__dt"] = parse_create_time(df[DATE_COL])
    df = df.dropna(subset=["__dt"])
    df["month"] = df["__dt"].dt.to_period("M").dt.to_timestamp()

    # Fill blank assignee for grouping
    df[ASSIGNEE_COL] = df[ASSIGNEE_COL].fillna("(Unassigned)").astype(str).str.strip()
    df["completed"] = (df[STATUS_COL] == COMPLETED_STATUS).astype(int)

    agg = (
        df.groupby([ASSIGNEE_COL, "month"])
        .agg(tickets=("Id", "count"), completed=("completed", "sum"))
        .reset_index()
    )
    agg["resolution_pct"] = (agg["completed"] / agg["tickets"]).round(4)
    agg["resolution_pct_display"] = (agg["resolution_pct"] * 100).round(1)
    agg["meets_volume_target"] = agg["tickets"] >= ticket_target
    agg["meets_resolution_target"] = agg["resolution_pct"] >= resolution_target_pct
    return agg


def mom_summary(agg: pd.DataFrame, assignees: list[str] | None) -> pd.DataFrame:
    """Month-over-month view: optionally filtered by assignee(s). assignees=None means all."""
    if assignees:
        agg = agg[agg[ASSIGNEE_COL].isin(assignees)].copy()
    agg = agg.sort_values(["month", ASSIGNEE_COL])
    agg["month_label"] = agg["month"].dt.strftime("%Y-%m")
    return agg


def run():
    st.set_page_config(page_title="MoM SMAX Analyst", layout="wide")
    st.title("MoM SMAX Assignee Analysis")
    st.caption("Volume target: 140 tickets/month per assignee · Resolution target: 85% per month")

    # Sidebar: file and targets
    with st.sidebar:
        st.subheader("Settings")
        uploaded = st.file_uploader("Upload CSV", type=["csv"])
        default_path = Path(__file__).parent / "Request_20260304_1010302318309310430531382643.csv"
        csv_path = st.text_input(
            "Or CSV path (server/local run)",
            value=str(default_path),
            help="On Streamlit Cloud, use the uploader above. This path is only valid on the machine running the app.",
        )
        ticket_target = st.number_input("Tickets target per month", min_value=1, value=TICKET_TARGET)
        resolution_target = st.number_input(
            "Resolution target (%)", min_value=1, max_value=100, value=85
        ) / 100

    ticket_target = int(ticket_target)
    try:
        if uploaded is not None:
            df = pd.read_csv(uploaded)
        else:
            df = load_data(csv_path)
    except Exception as e:
        st.error(f"Could not load data: {e}")
        return

    agg = build_assignee_monthly(df, ticket_target=ticket_target, resolution_target_pct=resolution_target)
    all_assignees = sorted(agg[ASSIGNEE_COL].unique().tolist())

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_assignees = st.multiselect(
            "Assignees (empty = all)",
            options=all_assignees,
            default=None,
            help="Select one or more assignees. Volume target = 140 × number selected (empty = all).",
        )
    # Resolve selection: empty means all assignees
    assignees_in_scope = selected_assignees if selected_assignees else all_assignees
    # Compound volume target: 140 × number of assignees, capped at 420
    effective_volume_target = min(ticket_target * len(assignees_in_scope), 420)
    with col2:
        months = sorted(agg["month"].unique())
        if months:
            month_min = st.selectbox(
                "From month",
                options=[""] + [m.strftime("%Y-%m") for m in months],
                index=0,
            )
        else:
            month_min = ""
    with col3:
        if months:
            month_max = st.selectbox(
                "To month",
                options=[""] + [m.strftime("%Y-%m") for m in months],
                index=len(months) if months else 0,
            )
        else:
            month_max = ""

    view = mom_summary(agg, selected_assignees if selected_assignees else None)
    if month_min:
        view = view[view["month_label"] >= month_min]
    if month_max:
        view = view[view["month_label"] <= month_max]

    st.subheader("Month-over-month by assignee")
    if view.empty:
        st.info("No data for the selected filters.")
        return

    # Summary cards: aggregate by month for selected assignee(s); volume target compounds (140 × n)
    if len(assignees_in_scope) == 1:
        sub = view.copy()
        sub["resolution_pct_display"] = (sub["resolution_pct"] * 100).round(1)
        label = f"**{assignees_in_scope[0]}**"
    else:
        sub = view.groupby("month").agg(
            tickets=("tickets", "sum"),
            completed=("completed", "sum"),
        ).reset_index()
        sub["resolution_pct"] = sub["completed"] / sub["tickets"]
        sub["resolution_pct_display"] = (sub["resolution_pct"] * 100).round(1)
        label = "**" + ", ".join(assignees_in_scope) + "**" if len(assignees_in_scope) <= 3 else f"**{len(assignees_in_scope)} assignees**"

    if not sub.empty:
        last = sub.iloc[-1]
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Last month tickets", int(last["tickets"]), None)
        with c2:
            st.metric("Last month completed", int(last["completed"]), None)
        with c3:
            st.metric("Last month resolution %", f"{last['resolution_pct_display']:.1f}%", None)
        with c4:
            vol_ok = "Yes" if last["tickets"] >= effective_volume_target else "No"
            res_ok = "Yes" if last["resolution_pct"] >= resolution_target else "No"
            st.metric("Targets (Volume / Resolution)", f"{vol_ok} / {res_ok}", None)
        st.caption(
            "Volume target: **{0}** (140 × {1} assignee(s), capped at 420)".format(
                effective_volume_target, len(assignees_in_scope)
            )
        )

    # Table: MoM breakdown (hide assignee column only when exactly one selected)
    display_cols = ["month_label", ASSIGNEE_COL, "tickets", "completed", "resolution_pct_display"]
    if len(assignees_in_scope) == 1:
        display_cols = [c for c in display_cols if c != ASSIGNEE_COL]
    table_df = view[display_cols].copy()
    table_df = table_df.rename(columns={
        "month_label": "Month",
        ASSIGNEE_COL: "Assignee",
        "resolution_pct_display": "Resolution %",
    })
    st.dataframe(table_df, width="stretch", hide_index=True)

    # MoM chart: tickets by month (sum when multiple assignees)
    if len(assignees_in_scope) == 1:
        chart_df = view[["month_label", "tickets"]].copy()
        chart_df = chart_df.rename(columns={"month_label": "Month", "tickets": "Tickets"})
    else:
        chart_df = view.groupby("month_label").agg(tickets=("tickets", "sum")).reset_index()
        chart_df = chart_df.rename(columns={"month_label": "Month", "tickets": "Tickets"})
    if not chart_df.empty:
        st.subheader("Tickets by month")
        st.bar_chart(chart_df.set_index("Month")[["Tickets"]], height=300)

    # Target status (always by assignee so single-assignee view still works)
    view["Volume OK"] = view["tickets"] >= ticket_target
    view["Resolution OK"] = view["resolution_pct"] >= resolution_target
    st.subheader("Target compliance (Volume ≥ 140/assignee, Resolution ≥ {0:.0f}%)".format(resolution_target * 100))
    compliance = view.groupby(ASSIGNEE_COL).agg(
        months=("month", "count"),
        volume_ok=("Volume OK", "sum"),
        resolution_ok=("Resolution OK", "sum"),
    ).reset_index()
    compliance = compliance.rename(columns={ASSIGNEE_COL: "Assignee"})
    compliance["Volume %"] = (compliance["volume_ok"] / compliance["months"] * 100).round(1)
    compliance["Resolution %"] = (compliance["resolution_ok"] / compliance["months"] * 100).round(1)
    st.dataframe(compliance, width="stretch", hide_index=True)

    # Export
    st.download_button(
        "Download MoM breakdown (CSV)",
        data=view.to_csv(index=False),
        file_name="mom_assignee_breakdown.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    run()
