import dash
from dash import dash_table, html

app = dash.Dash(__name__)

TEST_DROPDOWN_TABLE = dash_table.DataTable(
    id="test-dropdown-table",
    data=[{"Label": "Example", "Category": ""}],
    columns=[
        {"name": "Label", "id": "Label"},
        {"name": "Category", "id": "Category", "presentation": "dropdown"},
    ],
    dropdown={
        "Category": {
            "options": [
                {"label": "cash", "value": "cash"},
                {"label": "asset", "value": "asset"},
                {"label": "investment", "value": "investment"},
            ]
        }
    },
    editable=True,
    style_table={"maxHeight": "120px", "overflowY": "auto"},
    style_data={"backgroundColor": "#111", "color": "#eee"},
)

app.layout = html.Div(TEST_DROPDOWN_TABLE)

if __name__ == "__main__":
    app.run_server(debug=True)
