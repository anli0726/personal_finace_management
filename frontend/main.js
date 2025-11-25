const API_BASE =
  window.APP_CONFIG?.apiBase ??
  document.body?.dataset?.apiBase ??
  "http://localhost:8000";

const MIN_PANEL_WIDTH = 280;
const MIN_PANEL_HEIGHT = 200;

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
let gridContainer = null;
let dragState = null;
let resizeState = null;
let savedPlanNames = [];
const PANEL_LAYOUT_KEY = "panelLayout";
const currencyFormat = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function normalizeCurrencyValue(value) {
  if (value === null || value === undefined) {
    return 0;
  }
  if (typeof value === "string") {
    const cleaned = value.replace(/,/g, "");
    const parsed = Number(cleaned);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  const num = Number(value);
  if (Number.isFinite(num)) {
    return num;
  }
  return 0;
}

const statusBanner = document.getElementById("status-banner");
const planNameInput = document.getElementById("plan-name");
const planStartYearInput = document.getElementById("plan-start-year");
const planYearsInput = document.getElementById("plan-years");
const taxRateInput = document.getElementById("tax-rate");
const freqSelect = document.getElementById("freq");
const planFreqSelect = document.getElementById("plan-freq");
const planSelectInput = document.getElementById("saved-plans");
const savePlanButton = document.getElementById("save-plan-btn");
const saveNewPlanButton = document.getElementById("save-new-plan-btn");
const loadPlanButton = document.getElementById("load-plan-btn");
const deletePlanButton = document.getElementById("delete-plan-btn");
const saveLayoutButton = document.getElementById("save-layout-btn");
const addPlanButton = document.getElementById("add-plan-btn");
const planEditorSection = document.getElementById("plan-editor-panel");
const runSimulationButton = document.getElementById("run-simulation-btn");

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
      backendAvailable = true;
      return {};
    }
    const text = await response.text();
    let data = {};
    if (text) {
      try {
        data = JSON.parse(text);
      } catch (err) {
        backendAvailable = false;
        throw new Error(`Invalid JSON response: ${err.message}`);
      }
    }
    backendAvailable = true;
    return data;
  } catch (error) {
    backendAvailable = false;
    throw new Error(error.message || "Unable to reach backend.");
  }
}

function setStatus(message, variant = "") {
  statusBanner.textContent = message;
  statusBanner.className = `status${variant ? ` ${variant}` : ""}`;
}

function showPlanEditor() {
  if (planEditorSection) {
    planEditorSection.classList.remove("is-hidden");
    planEditorSection.hidden = false;
    planEditorSection.removeAttribute("aria-hidden");
  }
}

function hidePlanEditor() {
  if (planEditorSection) {
    planEditorSection.classList.add("is-hidden");
    planEditorSection.hidden = true;
    planEditorSection.setAttribute("aria-hidden", "true");
  }
}

function isPlanEditorVisible() {
  return planEditorSection ? !planEditorSection.hidden && !planEditorSection.classList.contains("is-hidden") : true;
}

function requirePlanEditorVisible() {
  if (!isPlanEditorVisible()) {
    setStatus("Add or load a plan before continuing.", "error");
    return false;
  }
  return true;
}

function populatePlanDefaults(defaults) {
  planNameInput.value = defaults.name;
  planStartYearInput.value = defaults.startYear;
  planYearsInput.value = defaults.years;
  taxRateInput.value = defaults.taxRate;
}

function initFreqOptions(options, defaultValue) {
  const selects = [freqSelect, planFreqSelect].filter(Boolean);
  selects.forEach((selectEl) => {
    selectEl.innerHTML = "";
    options.forEach((opt) => {
      const option = document.createElement("option");
      option.value = opt.value;
      option.textContent = opt.label;
      selectEl.appendChild(option);
    });
    selectEl.value = defaultValue;
  });
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

function initPanelInteractivity() {
  gridContainer = document.querySelector(".app-grid");
  if (!gridContainer) {
    return;
  }
  const panels = gridContainer.querySelectorAll(".panel");
  panels.forEach((panel) => {
    if (panel.dataset.interactive === "true") {
      return;
    }
    panel.dataset.interactive = "true";
    const dragHandle = document.createElement("button");
    dragHandle.type = "button";
    dragHandle.className = "panel-handle";
    dragHandle.title = "Drag to move section";
    dragHandle.setAttribute("aria-label", "Drag section");
    dragHandle.textContent = "::";
    panel.appendChild(dragHandle);

    const resizeHandle = document.createElement("div");
    resizeHandle.className = "panel-resize-handle";
    resizeHandle.title = "Drag to resize section";
    panel.appendChild(resizeHandle);

    enablePanelDrag(panel, dragHandle);
    enablePanelResize(panel, resizeHandle);
  });
}

function enablePanelDrag(panel, handle) {
  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    dragState = {
      panel,
      handle,
      pointerId: event.pointerId,
    };
    panel.classList.add("dragging");
    document.body.classList.add("is-gesturing");
    handle.setPointerCapture(event.pointerId);
    window.addEventListener("pointermove", onPanelDragMove);
    window.addEventListener("pointerup", stopPanelDrag);
    window.addEventListener("pointercancel", stopPanelDrag);
  });
}

function onPanelDragMove(event) {
  if (!dragState || event.pointerId !== dragState.pointerId) {
    return;
  }
  const hovered = document.elementFromPoint(event.clientX, event.clientY);
  const targetPanel = hovered?.closest(".panel");
  const containerRect = gridContainer.getBoundingClientRect();

  if (!targetPanel || targetPanel === dragState.panel || !gridContainer.contains(targetPanel)) {
    if (event.clientY > containerRect.bottom - 20) {
      gridContainer.appendChild(dragState.panel);
    }
    return;
  }
  const rect = targetPanel.getBoundingClientRect();
  const shouldInsertBefore = event.clientY < rect.top + rect.height / 2;
  if (shouldInsertBefore) {
    gridContainer.insertBefore(dragState.panel, targetPanel);
  } else {
    gridContainer.insertBefore(dragState.panel, targetPanel.nextElementSibling);
  }
}

function stopPanelDrag(event) {
  if (!dragState || event.pointerId !== dragState.pointerId) {
    return;
  }
  dragState.handle.releasePointerCapture(event.pointerId);
  dragState.panel.classList.remove("dragging");
  document.body.classList.remove("is-gesturing");
  window.removeEventListener("pointermove", onPanelDragMove);
  window.removeEventListener("pointerup", stopPanelDrag);
  window.removeEventListener("pointercancel", stopPanelDrag);
  dragState = null;
  persistPanelLayout(false);
}

function enablePanelResize(panel, handle) {
  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    const rect = panel.getBoundingClientRect();
    resizeState = {
      panel,
      handle,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      startWidth: rect.width,
      startHeight: rect.height,
    };
    panel.classList.add("resizing");
    document.body.classList.add("is-gesturing");
    handle.setPointerCapture(event.pointerId);
    window.addEventListener("pointermove", onPanelResizeMove);
    window.addEventListener("pointerup", stopPanelResize);
    window.addEventListener("pointercancel", stopPanelResize);
  });
}

function onPanelResizeMove(event) {
  if (!resizeState || event.pointerId !== resizeState.pointerId) {
    return;
  }
  const deltaX = event.clientX - resizeState.startX;
  const deltaY = event.clientY - resizeState.startY;
  const newWidth = Math.max(MIN_PANEL_WIDTH, resizeState.startWidth + deltaX);
  const newHeight = Math.max(MIN_PANEL_HEIGHT, resizeState.startHeight + deltaY);
  const panel = resizeState.panel;
  panel.style.flex = "0 0 auto";
  panel.style.width = `${newWidth}px`;
  panel.style.height = `${newHeight}px`;
  panel.classList.add("panel-custom-size");
}

function stopPanelResize(event) {
  if (!resizeState || event.pointerId !== resizeState.pointerId) {
    return;
  }
  resizeState.handle.releasePointerCapture(event.pointerId);
  resizeState.panel.classList.remove("resizing");
  document.body.classList.remove("is-gesturing");
  window.removeEventListener("pointermove", onPanelResizeMove);
  window.removeEventListener("pointerup", stopPanelResize);
  window.removeEventListener("pointercancel", stopPanelResize);
  resizeState = null;
  persistPanelLayout(false);
}

function createTableManager(containerId, model) {
  const container = document.getElementById(containerId);
  if (!container) {
    throw new Error(`Missing container for ${containerId}`);
  }
  const table = document.createElement("table");
  const colgroup = document.createElement("colgroup");
  const thead = document.createElement("thead");
  const tbody = document.createElement("tbody");
  container.innerHTML = "";
  table.appendChild(colgroup);
  table.appendChild(thead);
  table.appendChild(tbody);
  container.appendChild(table);
  const tableResizeHandle = document.createElement("div");
  tableResizeHandle.className = "table-resize-handle";
  container.appendChild(tableResizeHandle);

  const state = {
    rows: model.defaults.map((row) => ({ ...row })),
    monthOptions: [],
    colWidths: [],
  };
  let columnResizeState = null;
  let tableResizeState = null;

  const baseWidth = Math.max(120, Math.floor(((container.clientWidth || 640) - 32) / model.columns.length));
  state.colWidths = model.columns.map(() => baseWidth);

  function renderColgroup() {
    colgroup.innerHTML = "";
    state.colWidths.forEach((width) => {
      const col = document.createElement("col");
      col.style.width = `${width}px`;
      colgroup.appendChild(col);
    });
    const actionsCol = document.createElement("col");
    actionsCol.style.width = "110px";
    colgroup.appendChild(actionsCol);
  }
  renderColgroup();

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
    model.columns.forEach((col, colIndex) => {
      const th = document.createElement("th");
      const labelSpan = document.createElement("span");
      labelSpan.textContent = col.label;
      th.appendChild(labelSpan);
      if (colIndex < model.columns.length - 1) {
        const resizer = document.createElement("span");
        resizer.className = "col-resizer";
        resizer.addEventListener("pointerdown", (event) => startColumnResize(event, colIndex, resizer));
        th.appendChild(resizer);
      }
      headerRow.appendChild(th);
    });
    const actionsTh = document.createElement("th");
    actionsTh.textContent = "Actions";
    actionsTh.className = "table-actions";
    headerRow.appendChild(actionsTh);
    thead.innerHTML = "";
    thead.appendChild(headerRow);
  }

  function startColumnResize(event, colIndex, resizerEl) {
    event.preventDefault();
    columnResizeState = {
      colIndex,
      pointerId: event.pointerId,
      startX: event.clientX,
      startWidth: state.colWidths[colIndex],
      resizer: resizerEl,
    };
    resizerEl.classList.add("active");
    resizerEl.setPointerCapture(event.pointerId);
    window.addEventListener("pointermove", onColumnResizeMove);
    window.addEventListener("pointerup", stopColumnResize);
    window.addEventListener("pointercancel", stopColumnResize);
  }

  function onColumnResizeMove(event) {
    if (!columnResizeState || event.pointerId !== columnResizeState.pointerId) {
      return;
    }
    const deltaX = event.clientX - columnResizeState.startX;
    const newWidth = Math.max(90, columnResizeState.startWidth + deltaX);
    state.colWidths[columnResizeState.colIndex] = newWidth;
    renderColgroup();
  }

  function stopColumnResize(event) {
    if (!columnResizeState || event.pointerId !== columnResizeState.pointerId) {
      return;
    }
    columnResizeState.resizer.releasePointerCapture(event.pointerId);
    columnResizeState.resizer.classList.remove("active");
    window.removeEventListener("pointermove", onColumnResizeMove);
    window.removeEventListener("pointerup", stopColumnResize);
    window.removeEventListener("pointercancel", stopColumnResize);
    columnResizeState = null;
  }

  function startTableResize(event) {
    event.preventDefault();
    const rect = container.getBoundingClientRect();
    container.style.maxHeight = `${rect.height}px`;
    tableResizeState = {
      pointerId: event.pointerId,
      startY: event.clientY,
      startHeight: rect.height,
    };
    tableResizeHandle.setPointerCapture(event.pointerId);
    window.addEventListener("pointermove", onTableResizeMove);
    window.addEventListener("pointerup", stopTableResize);
    window.addEventListener("pointercancel", stopTableResize);
  }

  function onTableResizeMove(event) {
    if (!tableResizeState || event.pointerId !== tableResizeState.pointerId) {
      return;
    }
    const deltaY = event.clientY - tableResizeState.startY;
    const newHeight = Math.max(200, tableResizeState.startHeight + deltaY);
    container.style.maxHeight = `${newHeight}px`;
  }

  function stopTableResize(event) {
    if (!tableResizeState || event.pointerId !== tableResizeState.pointerId) {
      return;
    }
    tableResizeHandle.releasePointerCapture(event.pointerId);
    window.removeEventListener("pointermove", onTableResizeMove);
    window.removeEventListener("pointerup", stopTableResize);
    window.removeEventListener("pointercancel", stopTableResize);
    tableResizeState = null;
  }

  tableResizeHandle.addEventListener("pointerdown", startTableResize);

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
  const labelLower = col.label.toLowerCase();
  const isCurrency =
    labelLower.includes("amount") ||
    labelLower.includes("principal") ||
    labelLower.includes("usd");
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
  if (isCurrency) {
    const wrapper = document.createElement("label");
    wrapper.className = "currency-input";
    const prefix = document.createElement("span");
    prefix.textContent = "$";
    input.step = input.step || 0.01;
    input.min = input.min || 0;
    wrapper.appendChild(prefix);
    wrapper.appendChild(input);
    return wrapper;
  }
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
    setRows(newRows) {
      state.rows = (newRows || []).map(ensureRowShape);
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

function buildPlanPayload() {
  const base = collectPlanValues();
  return {
    ...base,
    accounts: accountsTable.getRows(),
    incomes: incomeTable.getRows(),
    spendings: spendingTable.getRows(),
  };
}

function cloneModelDefaults(modelConfig) {
  return (modelConfig?.defaults || []).map((row) => ({ ...row }));
}

function getDefaultPlanPayload() {
  const defaults = schema?.planDefaults ?? FALLBACK_SCHEMA.planDefaults;
  return {
    name: defaults.name,
    startYear: defaults.startYear,
    years: defaults.years,
    taxRate: defaults.taxRate,
    freq: defaults.freq,
    accounts: cloneModelDefaults(schema?.accounts ?? FALLBACK_SCHEMA.accounts),
    incomes: cloneModelDefaults(schema?.incomes ?? FALLBACK_SCHEMA.incomes),
    spendings: cloneModelDefaults(schema?.spendings ?? FALLBACK_SCHEMA.spendings),
  };
}

function applyPlanPayload(plan) {
  if (!plan) {
    return;
  }
  if (plan.name) {
    planNameInput.value = plan.name;
  }
  if (plan.startYear !== undefined) {
    planStartYearInput.value = plan.startYear;
  }
  if (plan.years !== undefined) {
    planYearsInput.value = plan.years;
  }
  if (plan.taxRate !== undefined) {
    taxRateInput.value = plan.taxRate;
  }
  if (plan.freq) {
    currentFreq = plan.freq;
    if (planFreqSelect) {
      planFreqSelect.value = plan.freq;
    }
    if (freqSelect) {
      freqSelect.value = plan.freq;
    }
  }
  accountsTable.setRows(plan.accounts || []);
  incomeTable.setRows(plan.incomes || []);
  spendingTable.setRows(plan.spendings || []);
  refreshMonths();
  showPlanEditor();
}

async function fetchSavedPlans() {
  if (!planSelectInput) {
    return;
  }
  try {
    const data = await fetchJSON("/api/plans");
    updatePlanSelect(data.plans || []);
  } catch (error) {
    console.warn("Unable to load saved plans:", error);
  }
}

function updatePlanSelect(planNames, preferred) {
  if (!planSelectInput) {
    return;
  }
  savedPlanNames = planNames;
  const current = preferred ?? planSelectInput.value;
  planSelectInput.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select a plan";
  planSelectInput.appendChild(placeholder);
  planNames.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    planSelectInput.appendChild(option);
  });
  if (current && planNames.includes(current)) {
    planSelectInput.value = current;
  } else {
    planSelectInput.value = "";
  }
}

async function persistPlan(requireUniqueName = false) {
  if (!planSelectInput) {
    return;
  }
  if (!requirePlanEditorVisible()) {
    return;
  }
  try {
    const payload = buildPlanPayload();
    if (requireUniqueName && savedPlanNames.includes(payload.name)) {
      setStatus(`Plan "${payload.name}" already exists. Choose a new name.`, "error");
      return;
    }
    const response = await fetchJSON("/api/plans", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    updatePlanSelect(response.plans || [], payload.name);
    if (planSelectInput) {
      planSelectInput.value = payload.name;
    }
    await fetchSavedPlans();
    if (response.plan) {
      applyPlanPayload(response.plan);
    }
    setStatus(requireUniqueName ? "Plan saved as new." : "Plan saved.", "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function handleSavePlan() {
  await persistPlan(false);
}

async function handleSavePlanAsNew() {
  await persistPlan(true);
}

async function handleLoadPlan() {
  if (!planSelectInput || !planSelectInput.value) {
    setStatus("Select a saved plan to load.", "error");
    return;
  }
  try {
    const plan = await fetchJSON(`/api/plans/${encodeURIComponent(planSelectInput.value)}`);
    applyPlanPayload(plan);
    setStatus(`Loaded plan "${planSelectInput.value}".`, "success");
    if (backendAvailable) {
      await runSimulation(true);
    }
  } catch (error) {
    setStatus(error.message, "error");
  }
}

async function handleDeletePlan() {
  if (!planSelectInput || !planSelectInput.value) {
    setStatus("Select a saved plan to delete.", "error");
    return;
  }
  const name = planSelectInput.value;
  try {
    const response = await fetchJSON(`/api/plans/${encodeURIComponent(name)}`, {
      method: "DELETE",
    });
    updatePlanSelect(response.plans || []);
    setStatus(`Deleted plan "${name}".`, "success");
  } catch (error) {
    setStatus(error.message, "error");
  }
}

function handleAddPlan() {
  const defaults = getDefaultPlanPayload();
  if (planSelectInput) {
    planSelectInput.value = "";
  }
  applyPlanPayload(defaults);
  setStatus("Default plan loaded. Customize and save when ready.", "success");
}

function capturePanelLayout() {
  if (!gridContainer) {
    return [];
  }
  const panels = Array.from(gridContainer.querySelectorAll(".panel"));
  return panels.map((panel, index) => ({
    id: panel.dataset.panelId || `panel-${index}`,
    order: index,
    width: panel.style.width || "",
    height: panel.style.height || "",
    custom: panel.classList.contains("panel-custom-size"),
  }));
}

function applyPanelLayout(layout) {
  if (!gridContainer || !Array.isArray(layout) || layout.length === 0) {
    return;
  }
  const lookup = new Map();
  layout.forEach((item, idx) => {
    lookup.set(item.id, { ...item, order: typeof item.order === "number" ? item.order : idx });
  });

  const panels = Array.from(gridContainer.querySelectorAll(".panel"));
  panels
    .sort((a, b) => {
      const aId = a.dataset.panelId;
      const bId = b.dataset.panelId;
      const aOrder = lookup.has(aId) ? lookup.get(aId).order : Number.MAX_SAFE_INTEGER;
      const bOrder = lookup.has(bId) ? lookup.get(bId).order : Number.MAX_SAFE_INTEGER;
      return aOrder - bOrder;
    })
    .forEach((panel) => gridContainer.appendChild(panel));

  layout.forEach((item) => {
    const panel = gridContainer.querySelector(`[data-panel-id="${item.id}"]`);
    if (!panel) {
      return;
    }
    panel.style.width = item.width || "";
    panel.style.height = item.height || "";
    if (item.width || item.height || item.custom) {
      panel.classList.add("panel-custom-size");
    } else {
      panel.classList.remove("panel-custom-size");
    }
  });
}

function persistPanelLayout(remote = false) {
  const layout = capturePanelLayout();
  try {
    localStorage.setItem(PANEL_LAYOUT_KEY, JSON.stringify(layout));
  } catch (error) {
    console.warn("Failed to store layout locally:", error);
  }
  if (remote && backendAvailable) {
    fetchJSON("/api/layout", {
      method: "POST",
      body: JSON.stringify({ layout }),
    })
      .then(() => setStatus("Layout saved.", "success"))
      .catch((error) => {
        console.warn("Failed to save layout remotely:", error);
        setStatus(error.message, "error");
      });
  }
}

async function loadPanelLayout() {
  let layout = null;
  if (backendAvailable) {
    try {
      const data = await fetchJSON("/api/layout");
      layout = data.layout || null;
    } catch (error) {
      console.warn("Failed to load layout from backend:", error);
    }
  }
  if (!layout || !layout.length) {
    try {
      const stored = localStorage.getItem(PANEL_LAYOUT_KEY);
      if (stored) {
        layout = JSON.parse(stored);
      }
    } catch (error) {
      console.warn("Failed to parse stored layout:", error);
    }
  }
  if (layout && layout.length) {
    applyPanelLayout(layout);
  }
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
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const label = ctx.dataset.label || "";
                const formatted = currencyFormat.format(normalizeCurrencyValue(ctx.parsed.y));
                return `${label ? `${label}: ` : ""}${formatted}`;
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { maxRotation: 45, minRotation: 0 },
          },
          y: {
            ticks: {
              callback: (value) => currencyFormat.format(normalizeCurrencyValue(value)),
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
    const net = normalizeCurrencyValue(record.NetWorth);
    const liquid = normalizeCurrencyValue(record.Liquid);
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${record.Scenario}</td>
      <td>${record.Period}</td>
      <td>${currencyFormat.format(net)}</td>
      <td>${currencyFormat.format(liquid)}</td>
    `;
    tbody.appendChild(tr);
  });
  table.appendChild(thead);
  table.appendChild(tbody);
  container.appendChild(table);
}

function renderCharts(payload) {
  const normalized = (payload.data || []).map((record) => {
    const net = Math.floor(normalizeCurrencyValue(record.NetWorth) * 100) / 100;
    const liquid = Math.floor(normalizeCurrencyValue(record.Liquid) * 100) / 100;
    return {
      ...record,
      NetWorth: net,
      Liquid: liquid,
    };
  });
  renderScenarioList(payload.scenarios || []);
  renderAggregateTable(normalized);
  const netCfg = prepareSeries(normalized, "NetWorth");
  const liqCfg = prepareSeries(normalized, "Liquid");
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

async function runSimulation(skipStatus = false) {
  if (!requirePlanEditorVisible()) {
    return;
  }
  if (!backendAvailable) {
    setStatus("Backend not running. Start the API server to simulate.", "error");
    return;
  }
  if (!skipStatus) {
    setStatus("Running simulation...");
  }
  try {
    const payload = buildPlanPayload();
    if (!savedPlanNames.includes(payload.name)) {
      await fetchJSON("/api/plans", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await fetchSavedPlans();
    }
    const data = await fetchJSON("/api/scenarios", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderCharts(data);
    if (!skipStatus) {
      setStatus("Simulation updated.", "success");
    }
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
  if (runSimulationButton) {
    runSimulationButton.addEventListener("click", () => runSimulation(false));
  }
  document.getElementById("clear-scenarios").addEventListener("click", clearScenarios);
  planStartYearInput.addEventListener("input", refreshMonths);
  planYearsInput.addEventListener("input", refreshMonths);
  const freqChangeHandler = (event) => {
    currentFreq = event.target.value;
    if (freqSelect && event.target !== freqSelect) {
      freqSelect.value = currentFreq;
    }
    if (planFreqSelect && event.target !== planFreqSelect) {
      planFreqSelect.value = currentFreq;
    }
    refreshScenarios();
  };
  if (freqSelect) {
    freqSelect.addEventListener("change", freqChangeHandler);
  }
  if (planFreqSelect) {
    planFreqSelect.addEventListener("change", freqChangeHandler);
  }
  if (addPlanButton) {
    addPlanButton.addEventListener("click", handleAddPlan);
  }
  if (savePlanButton) {
    savePlanButton.addEventListener("click", handleSavePlan);
  }
  if (saveNewPlanButton) {
    saveNewPlanButton.addEventListener("click", handleSavePlanAsNew);
  }
  if (loadPlanButton) {
    loadPlanButton.addEventListener("click", handleLoadPlan);
  }
  if (deletePlanButton) {
    deletePlanButton.addEventListener("click", handleDeletePlan);
  }
  if (saveLayoutButton) {
    saveLayoutButton.addEventListener("click", () => persistPanelLayout(true));
  }
}

async function bootstrap() {
  hidePlanEditor();
  initPanelInteractivity();
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
  await loadPanelLayout();
  await fetchSavedPlans();
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
