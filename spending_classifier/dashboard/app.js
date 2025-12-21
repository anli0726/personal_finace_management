const state = {
  clusters: [],
  filteredClusters: [],
  activeIndex: -1,
};

const rootList = document.getElementById("root-list");
const searchInput = document.getElementById("search");
const detailTitle = document.getElementById("detail-title");
const detailSubtitle = document.getElementById("detail-subtitle");
const detailTable = document.getElementById("detail-table");
const summarySpending = document.getElementById("summary-spending");
const summaryCount = document.getElementById("summary-count");
const summaryAverage = document.getElementById("summary-average");
const yearFilter = document.getElementById("year-filter");
const groupNameInput = document.getElementById("group-name");
const assignGroupButton = document.getElementById("assign-group");
const clearGroupButton = document.getElementById("clear-group");
const groupSummary = document.getElementById("group-summary");
const selectAllCheckbox = document.getElementById("select-all");
const statFiles = document.getElementById("stat-files");
const statTxns = document.getElementById("stat-txns");
const statUnique = document.getElementById("stat-unique");

const currencyFormatter = new Intl.NumberFormat(undefined, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const GROUP_STORAGE_KEY = "spendingGroups";
const selectedKeys = new Set();

function formatNumber(value) {
  return new Intl.NumberFormat().format(value);
}

function formatCurrency(value) {
  const safeValue = value || 0;
  const sign = safeValue < 0 ? "-" : "";
  return `${sign}$${currencyFormatter.format(Math.abs(safeValue))}`;
}

function txnKey(txn) {
  return `${txn.date || ""}|${txn.description || ""}|${txn.amount || ""}|${txn.category || ""}|${
    txn.source_file || ""
  }`;
}

function loadGroups() {
  try {
    const raw = localStorage.getItem(GROUP_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (err) {
    console.error("Failed to load groups", err);
    return {};
  }
}

function saveGroups(groups) {
  localStorage.setItem(GROUP_STORAGE_KEY, JSON.stringify(groups));
}

function collectYears(clusters) {
  const years = new Set();
  clusters.forEach((cluster) => {
    (cluster.transactions || []).forEach((txn) => {
      const year = txn.year || parseYearFromDate(txn.date);
      if (year) years.add(year);
    });
  });
  return Array.from(years).sort((a, b) => b - a);
}

function parseYearFromDate(value) {
  if (!value) return null;
  const isoMatch = String(value).match(/^(\d{4})[-/]\d{1,2}[-/]\d{1,2}$/);
  if (isoMatch) return Number(isoMatch[1]);
  const usMatch = String(value).match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (usMatch) return Number(usMatch[3]);
  return null;
}

function buildFilteredClusters(clusters, year) {
  return clusters.map((cluster) => {
    const filteredTxns = (cluster.transactions || []).filter((txn) => {
      if (!year) return true;
      const txnYear = txn.year || parseYearFromDate(txn.date);
      return txnYear === year;
    });
    const totalSpending = filteredTxns.reduce((sum, txn) => {
      const amount = Number(txn.amount || 0);
      return amount < 0 ? sum + Math.abs(amount) : sum;
    }, 0);
    return {
      ...cluster,
      total_count: filteredTxns.length,
      total_spending: Number(totalSpending.toFixed(2)),
      transactions: filteredTxns,
    };
  });
}

function renderRootList(filterText) {
  rootList.innerHTML = "";
  const query = (filterText || "").toLowerCase();
  state.filteredClusters.forEach((cluster, index) => {
    if (!cluster.total_count) {
      return;
    }
    const label = cluster.root_label || cluster.root_description;
    if (query && !label.toLowerCase().includes(query)) {
      return;
    }
    const item = document.createElement("div");
    item.className = "root-item";
    if (index === state.activeIndex) {
      item.classList.add("active");
    }
    item.addEventListener("click", () => selectCluster(index));

    const name = document.createElement("span");
    name.className = "root-name";
    name.textContent = label;

    const count = document.createElement("span");
    count.className = "root-count";
    count.textContent = `${formatCurrency(cluster.total_spending || 0)} • ${formatNumber(
      cluster.total_count
    )}`;

    item.appendChild(name);
    item.appendChild(count);
    rootList.appendChild(item);
  });
}

function renderDetails(cluster) {
  detailTitle.textContent = cluster.root_description;
  const categoryLabel = cluster.root_category ? `Category: ${cluster.root_category}` : null;
  const tokenLabel = `Root tokens: ${cluster.root_tokens || "-"}`;
  detailSubtitle.textContent = categoryLabel ? `${categoryLabel} • ${tokenLabel}` : tokenLabel;
  summarySpending.textContent = formatCurrency(cluster.total_spending || 0);
  summaryCount.textContent = formatNumber(cluster.total_count || 0);
  const avg = cluster.total_count ? (cluster.total_spending || 0) / cluster.total_count : 0;
  summaryAverage.textContent = formatCurrency(avg);

  detailTable.innerHTML = "";
  selectedKeys.clear();
  const groups = loadGroups();
  (cluster.transactions || []).forEach((item) => {
    const row = document.createElement("tr");
    row.dataset.key = txnKey(item);
    const checkboxCell = document.createElement("td");
    checkboxCell.className = "checkbox-cell";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.addEventListener("change", () => {
      const key = row.dataset.key;
      if (!key) return;
      if (checkbox.checked) {
        selectedKeys.add(key);
      } else {
        selectedKeys.delete(key);
      }
    });
    checkboxCell.appendChild(checkbox);
    const date = document.createElement("td");
    date.textContent = item.date || "";
    const desc = document.createElement("td");
    desc.textContent = item.description;
    const group = document.createElement("td");
    group.textContent = groups[row.dataset.key] || "";
    const amount = document.createElement("td");
    amount.className = "num";
    const amountValue = Number(item.amount || 0);
    amount.textContent = formatCurrency(amountValue);
    const spending = document.createElement("td");
    spending.className = "num";
    const spendingValue = amountValue < 0 ? Math.abs(amountValue) : 0;
    spending.textContent = formatCurrency(spendingValue);
    row.appendChild(checkboxCell);
    row.appendChild(date);
    row.appendChild(desc);
    row.appendChild(group);
    row.appendChild(amount);
    row.appendChild(spending);
    detailTable.appendChild(row);
  });

  selectAllCheckbox.checked = false;
  renderGroupSummary(cluster);
}

function selectCluster(index) {
  state.activeIndex = index;
  renderRootList(searchInput.value);
  const cluster = state.filteredClusters[index];
  if (cluster) {
    renderDetails(cluster);
  }
}

function renderGroupSummary(cluster) {
  const groups = loadGroups();
  const counts = {};
  (cluster.transactions || []).forEach((txn) => {
    const name = groups[txnKey(txn)];
    if (!name) return;
    counts[name] = (counts[name] || 0) + 1;
  });
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  if (!entries.length) {
    groupSummary.textContent = "No groups yet.";
    return;
  }
  groupSummary.textContent = entries
    .map(([name, count]) => `${name} (${formatNumber(count)})`)
    .join(" • ");
}

function selectFirstAvailable() {
  const index = state.filteredClusters.findIndex((cluster) => cluster.total_count);
  if (index >= 0) {
    selectCluster(index);
  } else {
    detailTitle.textContent = "No transactions";
    detailSubtitle.textContent = "Try another year filter.";
    detailTable.innerHTML = "";
    groupSummary.textContent = "No groups yet.";
    summarySpending.textContent = formatCurrency(0);
    summaryCount.textContent = "0";
    summaryAverage.textContent = formatCurrency(0);
  }
}

function initDashboard(data) {
  state.clusters = (data.clusters || []).slice().sort((a, b) => {
    const spendingDiff = (b.total_spending || 0) - (a.total_spending || 0);
    if (spendingDiff !== 0) return spendingDiff;
    return (b.total_count || 0) - (a.total_count || 0);
  });
  statFiles.textContent = formatNumber(data.stats?.statement_files || 0);
  statTxns.textContent = formatNumber(data.stats?.total_transactions || 0);
  statUnique.textContent = formatNumber(data.stats?.unique_descriptions || 0);
  const years = collectYears(state.clusters);
  yearFilter.innerHTML = "";
  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = "All years";
  yearFilter.appendChild(allOption);
  years.forEach((year) => {
    const option = document.createElement("option");
    option.value = year;
    option.textContent = year;
    yearFilter.appendChild(option);
  });
  state.filteredClusters = buildFilteredClusters(state.clusters, null);
  renderRootList("");
  selectFirstAvailable();
}

searchInput.addEventListener("input", (event) => {
  renderRootList(event.target.value);
});

yearFilter.addEventListener("change", (event) => {
  const yearValue = event.target.value ? Number(event.target.value) : null;
  state.filteredClusters = buildFilteredClusters(state.clusters, yearValue);
  state.activeIndex = -1;
  renderRootList(searchInput.value);
  selectFirstAvailable();
});

assignGroupButton.addEventListener("click", () => {
  const name = groupNameInput.value.trim();
  if (!name || !selectedKeys.size) return;
  const groups = loadGroups();
  selectedKeys.forEach((key) => {
    groups[key] = name;
  });
  saveGroups(groups);
  if (state.activeIndex >= 0) {
    renderDetails(state.filteredClusters[state.activeIndex]);
  }
});

clearGroupButton.addEventListener("click", () => {
  if (!selectedKeys.size) return;
  const groups = loadGroups();
  selectedKeys.forEach((key) => {
    delete groups[key];
  });
  saveGroups(groups);
  if (state.activeIndex >= 0) {
    renderDetails(state.filteredClusters[state.activeIndex]);
  }
});

selectAllCheckbox.addEventListener("change", (event) => {
  const shouldSelect = event.target.checked;
  selectedKeys.clear();
  detailTable.querySelectorAll("tr").forEach((row) => {
    const checkbox = row.querySelector("input[type='checkbox']");
    if (!checkbox) return;
    checkbox.checked = shouldSelect;
    if (shouldSelect && row.dataset.key) {
      selectedKeys.add(row.dataset.key);
    }
  });
});

fetch("data.json")
  .then((resp) => resp.json())
  .then(initDashboard)
  .catch((err) => {
    detailTitle.textContent = "Missing data.json";
    detailSubtitle.textContent = "Run the summarizer to generate dashboard data.";
    console.error(err);
  });
