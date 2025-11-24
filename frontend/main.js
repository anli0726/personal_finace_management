const API_BASE =
  window.APP_CONFIG?.apiBase ??
  document.body?.dataset?.apiBase ??
  "http://localhost:8000";

const FALLBACK_SCHEMA = {
  planDefaults: {
    name: "MyPlan",
    startYear: 2024,
    years: 5,
    taxRate: 25,
    freq: "Q",
  },
  freqOptions: [
    { label: "Monthly", value: "M" },
    { label: "Quarterly", value: "Q" },
    { label: "Yearly", value: "Y" },
  ],
  accounts: {
    name: "accounts",
    columns: [
      { field: "Name", label: "Name", kind: "text", default: "" },
      {
        field: "Category",
        label: "Category",
        kind: "select",
        default: "asset",
        options: ["cash", "asset", "investment", "debt", "liability"],
      },
      {
        field: "Principal",
        label: "Amount (USD)",
        kind: "number",
        default: 0,
        min: 0,
        step: 500,
        format: "%.2f",
      },
      { field: "APR (%)", label: "APR (%)", kind: "number", default: 0, step: 0.25 },
      {
        field: "Interest Rate (%)",
        label: "Interest Rate (%)",
        kind: "number",
        default: 0,
        step: 0.25,
      },
      { field: "Start Month", label: "Start Month", kind: "select", default: "" },
      {
        field: "End Month",
        label: "End Month (empty=all)",
        kind: "select",
        default: "",
      },
      {
        field: "Action at End",
        label: "Action at End",
        kind: "select",
        default: "keep",
        options: ["keep", "liquidate_to_cash", "drop"],
      },
    ],
    defaults: [
      {
        Name: "Cash",
        Category: "cash",
        Principal: 182000,
        "APR (%)": 1.5,
        "Interest Rate (%)": 0,
        "Start Month": "",
        "End Month": "",
        "Action at End": "keep",
      },
    ],
  },
  incomes: {
    name: "income",
    columns: [
      { field: "Name", label: "Name", kind: "text", default: "" },
      {
        field: "Category",
        label: "Category",
        kind: "select",
        default: "salary",
        options: ["salary", "bonus", "rental", "business", "other"],
      },
      {
        field: "Annual Amount",
        label: "Annual Amount (USD)",
        kind: "number",
        default: 0,
        min: 0,
        step: 1000,
        format: "%.2f",
      },
      { field: "Start Month", label: "Start Month", kind: "select", default: "" },
      {
        field: "End Month",
        label: "End Month (empty=all)",
        kind: "select",
        default: "",
      },
    ],
    defaults: [
      {
        Name: "Annual Income",
        Category: "salary",
        "Annual Amount": 30000,
        "Start Month": "",
        "End Month": "",
      },
    ],
  },
  spendings: {
    name: "spending",
    columns: [
      { field: "Name", label: "Name", kind: "text", default: "" },
      {
        field: "Category",
        label: "Category",
        kind: "select",
        default: "living",
        options: ["living", "parents", "debt", "health", "other"],
      },
      {
        field: "Annual Amount",
        label: "Annual Amount (USD)",
        kind: "number",
        default: 0,
        min: 0,
        step: 1000,
        format: "%.2f",
      },
      { field: "Start Month", label: "Start Month", kind: "select", default: "" },
      {
        field: "End Month",
        label: "End Month (empty=all)",
        kind: "select",
        default: "",
      },
    ],
    defaults: [
      {
        Name: "Personal Expense",
        Category: "living",
        "Annual Amount": 67200,
        "Start Month": "",
        "End Month": "",
      },
    ],
  },
};

let schema;
let currentFreq = "Q";
let accountsTable;
let incomeTable;
let spendingTable;
let netWorthChart;
let liquidChart;
let backendAvailable = true;

const statusBanner = document.getElementById("status-banner");
const planNameInput = document.getElementById("plan-name");
const planStartYearInput = document.getElementById("plan-start-year");
const planYearsInput = document.getElementById("plan-years");
const taxRateInput = document.getElementById("tax-rate");
const freqSelect = document.getElementById("freq");

async function fetchJSON(path, options = {}) {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!response.ok) {
      let errorMessage = response.statusText;
      try {
        const body = await response.json();
        if (body?.error) {
          errorMessage = body.error;
        }
      } catch (err) {
        // ignore JSON parse failure
      }
      throw new Error(errorMessage);
    }
    if (response.status === 204) {
      return {};
    }
    return response.json();
  } catch (error) {
    throw new Error(error.message || "Unable to reach backend.");
  }
}

function setStatus(message, variant = "") {
  statusBanner.textContent = message;
  statusBanner.className = `status${variant ? ` ${variant}` : ""}`;
}

function populatePlanDefaults(defaults) {
  planNameInput.value = defaults.name;
  planStartYearInput.value = defaults.startYear;
  planYearsInput.value = defaults.years;
  taxRateInput.value = defaults.taxRate;
}

function initFreqOptions(options, defaultValue) {
  freqSelect.innerHTML = "";
  options.forEach((opt) => {
    const option = document.createElement("option");
    option.value = opt.value;
    option.textContent = opt.label;
    freqSelect.appendChild(option);
  });
  freqSelect.value = defaultValue;
}

function generateMonths(startYear, years) {
  const months = [];
  const start = parseInt(startYear, 10);
  const span = parseInt(years, 10);
  if (!start || !span) {
    return months;
  }
  for (let year = start; year < start + span; year += 1) {
    for (let month = 1; month <= 12; month += 1) {
      const label = `${year}-${String(month).padStart(2, "0")}`;
      months.push(label);
    }
  }
  return months;
}

function createTableManager(containerId, model) {
  const container = document.getElementById(containerId);
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const tbody = document.createElement("tbody");
  table.appendChild(thead);
  table.appendChild(tbody);
  container.innerHTML = "";
  container.appendChild(table);

  const state = {
    rows: model.defaults.map((row) => ({ ...row })),
    monthOptions: [],
  };

  function ensureRowShape(row = {}) {
    const shaped = {};
    model.columns.forEach((col) => {
      const value = Object.prototype.hasOwnProperty.call(row, col.field) ? row[col.field] : col.default ?? "";
      shaped[col.field] = value ?? "";
    });
    return shaped;
  }

  state.rows = state.rows.map(ensureRowShape);

  function renderHeader() {
    const headerRow = document.createElement("tr");
    model.columns.forEach((col) => {
      const th = document.createElement("th");
      th.textContent = col.label;
      headerRow.appendChild(th);
    });
    const actionsTh = document.createElement("th");
    actionsTh.textContent = "Actions";
    actionsTh.className = "table-actions";
    headerRow.appendChild(actionsTh);
    thead.innerHTML = "";
    thead.appendChild(headerRow);
  }

  function handleChange(rowIndex, field, value) {
    state.rows[rowIndex][field] = value;
  }

  function createInput(col, rowIndex, value) {
    if (col.kind === "select") {
      const select = document.createElement("select");
      const opts = (col.options && col.options.length ? col.options : state.monthOptions) ?? [];
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "—";
      select.appendChild(placeholder);
      opts.forEach((opt) => {
        const option = document.createElement("option");
        option.value = typeof opt === "string" ? opt : opt.value ?? opt.label;
        option.textContent = typeof opt === "string" ? opt : opt.label ?? opt.value;
        select.appendChild(option);
      });
      select.value = value ?? "";
      select.addEventListener("change", (event) => handleChange(rowIndex, col.field, event.target.value));
      return select;
    }
    const input = document.createElement("input");
    input.type = col.kind === "number" ? "number" : "text";
    if (col.kind === "number") {
      if (col.min !== null && col.min !== undefined) {
        input.min = col.min;
      }
      if (col.step) {
        input.step = col.step;
      }
    }
    input.value = value ?? "";
    input.addEventListener("input", (event) => handleChange(rowIndex, col.field, event.target.value));
    return input;
  }

  function renderBody() {
    tbody.innerHTML = "";
    if (!state.rows.length) {
      const emptyRow = document.createElement("tr");
      const emptyCell = document.createElement("td");
      emptyCell.colSpan = model.columns.length + 1;
      emptyCell.textContent = "No rows yet.";
      emptyCell.style.textAlign = "center";
      emptyCell.style.color = "var(--muted)";
      emptyRow.appendChild(emptyCell);
      tbody.appendChild(emptyRow);
      return;
    }

    state.rows.forEach((row, rowIndex) => {
      const tr = document.createElement("tr");
      model.columns.forEach((col) => {
        const td = document.createElement("td");
        const input = createInput(col, rowIndex, row[col.field]);
        td.appendChild(input);
        tr.appendChild(td);
      });
      const actionsTd = document.createElement("td");
      actionsTd.className = "table-actions";
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "link-btn";
      removeBtn.textContent = "Remove";
      removeBtn.addEventListener("click", () => {
        state.rows.splice(rowIndex, 1);
        renderBody();
      });
      actionsTd.appendChild(removeBtn);
      tr.appendChild(actionsTd);
      tbody.appendChild(tr);
    });
  }

  renderHeader();
  renderBody();

  return {
    addRow() {
      const newRow = ensureRowShape();
      state.rows.push(newRow);
      renderBody();
    },
    getRows() {
      return state.rows;
    },
    setMonthOptions(months) {
      state.monthOptions = months ?? [];
      renderBody();
    },
  };
}

function collectPlanValues() {
  return {
    name: planNameInput.value.trim() || "Scenario",
    startYear: parseInt(planStartYearInput.value, 10) || 2024,
    years: parseInt(planYearsInput.value, 10) || 1,
    taxRate: parseFloat(taxRateInput.value) || 0,
    freq: currentFreq,
  };
}

function renderScenarioList(names) {
  const listEl = document.getElementById("scenario-list");
  if (!names?.length) {
    listEl.textContent = "No scenarios";
    return;
  }
  listEl.textContent = names.join(", ");
}

function prepareSeries(records, valueField) {
  if (!records?.length) {
    return { labels: [], datasets: [] };
  }
  const labelEntries = new Map();
  records.forEach((record) => {
    if (!labelEntries.has(record.PeriodValue)) {
      labelEntries.set(record.PeriodValue, record.Period);
    }
  });
  const sortedLabels = Array.from(labelEntries.entries())
    .sort((a, b) => a[0] - b[0])
    .map((entry) => ({ value: entry[0], label: entry[1] }));

  const indexLookup = new Map();
  sortedLabels.forEach((entry, idx) => {
    indexLookup.set(entry.value, idx);
  });

  const scenarioSeries = new Map();
  records.forEach((record) => {
    if (!scenarioSeries.has(record.Scenario)) {
      scenarioSeries.set(record.Scenario, new Array(sortedLabels.length).fill(null));
    }
    const series = scenarioSeries.get(record.Scenario);
    const targetIndex = indexLookup.get(record.PeriodValue);
    series[targetIndex] = record[valueField];
  });

  const palette = ["#3dd598", "#62dafb", "#f4bf4f", "#ff6b6b", "#a097f4", "#4dd0e1", "#f06292"];
  const datasets = Array.from(scenarioSeries.entries()).map(([scenario, seriesValues], idx) => ({
    label: scenario,
    data: seriesValues,
    borderColor: palette[idx % palette.length],
    backgroundColor: palette[idx % palette.length],
    tension: 0.3,
    fill: false,
    spanGaps: true,
  }));

  return { labels: sortedLabels.map((entry) => entry.label), datasets };
}

function updateLineChart(chartRef, canvasId, config, title) {
  const ctx = document.getElementById(canvasId).getContext("2d");
  if (!chartRef) {
    return new Chart(ctx, {
      type: "line",
      data: {
        labels: config.labels,
        datasets: config.datasets,
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
          },
          title: {
            display: true,
            text: title,
          },
        },
        scales: {
          x: {
            ticks: { maxRotation: 45, minRotation: 0 },
          },
          y: {
            ticks: {
              callback: (value) => `$${Number(value).toLocaleString()}`,
            },
          },
        },
      },
    });
  }
  chartRef.data.labels = config.labels;
  chartRef.data.datasets = config.datasets;
  chartRef.options.plugins.title.text = title;
  chartRef.update();
  return chartRef;
}

function renderAggregateTable(records) {
  const container = document.getElementById("aggregate-table");
  container.innerHTML = "";
  if (!records?.length) {
    container.textContent = "Run a scenario to see tabular data.";
    return;
  }
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  thead.innerHTML = `
    <tr>
      <th>Scenario</th>
      <th>Period</th>
      <th>Net Worth</th>
      <th>Liquid</th>
    </tr>`;
  const tbody = document.createElement("tbody");
  records.forEach((record) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${record.Scenario}</td>
      <td>${record.Period}</td>
      <td>${Number(record.NetWorth || 0).toLocaleString()}</td>
      <td>${Number(record.Liquid || 0).toLocaleString()}</td>
    `;
    tbody.appendChild(tr);
  });
  table.appendChild(thead);
  table.appendChild(tbody);
  container.appendChild(table);
}

function renderCharts(payload) {
  renderScenarioList(payload.scenarios || []);
  renderAggregateTable(payload.data || []);
  const netCfg = prepareSeries(payload.data, "NetWorth");
  const liqCfg = prepareSeries(payload.data, "Liquid");
  netWorthChart = updateLineChart(netWorthChart, "networth-chart", netCfg, `Net Worth (${payload.freq})`);
  liquidChart = updateLineChart(liquidChart, "liquid-chart", liqCfg, `Liquid Assets (${payload.freq})`);
}

async function refreshScenarios() {
  if (!backendAvailable) {
    renderCharts({ scenarios: [], data: [], freq: currentFreq });
    return;
  }
  try {
    const data = await fetchJSON(`/api/scenarios?freq=${currentFreq}`);
    renderCharts(data);
  } catch (error) {
    console.warn("Failed to refresh scenarios:", error);
    backendAvailable = false;
    renderCharts({ scenarios: [], data: [], freq: currentFreq });
    setStatus("Backend unavailable. Using built-in defaults for editing.", "error");
  }
}

async function submitScenario() {
  if (!backendAvailable) {
    setStatus("Backend not running. Start the API server to simulate.", "error");
    return;
  }
  setStatus("Running simulation...");
  try {
    const planValues = collectPlanValues();
    const payload = {
      ...planValues,
      accounts: accountsTable.getRows(),
      incomes: incomeTable.getRows(),
      spendings: spendingTable.getRows(),
    };
    const data = await fetchJSON("/api/scenarios", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderCharts(data);
    setStatus("Scenario added.", "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function clearScenarios() {
  if (!backendAvailable) {
    setStatus("Backend not running. Nothing to clear.", "error");
    return;
  }
  try {
    await fetchJSON("/api/scenarios", { method: "DELETE" });
    await refreshScenarios();
    setStatus("Cleared all scenarios.", "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

function refreshMonths() {
  const months = generateMonths(planStartYearInput.value, planYearsInput.value);
  accountsTable.setMonthOptions(months);
  incomeTable.setMonthOptions(months);
  spendingTable.setMonthOptions(months);
}

function attachEventListeners() {
  document.getElementById("add-account-row").addEventListener("click", () => accountsTable.addRow());
  document.getElementById("add-income-row").addEventListener("click", () => incomeTable.addRow());
  document.getElementById("add-spending-row").addEventListener("click", () => spendingTable.addRow());
  document.getElementById("submit-scenario").addEventListener("click", submitScenario);
  document.getElementById("clear-scenarios").addEventListener("click", clearScenarios);
  planStartYearInput.addEventListener("input", refreshMonths);
  planYearsInput.addEventListener("input", refreshMonths);
  freqSelect.addEventListener("change", (event) => {
    currentFreq = event.target.value;
    refreshScenarios();
  });
}

async function bootstrap() {
  setStatus("Loading models...");
  try {
    schema = await fetchJSON("/api/schema");
    backendAvailable = true;
  } catch (error) {
    console.warn("Falling back to built-in schema:", error);
    backendAvailable = false;
    schema = FALLBACK_SCHEMA;
  }
  currentFreq = schema.planDefaults.freq;
  populatePlanDefaults(schema.planDefaults);
  initFreqOptions(schema.freqOptions, schema.planDefaults.freq);
  accountsTable = createTableManager("accounts-table", schema.accounts);
  incomeTable = createTableManager("income-table", schema.incomes);
  spendingTable = createTableManager("spending-table", schema.spendings);
  attachEventListeners();
  refreshMonths();
  if (backendAvailable) {
    try {
      await refreshScenarios();
      setStatus("Ready", "success");
    } catch (error) {
      console.warn("Failed to load scenarios:", error);
      backendAvailable = false;
      renderCharts({ scenarios: [], data: [], freq: currentFreq });
      setStatus("Backend unavailable. Using built-in defaults for editing.", "error");
    }
  } else {
    renderCharts({ scenarios: [], data: [], freq: currentFreq });
    setStatus("Backend unavailable. Using built-in defaults for editing.", "error");
  }
}

document.addEventListener("DOMContentLoaded", bootstrap);
