# MoM SMAX Analyst — Dashboard

Web interface to analyse ticket data by assignee with **volume** and **resolution** targets.

## Targets

- **Volume**: 140 tickets per assignee per month (configurable in sidebar).
- **Resolution**: At least 85% of tickets **created** in a given month must be in **Completed** status (configurable in sidebar).

Resolution is computed per month: for tickets created in that month, the share with `Status == "RequestStatusComplete"` must be ≥ 85%.

## Data

- CSV with columns: `CreateTime` (epoch milliseconds), `AssignedToPerson.Name`, `Status`.
- Default file: `Request_20260304_1010302318309310430531382643.csv` in the same folder as `app.py`.

## Run

```bash
cd "c:\Users\tateesa\Box\DIGITAL WORK PLACE\FY2026\Documents\MoM Analyst"
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL shown in the terminal (usually http://localhost:8501).

## Features

- **Assignee filter**: View all assignees or a single assignee.
- **Month range**: Optional “From month” / “To month” to limit the period.
- **MoM table**: Month, assignee, tickets, completed, resolution %.
- **Summary metrics**: Last month tickets, completed, resolution %, and whether volume/resolution targets were met.
- **Target compliance**: Per assignee, count of months meeting volume and resolution targets.
- **Chart**: Bar chart of tickets by month for the current view.
- **Export**: Download the MoM breakdown as CSV.
