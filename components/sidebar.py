# components/sidebar.py
from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html, dcc, dash_table

from backend.data_model import AccountTableModel, IncomeTableModel, SpendingTableModel

ACCOUNT_MODEL = AccountTableModel()
INCOME_MODEL = IncomeTableModel()
SPENDING_MODEL = SpendingTableModel()


def _table_config(model: AccountTableModel):
    columns = []
    dropdowns = {}
    month_fields: list[str] = []
    for col in model.columns:
        col_def = {"name": col.label, "id": col.field}
        if col.kind == "number":
            col_def["type"] = "numeric"
        if col.kind == "select":
            col_def["presentation"] = "dropdown"
            if col.options:
                dropdowns[col.field] = [{"label": opt, "value": opt} for opt in col.options]
            else:
                month_fields.append(col.field)
        columns.append(col_def)
    return columns, dropdowns, month_fields


ACCOUNT_COLUMNS, ACCOUNT_STATIC_DROPDOWNS, ACCOUNT_MONTH_FIELDS = _table_config(ACCOUNT_MODEL)
INCOME_COLUMNS, INCOME_STATIC_DROPDOWNS, INCOME_MONTH_FIELDS = _table_config(INCOME_MODEL)
SPENDING_COLUMNS, SPENDING_STATIC_DROPDOWNS, SPENDING_MONTH_FIELDS = _table_config(SPENDING_MODEL)


def month_dropdown_entries(month_fields: list[str], month_options: list[str]):
    entries = []
    month_opts = [{"label": "", "value": ""}] + [{"label": opt, "value": opt} for opt in month_options]
    for field in month_fields:
        entries.append({"if": {"column_id": field}, "options": month_opts})
    return entries


def _datatable(id_value: str, data, columns, dropdowns, month_fields):
    table = dash_table.DataTable(
        id=id_value,
        data=data,
        columns=columns,
        editable=True,
        row_deletable=True,
        style_table={"height": "auto", "overflowY": "visible"},
        style_header={"backgroundColor": "#222", "color": "#eee", "fontWeight": "bold"},
        style_data={"backgroundColor": "#111", "color": "#eee"},
        dropdown={col: {"options": opts} for col, opts in dropdowns.items()},
        dropdown_conditional=month_dropdown_entries(month_fields, []),
        fill_width=True,
    )
    return html.Div(table, style={"maxHeight": "240px", "overflowY": "auto"})


def build_sidebar():
    return dbc.Card(
        [
            html.H4("New Scenario", className="card-title"),
            dbc.Label("Scenario Name"),
            dbc.Input(id="plan-name", value="MyPlan", type="text"),

            dbc.Label("Plan Start Year"),
            dbc.Input(id="plan-start-year", type="number", value=2024, min=1900, max=2100),

            dbc.Label("Years"),
            dcc.Slider(
                id="plan-years",
                min=1,
                max=10,
                value=5,
                step=1,
                marks={i: str(i) for i in range(1, 11)},
            ),

            dbc.Label(
                [
                    "Tax Rate (%) ",
                    html.Span("25%", id="tax-rate-display", className="badge bg-info text-dark ms-2"),
                ]
            ),
            dcc.Slider(
                id="tax-rate",
                min=0,
                max=60,
                value=25,
                step=0.5,
                marks={i: f"{i}%" for i in range(0, 61, 10)},
                tooltip={"placement": "bottom", "always_visible": False},
            ),

            html.Hr(),

            html.H5("Accounts / Assets / Debts"),
            _datatable(
                "accounts-table",
                ACCOUNT_MODEL.create_default_df().to_dict("records"),
                ACCOUNT_COLUMNS,
                ACCOUNT_STATIC_DROPDOWNS,
                ACCOUNT_MONTH_FIELDS,
            ),
            dbc.Button("Add Account", id="add-account-row", color="secondary", size="sm", className="mt-2"),

            html.Hr(),
            html.H5("Income Streams"),
            _datatable(
                "income-table",
                INCOME_MODEL.create_default_df().to_dict("records"),
                INCOME_COLUMNS,
                INCOME_STATIC_DROPDOWNS,
                INCOME_MONTH_FIELDS,
            ),
            dbc.Button("Add Income", id="add-income-row", color="secondary", size="sm", className="mt-2"),

            html.Hr(),
            html.H5("Expense Streams"),
            _datatable(
                "spending-table",
                SPENDING_MODEL.create_default_df().to_dict("records"),
                SPENDING_COLUMNS,
                SPENDING_STATIC_DROPDOWNS,
                SPENDING_MONTH_FIELDS,
            ),
            dbc.Button("Add Expense", id="add-spending-row", color="secondary", size="sm", className="mt-2"),

            html.Hr(),
            dbc.Button("Add Scenario", id="add-scenario-btn", color="primary", className="mt-2 w-100"),
            dbc.Button("Clear All", id="clear-scenarios-btn", color="secondary", className="mt-2 w-100"),

            html.Hr(),
            dbc.Label("Time Granularity"),
            dcc.RadioItems(
                id="freq",
                options=[
                    {"label": "Monthly", "value": "M"},
                    {"label": "Quarterly", "value": "Q"},
                    {"label": "Yearly", "value": "Y"},
                ],
                value="Q",
                inline=True,
            ),
        ],
        body=True,
    )


def model_blank_row(model):
    """Return an empty row using the column defaults for the model."""
    return {col.field: col.default for col in model.columns}


__all__ = [
    "ACCOUNT_MODEL",
    "INCOME_MODEL",
    "SPENDING_MODEL",
    "ACCOUNT_COLUMNS",
    "INCOME_COLUMNS",
    "SPENDING_COLUMNS",
    "ACCOUNT_STATIC_DROPDOWNS",
    "INCOME_STATIC_DROPDOWNS",
    "SPENDING_STATIC_DROPDOWNS",
    "ACCOUNT_MONTH_FIELDS",
    "INCOME_MONTH_FIELDS",
    "SPENDING_MONTH_FIELDS",
    "month_dropdown_entries",
    "build_sidebar",
    "model_blank_row",
]
