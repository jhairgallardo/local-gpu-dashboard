const REFRESH_INTERVAL_MS = 1000;
const HIDDEN_REFRESH_INTERVAL_MS = 5000;
const HISTORY_LIMIT = 60;
const STALE_FAILURE_THRESHOLD = 3;
const OVERVIEW_POWER_BAR_MAX_WATTS = 230;
const OVERVIEW_MEMORY_BAR_MAX_GB = 24.0;
const THEME_STORAGE_KEY = "gpu-dashboard-theme";
const DEFAULT_ROUTE = { view: "overview", gpuIndex: null };

const gpuGrid = document.querySelector("#gpu-grid");
const statePanel = document.querySelector("#state-panel");
const stateMessage = document.querySelector("#state-message");
const overallStatus = document.querySelector("#overall-status");
const gpuTemplate = document.querySelector("#gpu-card-template");
const diagnosticsPanel = document.querySelector("#diagnostics-panel");
const diagnosticsStatus = document.querySelector("#diagnostics-status");
const diagnosticsGrid = document.querySelector("#diagnostics-grid");
const diagnosticsIssues = document.querySelector("#diagnostics-issues");
const themeToggle = document.querySelector("#theme-toggle");
const themeToggleLabel = document.querySelector("#theme-toggle-label");
const viewNav = document.querySelector(".view-nav");
const gpuNavList = document.querySelector("#gpu-nav-list");
const overviewView = document.querySelector("#overview-view");
const gpuDetailView = document.querySelector("#gpu-detail-view");
const diagnosticsView = document.querySelector("#diagnostics-view");
const detailGpuIndex = document.querySelector("#detail-gpu-index");
const detailGpuName = document.querySelector("#detail-gpu-name");
const detailGpuHealth = document.querySelector("#detail-gpu-health");
const detailIntro = document.querySelector("#detail-intro");
const detailUtilization = document.querySelector("#detail-utilization");
const detailMemory = document.querySelector("#detail-memory");
const detailTemperature = document.querySelector("#detail-temperature");
const detailPower = document.querySelector("#detail-power");
const detailFan = document.querySelector("#detail-fan");
const detailHistoryChip = document.querySelector("#detail-history-chip");
const detailUpdatedChip = document.querySelector("#detail-updated-chip");
const detailMemoryChip = document.querySelector("#detail-memory-chip");
const detailUuidChip = document.querySelector("#detail-uuid-chip");
const detailMetricGrid = document.querySelector("#detail-metric-grid");
const detailMemoryBars = document.querySelector("#detail-memory-bars");
const detailTechnicalGrid = document.querySelector("#detail-technical-grid");
const detailUnavailableList = document.querySelector("#detail-unavailable-list");
const detailProcessCount = document.querySelector("#detail-process-count");
const detailProcessNotices = document.querySelector("#detail-process-notices");
const detailProcessList = document.querySelector("#detail-process-list");
const detailHistoryUtilization = document.querySelector("#detail-history-utilization");
const detailHistoryMemory = document.querySelector("#detail-history-memory");
const detailHistoryTemperature = document.querySelector("#detail-history-temperature");
const detailHistoryUtilizationTooltip = document.querySelector("#detail-history-utilization-tooltip");
const detailHistoryMemoryTooltip = document.querySelector("#detail-history-memory-tooltip");
const detailHistoryTemperatureTooltip = document.querySelector("#detail-history-temperature-tooltip");
const overviewHeroCore = document.querySelector("#overview-hero-core");
const overviewFleetChip = document.querySelector("#overview-fleet-chip");
const overviewUtilizationChart = document.querySelector("#overview-utilization-chart");
const overviewUtilizationTooltip = document.querySelector("#overview-utilization-tooltip");
const overviewMemoryBars = document.querySelector("#overview-memory-bars");
const overviewTemperatureChart = document.querySelector("#overview-temperature-chart");
const overviewTemperatureTooltip = document.querySelector("#overview-temperature-tooltip");
const overviewPowerBars = document.querySelector("#overview-power-bars");
const overviewUtilizationLegend = document.querySelector("#overview-utilization-legend");
const overviewKpis = {
  gpus: {
    value: document.querySelector("#overview-kpi-gpus"),
    detail: document.querySelector("#overview-kpi-gpus-detail"),
  },
  health: {
    value: document.querySelector("#overview-kpi-health"),
    detail: document.querySelector("#overview-kpi-health-detail"),
  },
  utilization: {
    value: document.querySelector("#overview-kpi-utilization"),
    detail: document.querySelector("#overview-kpi-utilization-detail"),
  },
  memory: {
    value: document.querySelector("#overview-kpi-memory"),
    detail: document.querySelector("#overview-kpi-memory-detail"),
  },
  temperature: {
    value: document.querySelector("#overview-kpi-temperature"),
    detail: document.querySelector("#overview-kpi-temperature-detail"),
  },
  power: {
    value: document.querySelector("#overview-kpi-power"),
    detail: document.querySelector("#overview-kpi-power-detail"),
  },
};

const GPU_ACCENTS = [
  { color: "#24d7e8", rgb: "36, 215, 232" },
  { color: "#3ee59a", rgb: "62, 229, 154" },
  { color: "#f3bb52", rgb: "243, 187, 82" },
  { color: "#8b7cff", rgb: "139, 124, 255" },
  { color: "#ff6676", rgb: "255, 102, 118" },
  { color: "#46a7ff", rgb: "70, 167, 255" },
];

const detailHistoryTooltipTargets = [
  { chart: detailHistoryUtilization, tooltip: detailHistoryUtilizationTooltip },
  { chart: detailHistoryMemory, tooltip: detailHistoryMemoryTooltip },
  { chart: detailHistoryTemperature, tooltip: detailHistoryTemperatureTooltip },
];

const histories = new Map();
const renderedCards = new Map();

let pollTimer = null;
let inFlight = false;
let failureCount = 0;
let hasRenderedSnapshot = false;
let currentSnapshot = null;
let currentRoute = parseRoute();

function initializeTheme() {
  const initialTheme = getStoredTheme() || normalizeTheme(document.documentElement.dataset.theme) || "dark";
  applyTheme(initialTheme, false);

  themeToggle?.addEventListener("click", () => {
    const nextTheme = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    applyTheme(nextTheme, true);
  });
}

function applyTheme(theme, persist) {
  const safeTheme = normalizeTheme(theme) || "dark";
  document.documentElement.dataset.theme = safeTheme;
  document.documentElement.style.colorScheme = safeTheme;

  if (themeToggle) {
    themeToggle.setAttribute("aria-pressed", String(safeTheme === "light"));
  }

  if (themeToggleLabel) {
    themeToggleLabel.textContent = safeTheme === "light" ? "Light Mode" : "Dark Mode";
  }

  if (persist) {
    storeTheme(safeTheme);
  }
}

function getStoredTheme() {
  try {
    return normalizeTheme(localStorage.getItem(THEME_STORAGE_KEY));
  } catch (error) {
    return null;
  }
}

function storeTheme(theme) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch (error) {
    // Theme persistence is nice-to-have; the dashboard remains usable without storage.
  }
}

function normalizeTheme(theme) {
  return theme === "dark" || theme === "light" ? theme : null;
}

function initializeRouting() {
  if (!window.location.hash) {
    history.replaceState(null, "", "#overview");
    currentRoute = DEFAULT_ROUTE;
  } else {
    currentRoute = parseRoute();
  }

  window.addEventListener("hashchange", () => {
    currentRoute = parseRoute();
    renderCurrentView();
  });

  viewNav?.addEventListener("keydown", handleNavigationKeydown);
  renderCurrentView();
}

function initializeChartInteractions() {
  if (overviewUtilizationChart && overviewUtilizationTooltip) {
    overviewUtilizationChart.addEventListener("pointermove", showOverviewUtilizationTooltip);
    overviewUtilizationChart.addEventListener("pointerleave", hideOverviewUtilizationTooltip);
    overviewUtilizationChart.addEventListener("focus", showLatestOverviewUtilizationTooltip);
    overviewUtilizationChart.addEventListener("blur", hideOverviewUtilizationTooltip);
  }

  if (overviewTemperatureChart && overviewTemperatureTooltip) {
    overviewTemperatureChart.addEventListener("pointermove", showOverviewTemperatureTooltip);
    overviewTemperatureChart.addEventListener("pointerleave", hideOverviewTemperatureTooltip);
    overviewTemperatureChart.addEventListener("focus", showLatestOverviewTemperatureTooltip);
    overviewTemperatureChart.addEventListener("blur", hideOverviewTemperatureTooltip);
  }

  detailHistoryTooltipTargets.forEach(({ chart, tooltip }) => {
    if (!chart || !tooltip) {
      return;
    }

    chart.addEventListener("pointermove", (event) => showDetailHistoryTooltip(chart, tooltip, event));
    chart.addEventListener("pointerleave", () => hideChartTooltip(tooltip));
    chart.addEventListener("focus", () => showDetailHistoryTooltip(chart, tooltip, null, true));
    chart.addEventListener("blur", () => hideChartTooltip(tooltip));
  });
}

function handleNavigationKeydown(event) {
  const keys = ["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End"];
  if (!keys.includes(event.key)) {
    return;
  }

  const tabs = Array.from(viewNav.querySelectorAll('[role="tab"]'));
  const currentIndex = tabs.indexOf(document.activeElement);
  if (currentIndex === -1 || tabs.length === 0) {
    return;
  }

  event.preventDefault();
  let nextIndex = currentIndex;

  if (event.key === "ArrowRight" || event.key === "ArrowDown") {
    nextIndex = (currentIndex + 1) % tabs.length;
  } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
    nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
  } else if (event.key === "Home") {
    nextIndex = 0;
  } else if (event.key === "End") {
    nextIndex = tabs.length - 1;
  }

  const nextTab = tabs[nextIndex];
  nextTab.focus();
  window.location.hash = nextTab.hash || "#overview";
}

function parseRoute() {
  const hash = window.location.hash.replace(/^#/, "").trim().toLowerCase();

  if (hash === "diagnostics") {
    return { view: "diagnostics", gpuIndex: null };
  }

  const gpuMatch = hash.match(/^gpu-(\d+)$/);
  if (gpuMatch) {
    return { view: "gpu", gpuIndex: Number(gpuMatch[1]) };
  }

  return DEFAULT_ROUTE;
}

function routeKey(route = currentRoute) {
  if (route.view === "gpu") {
    return `gpu-${route.gpuIndex}`;
  }

  return route.view;
}

async function requestSnapshot() {
  if (inFlight) {
    return;
  }

  inFlight = true;

  if (!hasRenderedSnapshot) {
    setLoadingState();
  }

  try {
    const response = await fetch("/api/snapshot", {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      throw new Error(`Snapshot request failed with HTTP ${response.status}`);
    }

    const snapshot = await response.json();
    failureCount = 0;
    hasRenderedSnapshot = true;
    renderSnapshot(snapshot);
  } catch (error) {
    failureCount += 1;
    renderPollFailure(error);
  } finally {
    inFlight = false;
    scheduleNextPoll();
  }
}

function scheduleNextPoll() {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(requestSnapshot, getPollInterval());
}

function getPollInterval() {
  return document.hidden ? HIDDEN_REFRESH_INTERVAL_MS : REFRESH_INTERVAL_MS;
}

function handleVisibilityChange() {
  if (!document.hidden && !inFlight) {
    clearTimeout(pollTimer);
    requestSnapshot();
    return;
  }

  scheduleNextPoll();
}

function setLoadingState() {
  gpuGrid.replaceChildren();
  renderGpuNavigation([], "Awaiting GPUs");
  renderCurrentView();
  statePanel.dataset.state = "loading";
  stateMessage.textContent = "Awaiting GPU telemetry.";
  setDiagnosticsLoading();
}

function renderSnapshot(snapshot) {
  const gpus = Array.isArray(snapshot.gpus) ? snapshot.gpus : [];
  currentSnapshot = snapshot;
  renderGpuNavigation(gpus);
  renderDiagnostics(snapshot.diagnostics, snapshot.errors);

  if (!snapshot.ok && gpus.length === 0) {
    const message = firstErrorMessage(snapshot) || "GPU telemetry is unavailable.";
    clearGpuCards();
    statePanel.dataset.state = snapshot.status === "no_gpus" ? "empty" : "error";
    stateMessage.textContent = message;
    setOverallStatus(
      snapshot.status === "no_gpus" ? "No GPUs" : "Offline",
      snapshot.status === "no_gpus" ? "warning" : "error",
    );
    renderCurrentView();
    return;
  }

  if (gpus.length === 0) {
    clearGpuCards();
    statePanel.dataset.state = "empty";
    stateMessage.textContent = "No NVIDIA GPUs were reported by the local collector.";
    setOverallStatus("No GPUs", "warning");
    renderCurrentView();
    return;
  }

  gpus.forEach(recordHistory);

  const overall = getOverallHealth(gpus);
  renderCurrentView();
  setOverallStatus(overall.label, overall.level);
  statePanel.dataset.state = "ready";
  stateMessage.textContent = "";
}

function renderCurrentView() {
  const snapshot = currentSnapshot;
  const gpus = Array.isArray(snapshot?.gpus) ? snapshot.gpus : [];
  const activeRouteKey = routeKey();

  overviewView.hidden = currentRoute.view !== "overview";
  gpuDetailView.hidden = currentRoute.view !== "gpu";
  diagnosticsView.hidden = currentRoute.view !== "diagnostics";
  updateActiveNavigation(activeRouteKey);

  if (currentRoute.view === "overview") {
    renderOverviewView(gpus);
    return;
  }

  if (currentRoute.view === "gpu") {
    renderGpuDetailView(gpus);
  }
}

function renderGpuNavigation(gpus, emptyText = "No GPUs detected") {
  gpuNavList.replaceChildren();

  if (gpus.length === 0) {
    const empty = document.createElement("span");
    empty.className = "nav-empty";
    empty.textContent = emptyText;
    gpuNavList.appendChild(empty);
    updateActiveNavigation(routeKey());
    return;
  }

  gpus.forEach((gpu) => {
    const link = document.createElement("a");
    const index = gpu.index ?? 0;
    const health = getGpuHealth(gpu);
    link.className = "nav-link gpu-nav-link";
    link.href = `#gpu-${index}`;
    link.dataset.route = `gpu-${index}`;
    link.setAttribute("role", "tab");
    link.setAttribute("aria-controls", "gpu-detail-view");
    link.setAttribute("aria-label", `GPU ${index} detail view`);

    const label = document.createElement("span");
    label.textContent = `GPU ${index}`;

    const detail = document.createElement("small");
    detail.textContent = gpu.name || "NVIDIA GPU";

    const status = document.createElement("span");
    status.className = "nav-status";
    status.dataset.status = health.level;
    status.textContent = health.label;

    link.append(label, detail, status);
    gpuNavList.appendChild(link);
  });

  updateActiveNavigation(routeKey());
}

function updateActiveNavigation(activeRouteKey) {
  document.querySelectorAll("[data-route]").forEach((link) => {
    const active = link.dataset.route === activeRouteKey;
    link.classList.toggle("is-active", active);
    if (link.getAttribute("role") === "tab") {
      link.setAttribute("aria-selected", String(active));
      link.setAttribute("tabindex", active ? "0" : "-1");
    }
    if (active) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  });
}

function renderOverviewView(gpus) {
  if (currentRoute.view !== "overview") {
    return;
  }

  updateOverviewKpis(gpus);
  renderOverviewCharts(gpus);
  renderOverviewMemoryBars(gpus);
  renderOverviewPowerBars(gpus);
  renderOverviewLegend(gpus);
  if (overviewHeroCore) {
    overviewHeroCore.textContent = String(gpus.length || "--");
  }
  if (overviewFleetChip) {
    overviewFleetChip.textContent = gpus.length === 1 ? "1 GPU" : `${gpus.length || "--"} GPUs`;
  }

  const fragment = document.createDocumentFragment();
  const visibleKeys = new Set();

  gpus.forEach((gpu) => {
    const key = getGpuKey(gpu);
    visibleKeys.add(key);

    let card = renderedCards.get(key);
    if (!card) {
      card = gpuTemplate.content.firstElementChild.cloneNode(true);
      renderedCards.set(key, card);
    }

    updateGpuCard(card, gpu);
    fragment.appendChild(card);
  });

  Array.from(renderedCards.keys()).forEach((key) => {
    if (!visibleKeys.has(key)) {
      renderedCards.delete(key);
    }
  });

  gpuGrid.replaceChildren(fragment);
}

function updateOverviewKpis(gpus) {
  const stats = getOverviewStats(gpus);
  const hasGpus = gpus.length > 0;

  setKpi("gpus", hasGpus ? String(gpus.length) : "--", hasGpus ? "Detected by NVML" : "Awaiting telemetry");
  setKpi("health", stats.health.label, hasGpus ? healthDetail(stats.health.level) : "Collector starting");
  setKpi(
    "utilization",
    Number.isFinite(stats.averageUtilization) ? formatPercent(stats.averageUtilization) : "--",
    Number.isFinite(stats.peakUtilization) ? `Peak ${formatPercent(stats.peakUtilization)}` : "Avg / peak",
  );
  setKpi(
    "memory",
    stats.memoryTotal > 0 ? formatMib(stats.memoryUsed) : "--",
    stats.memoryTotal > 0
      ? `${formatPercent(stats.memoryPercent)} of ${formatMib(stats.memoryTotal)}`
      : "Used / capacity",
  );
  setKpi(
    "temperature",
    Number.isFinite(stats.hottestTemperature) ? formatTemperature(stats.hottestTemperature) : "--",
    Number.isFinite(stats.hottestGpuIndex) ? `GPU ${stats.hottestGpuIndex}` : "Thermal peak",
  );
  setKpi(
    "power",
    Number.isFinite(stats.totalPowerDraw) ? `${stats.totalPowerDraw.toFixed(1)} W` : "--",
    Number.isFinite(stats.totalPowerLimit) ? `Limit ${stats.totalPowerLimit.toFixed(0)} W` : "Total draw",
  );
}

function setKpi(key, value, detail) {
  const kpi = overviewKpis[key];
  if (!kpi?.value || !kpi?.detail) {
    return;
  }

  kpi.value.textContent = value;
  kpi.detail.textContent = detail;
}

function getOverviewStats(gpus) {
  const utilizationValues = gpus
    .map((gpu) => normalizePercent(gpu.utilization?.gpu_percent))
    .filter(Number.isFinite);
  const memoryUsedValues = gpus.map((gpu) => toFiniteMetric(gpu.memory?.used_mib)).filter(Number.isFinite);
  const memoryTotalValues = gpus.map((gpu) => toFiniteMetric(gpu.memory?.total_mib)).filter(Number.isFinite);
  const powerDrawValues = gpus.map((gpu) => toFiniteMetric(gpu.power?.draw_watts)).filter(Number.isFinite);
  const powerLimitValues = gpus.map((gpu) => toFiniteMetric(gpu.power?.limit_watts)).filter(Number.isFinite);
  let hottestTemperature = null;
  let hottestGpuIndex = null;

  gpus.forEach((gpu) => {
    if (!Number.isFinite(gpu.temperature_c)) {
      return;
    }

    if (!Number.isFinite(hottestTemperature) || gpu.temperature_c > hottestTemperature) {
      hottestTemperature = gpu.temperature_c;
      hottestGpuIndex = gpu.index;
    }
  });

  const memoryUsed = sumValues(memoryUsedValues);
  const memoryTotal = sumValues(memoryTotalValues);
  const totalPowerDraw = sumValues(powerDrawValues);
  const totalPowerLimit = sumValues(powerLimitValues);

  return {
    health: gpus.length > 0 ? getOverallHealth(gpus) : { label: "Loading", level: "warning" },
    averageUtilization: averageValues(utilizationValues),
    peakUtilization: utilizationValues.length > 0 ? Math.max(...utilizationValues) : null,
    memoryUsed,
    memoryTotal,
    memoryPercent: memoryTotal > 0 ? normalizePercent((memoryUsed / memoryTotal) * 100) : null,
    hottestTemperature,
    hottestGpuIndex,
    totalPowerDraw: powerDrawValues.length > 0 ? totalPowerDraw : null,
    totalPowerLimit: powerLimitValues.length > 0 ? totalPowerLimit : null,
  };
}

function renderOverviewCharts(gpus) {
  renderMultiGpuTrendChart(overviewUtilizationChart, gpus, "utilization", 100, {
    showAxisLabels: true,
    axisTicks: [0, 25, 50, 75, 100],
    axisSuffix: "%",
    enableTooltip: true,
    tooltipTitle: "Utilization",
    formatTooltipValue: formatPercent,
  });
  renderMultiGpuTrendChart(overviewTemperatureChart, gpus, "temperature", 110, {
    showAxisLabels: true,
    axisTicks: [0, 55, 90, 110],
    axisSuffix: " C",
    dangerZoneStart: 90,
    enableTooltip: true,
    tooltipTitle: "Temperature",
    formatTooltipValue: formatTemperature,
  });
}

function renderMultiGpuTrendChart(svg, gpus, metric, maxValue, options = {}) {
  if (!svg) {
    return;
  }

  const box = parseViewBox(svg, 620, 220);
  const basePadding = box.height >= 160 ? 22 : 12;
  const showAxisLabels = Boolean(options.showAxisLabels || options.showPercentAxis);
  const padding = {
    top: basePadding,
    right: basePadding,
    bottom: basePadding,
    left: showAxisLabels ? 56 : basePadding,
  };
  const plotWidth = box.width - padding.left - padding.right;
  const axisTicks = options.axisTicks || (showAxisLabels ? [0, 25, 50, 75, 100] : [25, 50, 75]);
  const gridLines = axisTicks.map((tick) => {
    const y = yForChartValue(tick, maxValue, box, padding);
    const className = tick === 0 || tick === maxValue ? "overview-chart-boundary" : "overview-chart-gridline";
    return `<line class="${className}" x1="${padding.left}" y1="${y.toFixed(1)}" x2="${box.width - padding.right}" y2="${y.toFixed(1)}"></line>`;
  });
  const axisLabels = showAxisLabels
    ? axisTicks
        .map((tick) => {
          const y = yForChartValue(tick, maxValue, box, padding);
          return `<text class="overview-chart-axis-label" x="${padding.left - 9}" y="${y.toFixed(1)}" text-anchor="end" dominant-baseline="middle">${tick}${options.axisSuffix || ""}</text>`;
        })
        .join("")
    : "";
  const dangerZone = Number.isFinite(options.dangerZoneStart)
    ? makeChartDangerZone(box, padding, maxValue, options.dangerZoneStart)
    : "";

  const polylines = gpus
    .map((gpu) => {
      const history = histories.get(getGpuKey(gpu)) || [];
      const values = history.map((point) => point[metric]).filter(Number.isFinite);
      if (values.length === 0) {
        return "";
      }

      const accent = getGpuAccent(gpu.index);
      const points = values.map((value, index) => {
        const x =
          values.length === 1
            ? padding.left
            : padding.left + (index / (values.length - 1)) * plotWidth;
        const y = yForChartValue(value, maxValue, box, padding);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      });

      if (values.length === 1) {
        points.push(`${(box.width - padding.right).toFixed(1)},${points[0].split(",")[1]}`);
      }

      return `<polyline class="overview-chart-line" style="--series-color: ${accent.color}" points="${points.join(" ")}"></polyline>`;
    })
    .join("");

  const hitArea = options.enableTooltip
    ? `<rect class="overview-chart-hit-area" x="0" y="0" width="${box.width}" height="${box.height}"></rect>`
    : "";

  svg.innerHTML = `${dangerZone}${gridLines.join("")}${axisLabels}${polylines || makeEmptyChartLine(box, padding.left, padding.right, padding.bottom)}${hitArea}`;
  if (options.enableTooltip) {
    svg._tooltipData = {
      box,
      formatTooltipValue: options.formatTooltipValue,
      gpus,
      maxValue,
      metric,
      padding,
      tooltipTitle: options.tooltipTitle,
    };
  }
}

function yForChartValue(value, maxValue, box, padding) {
  const ratio = Math.max(0, Math.min(1, value / maxValue));
  return box.height - padding.bottom - ratio * (box.height - padding.top - padding.bottom);
}

function makeChartDangerZone(box, padding, maxValue, startValue) {
  const dangerY = yForChartValue(startValue, maxValue, box, padding);
  const height = Math.max(0, dangerY - padding.top);
  return `<rect class="overview-chart-danger-zone" x="${padding.left}" y="${padding.top}" width="${box.width - padding.left - padding.right}" height="${height.toFixed(1)}"></rect>`;
}

function showLatestOverviewUtilizationTooltip() {
  showOverviewTrendTooltip(overviewUtilizationChart, overviewUtilizationTooltip, null, true);
}

function showLatestOverviewTemperatureTooltip() {
  showOverviewTrendTooltip(overviewTemperatureChart, overviewTemperatureTooltip, null, true);
}

function showOverviewUtilizationTooltip(event, useLatest = false) {
  showOverviewTrendTooltip(overviewUtilizationChart, overviewUtilizationTooltip, event, useLatest);
}

function showOverviewTemperatureTooltip(event, useLatest = false) {
  showOverviewTrendTooltip(overviewTemperatureChart, overviewTemperatureTooltip, event, useLatest);
}

function showOverviewTrendTooltip(svg, tooltip, event, useLatest = false) {
  const data = svg?._tooltipData;
  if (!data || !tooltip || !Array.isArray(data.gpus) || data.gpus.length === 0) {
    hideChartTooltip(tooltip);
    return;
  }

  const sampleRatio = useLatest || !event ? 1 : getChartSampleRatio(event, svg, data);
  const rows = data.gpus.map((gpu) => getOverviewTrendTooltipRow(gpu, data, sampleRatio));
  tooltip.replaceChildren(makeTooltipTitle(data.tooltipTitle || formatMetricName(data.metric)), ...rows.map(renderTooltipRow));
  tooltip.hidden = false;
  positionOverviewTrendTooltip(svg, tooltip, event);
}

function showDetailHistoryTooltip(svg, tooltip, event, useLatest = false) {
  const data = svg?._tooltipData;
  if (!data || !tooltip || !Array.isArray(data.history) || data.history.length === 0) {
    hideChartTooltip(tooltip);
    return;
  }

  const sampleRatio = useLatest || !event ? 1 : getChartSampleRatio(event, svg, data);
  const row = getDetailHistoryTooltipRow(data, sampleRatio);
  tooltip.replaceChildren(makeTooltipTitle(data.tooltipTitle || "History"), renderTooltipRow(row));
  tooltip.hidden = false;
  positionChartTooltip(svg, tooltip, event);
}

function getChartSampleRatio(event, svg, data) {
  const rect = svg.getBoundingClientRect();
  if (rect.width <= 0) {
    return 1;
  }

  const svgX = ((event.clientX - rect.left) / rect.width) * data.box.width;
  const plotWidth = data.box.width - data.padding.left - data.padding.right;
  return clampNumber((svgX - data.padding.left) / plotWidth, 0, 1) ?? 1;
}

function getOverviewTrendTooltipRow(gpu, data, sampleRatio) {
  const history = histories.get(getGpuKey(gpu)) || [];
  const index = history.length <= 1 ? 0 : Math.round(sampleRatio * (history.length - 1));
  const value = history[index]?.[data.metric];
  const formatter =
    typeof data.formatTooltipValue === "function" ? data.formatTooltipValue : (metricValue) => String(metricValue);
  const accent = getGpuAccent(gpu.index);

  return {
    color: accent.color,
    label: `GPU ${gpu.index ?? "--"}`,
    value: Number.isFinite(value) ? formatter(value) : "Unavailable",
  };
}

function getDetailHistoryTooltipRow(data, sampleRatio) {
  const index = data.history.length <= 1 ? 0 : Math.round(sampleRatio * (data.history.length - 1));
  const value = data.history[index]?.[data.metric];
  const formatter =
    typeof data.formatTooltipValue === "function" ? data.formatTooltipValue : (metricValue) => String(metricValue);

  return {
    color: data.color,
    label: data.tooltipLabel || formatMetricName(data.metric),
    value: Number.isFinite(value) ? formatter(value) : "Unavailable",
  };
}

function makeTooltipTitle(text) {
  const title = document.createElement("strong");
  title.className = "chart-tooltip-title";
  title.textContent = text;
  return title;
}

function renderTooltipRow(row) {
  const item = document.createElement("span");
  item.className = "chart-tooltip-row";

  const label = document.createElement("span");
  label.className = "chart-tooltip-label";

  const dot = document.createElement("span");
  dot.className = "chart-tooltip-dot";
  dot.style.setProperty("--gpu-accent", row.color);

  const name = document.createElement("span");
  name.textContent = row.label;
  label.append(dot, name);

  const value = document.createElement("strong");
  value.textContent = row.value;

  item.append(label, value);
  return item;
}

function positionOverviewUtilizationTooltip(event) {
  positionOverviewTrendTooltip(overviewUtilizationChart, overviewUtilizationTooltip, event);
}

function positionOverviewTrendTooltip(svg, tooltip, event) {
  const panel = tooltip.closest(".command-panel") || svg?.parentElement;
  if (!panel) {
    return;
  }

  const panelRect = panel.getBoundingClientRect();
  const fallbackLeft = panelRect.width - tooltip.offsetWidth - 18;
  const fallbackTop = 74;
  const requestedLeft = event ? event.clientX - panelRect.left + 14 : fallbackLeft;
  const requestedTop = event ? event.clientY - panelRect.top + 14 : fallbackTop;
  const left = clampNumber(requestedLeft, 12, panelRect.width - tooltip.offsetWidth - 12) ?? 12;
  const top = clampNumber(requestedTop, 58, panelRect.height - tooltip.offsetHeight - 12) ?? 58;

  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

function positionChartTooltip(svg, tooltip, event) {
  const panel = tooltip.closest(".detail-history-item") || svg?.parentElement;
  if (!panel) {
    return;
  }

  const panelRect = panel.getBoundingClientRect();
  const fallbackLeft = panelRect.width - tooltip.offsetWidth - 14;
  const fallbackTop = 36;
  const requestedLeft = event ? event.clientX - panelRect.left + 14 : fallbackLeft;
  const requestedTop = event ? event.clientY - panelRect.top + 14 : fallbackTop;
  const left = clampNumber(requestedLeft, 8, panelRect.width - tooltip.offsetWidth - 8) ?? 8;
  const top = clampNumber(requestedTop, 32, panelRect.height - tooltip.offsetHeight - 8) ?? 32;

  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

function hideChartTooltip(tooltip) {
  if (tooltip) {
    tooltip.hidden = true;
  }
}

function hideOverviewUtilizationTooltip() {
  hideChartTooltip(overviewUtilizationTooltip);
}

function hideOverviewTemperatureTooltip() {
  hideChartTooltip(overviewTemperatureTooltip);
}

function renderOverviewMemoryBars(gpus) {
  if (!overviewMemoryBars) {
    return;
  }

  overviewMemoryBars.replaceChildren();

  if (gpus.length === 0) {
    const empty = document.createElement("p");
    empty.className = "overview-empty";
    empty.textContent = "Awaiting memory telemetry.";
    overviewMemoryBars.appendChild(empty);
    return;
  }

  gpus.forEach((gpu) => {
    const usedGb = mibToGb(toFiniteMetric(gpu.memory?.used_mib));
    const percent = Number.isFinite(usedGb)
      ? clampNumber((usedGb / OVERVIEW_MEMORY_BAR_MAX_GB) * 100, 0, 100)
      : 0;
    const accent = getGpuAccent(gpu.index);
    const row = document.createElement("div");
    row.className = "power-bar-row overview-memory-row";
    row.style.setProperty("--gpu-accent", accent.color);
    row.style.setProperty("--gpu-accent-rgb", accent.rgb);

    const label = document.createElement("span");
    label.textContent = `GPU ${gpu.index ?? "--"}`;

    const track = document.createElement("span");
    track.className = "power-bar-track";

    const fill = document.createElement("span");
    fill.className = "power-bar-fill";
    fill.style.width = `${percent}%`;
    track.appendChild(fill);

    const value = document.createElement("strong");
    value.textContent = Number.isFinite(usedGb) ? `${formatGb(usedGb)} / ${formatGb(OVERVIEW_MEMORY_BAR_MAX_GB)}` : "--";

    row.append(label, track, value);
    overviewMemoryBars.appendChild(row);
  });
}

function renderOverviewPowerBars(gpus) {
  if (!overviewPowerBars) {
    return;
  }

  overviewPowerBars.replaceChildren();

  if (gpus.length === 0) {
    const empty = document.createElement("p");
    empty.className = "overview-empty";
    empty.textContent = "Awaiting power telemetry.";
    overviewPowerBars.appendChild(empty);
    return;
  }

  gpus.forEach((gpu) => {
    const draw = toFiniteMetric(gpu.power?.draw_watts);
    const percent = Number.isFinite(draw)
      ? clampNumber((draw / OVERVIEW_POWER_BAR_MAX_WATTS) * 100, 0, 100)
      : 0;
    const accent = getGpuAccent(gpu.index);
    const row = document.createElement("div");
    row.className = "power-bar-row";
    row.style.setProperty("--gpu-accent", accent.color);
    row.style.setProperty("--gpu-accent-rgb", accent.rgb);

    const label = document.createElement("span");
    label.textContent = `GPU ${gpu.index ?? "--"}`;

    const track = document.createElement("span");
    track.className = "power-bar-track";

    const fill = document.createElement("span");
    fill.className = "power-bar-fill";
    fill.style.width = `${percent}%`;
    track.appendChild(fill);

    const value = document.createElement("strong");
    value.textContent = Number.isFinite(draw) ? `${draw.toFixed(1)} W` : "--";

    row.append(label, track, value);
    overviewPowerBars.appendChild(row);
  });
}

function renderOverviewLegend(gpus) {
  if (!overviewUtilizationLegend) {
    return;
  }

  overviewUtilizationLegend.replaceChildren();

  if (gpus.length === 0) {
    const empty = document.createElement("span");
    empty.className = "overview-empty";
    empty.textContent = "Awaiting GPU trend data.";
    overviewUtilizationLegend.appendChild(empty);
    return;
  }

  gpus.forEach((gpu) => {
    const accent = getGpuAccent(gpu.index);
    const item = document.createElement("span");
    item.className = "legend-item";
    item.style.setProperty("--gpu-accent", accent.color);
    item.textContent = `GPU ${gpu.index ?? "--"}`;
    overviewUtilizationLegend.appendChild(item);
  });
}

function renderGpuDetailView(gpus) {
  if (!currentSnapshot) {
    renderEmptyGpuDetail(
      `GPU ${currentRoute.gpuIndex ?? "--"}`,
      "Awaiting telemetry",
      "Loading",
      "warning",
      "Waiting for the first GPU snapshot before rendering this view.",
    );
    return;
  }

  const gpu = gpus.find((candidate) => candidate.index === currentRoute.gpuIndex);

  if (!gpu) {
    renderEmptyGpuDetail(
      `GPU ${currentRoute.gpuIndex ?? "--"}`,
      "GPU unavailable",
      "Missing",
      "warning",
      "This GPU is not present in the latest snapshot. Choose another GPU or return to the overview.",
    );
    return;
  }

  const health = getGpuHealth(gpu);
  const utilization = normalizePercent(gpu.utilization?.gpu_percent);
  const memoryPercent = normalizePercent(gpu.memory?.percent);
  const accent = getGpuAccent(gpu.index);
  const history = histories.get(getGpuKey(gpu)) || [];

  gpuDetailView.style.setProperty("--gpu-accent", accent.color);
  gpuDetailView.style.setProperty("--gpu-accent-rgb", accent.rgb);
  detailGpuIndex.textContent = `GPU ${gpu.index ?? "--"}`;
  detailGpuName.textContent = gpu.name || "NVIDIA GPU";
  detailGpuHealth.textContent = health.label;
  detailGpuHealth.dataset.status = health.level;
  detailIntro.textContent = `Focused telemetry for GPU ${gpu.index ?? "--"}. Process details and unsupported NVML fields stay contained here.`;
  detailUtilization.textContent = formatPercent(utilization);
  detailMemory.textContent = formatPercent(memoryPercent);
  detailTemperature.textContent = formatTemperature(gpu.temperature_c);
  detailPower.textContent = formatPower(gpu.power);
  detailFan.textContent = formatFan(gpu.fan_speed_percent);

  if (detailHistoryChip) {
    detailHistoryChip.textContent = history.length === 1 ? "1 sample" : `${history.length} samples`;
  }
  if (detailUpdatedChip) {
    detailUpdatedChip.textContent = formatTimestamp(currentSnapshot.timestamp);
  }
  if (detailMemoryChip) {
    detailMemoryChip.textContent = formatMemory(gpu.memory);
  }
  if (detailUuidChip) {
    detailUuidChip.textContent = gpu.uuid ? shortUuid(gpu.uuid) : "UUID unavailable";
  }

  renderDetailMetricGrid(gpu);
  renderDetailMemoryBars(gpu);
  renderDetailTechnicalGrid(gpu);
  renderDetailUnavailableMetrics(gpu.unavailable_metrics);
  renderDetailProcessList(gpu.processes);
  renderDetailHistoryCharts(history, accent);
}

function renderEmptyGpuDetail(indexLabel, name, healthLabel, healthLevel, intro) {
  detailGpuIndex.textContent = indexLabel;
  detailGpuName.textContent = name;
  detailGpuHealth.textContent = healthLabel;
  detailGpuHealth.dataset.status = healthLevel;
  detailIntro.textContent = intro;
  detailUtilization.textContent = "--";
  detailMemory.textContent = "--";
  detailTemperature.textContent = "--";
  detailPower.textContent = "--";
  detailFan.textContent = "--";

  if (detailHistoryChip) {
    detailHistoryChip.textContent = "--";
  }
  if (detailUpdatedChip) {
    detailUpdatedChip.textContent = "--";
  }
  if (detailMemoryChip) {
    detailMemoryChip.textContent = "--";
  }
  if (detailUuidChip) {
    detailUuidChip.textContent = "--";
  }

  detailMetricGrid?.replaceChildren(makeDetailEmpty("Detailed telemetry is waiting for a matching GPU snapshot."));
  detailMemoryBars?.replaceChildren(makeDetailEmpty("Memory breakdown is unavailable until this GPU is present."));
  detailTechnicalGrid?.replaceChildren(makeDetailEmpty("NVML field details are unavailable for this route."));
  detailUnavailableList?.replaceChildren(makeUnavailableItem("No unavailable metric report is available yet.", "warning"));
  detailProcessNotices?.replaceChildren();
  detailProcessList?.replaceChildren(makeDetailEmpty("Process data is unavailable until this GPU is present."));
  if (detailProcessCount) {
    detailProcessCount.textContent = "--";
  }
  renderDetailHistoryCharts([], getGpuAccent(currentRoute.gpuIndex));
}

function renderDetailMetricGrid(gpu) {
  if (!detailMetricGrid) {
    return;
  }

  const memory = gpu.memory || {};
  const power = gpu.power || {};
  const clocks = gpu.clocks || {};
  const metrics = [
    ["GPU Utilization", formatPercent(normalizePercent(gpu.utilization?.gpu_percent)), metricDetail(gpu, ["utilization"], "Streaming processor load")],
    [
      "Memory Controller",
      formatPercent(normalizePercent(gpu.utilization?.memory_percent)),
      metricDetail(gpu, ["utilization"], "Memory controller load"),
    ],
    ["Memory Used", formatMibOrUnavailable(memory.used_mib), metricDetail(gpu, ["memory"], "Framebuffer used")],
    ["Memory Free", formatMibOrUnavailable(memory.free_mib), metricDetail(gpu, ["memory"], "Framebuffer free")],
    ["Memory Total", formatMibOrUnavailable(memory.total_mib), metricDetail(gpu, ["memory"], "Visible capacity")],
    ["Memory Load", formatPercent(normalizePercent(memory.percent)), metricDetail(gpu, ["memory"], "Used capacity")],
    ["Temperature", formatTemperature(gpu.temperature_c), metricDetail(gpu, ["temperature"], "GPU core temperature")],
    ["Power Draw", formatWatts(power.draw_watts, 1), metricDetail(gpu, ["power_draw"], "Current board power")],
    ["Power Limit", formatWatts(power.limit_watts, 0), metricDetail(gpu, ["power_limit"], "Configured power ceiling")],
    ["Fan Speed", formatFan(gpu.fan_speed_percent), metricDetail(gpu, ["fan_speed"], "Fan duty cycle")],
    ["Graphics Clock", formatMhz(clocks.graphics_mhz), metricDetail(gpu, ["graphics_clock"], "Graphics clock")],
    ["Memory Clock", formatMhz(clocks.memory_mhz), metricDetail(gpu, ["memory_clock"], "Memory clock")],
  ];

  detailMetricGrid.replaceChildren(...metrics.map(([label, value, detail]) => makeDetailMetricItem(label, value, detail)));
}

function renderDetailMemoryBars(gpu) {
  if (!detailMemoryBars) {
    return;
  }

  const memory = gpu.memory || {};
  const usedPercent = normalizePercent(memory.percent);
  const freePercent =
    Number.isFinite(memory.free_mib) && Number.isFinite(memory.total_mib) && memory.total_mib > 0
      ? normalizePercent((memory.free_mib / memory.total_mib) * 100)
      : null;
  const rows = [
    ["Used", formatMibOrUnavailable(memory.used_mib), usedPercent, "used"],
    ["Free", formatMibOrUnavailable(memory.free_mib), freePercent, "free"],
    ["Total", formatMibOrUnavailable(memory.total_mib), Number.isFinite(memory.total_mib) ? 100 : null, "total"],
  ];

  detailMemoryBars.replaceChildren(
    ...rows.map(([label, value, percent, kind]) => makeMemoryBar(label, value, percent, kind)),
  );
}

function renderDetailTechnicalGrid(gpu) {
  if (!detailTechnicalGrid) {
    return;
  }

  const clocks = gpu.clocks || {};
  const items = [
    ["Index", `GPU ${gpu.index ?? "--"}`, "NVML device index"],
    ["UUID", gpu.uuid || "Unavailable", metricDetail(gpu, ["uuid"], "Stable device identifier")],
    ["Name", gpu.name || "Unavailable", metricDetail(gpu, ["name"], "NVML device name")],
    ["Graphics Clock", formatMhz(clocks.graphics_mhz), metricDetail(gpu, ["graphics_clock"], "Current graphics clock")],
    ["Memory Clock", formatMhz(clocks.memory_mhz), metricDetail(gpu, ["memory_clock"], "Current memory clock")],
    ["Snapshot", formatTimestamp(currentSnapshot?.timestamp), "Last API snapshot timestamp"],
  ];

  detailTechnicalGrid.replaceChildren(...items.map(([label, value, detail]) => makeDetailMetricItem(label, value, detail)));
}

function renderDetailUnavailableMetrics(unavailableMetrics) {
  if (!detailUnavailableList) {
    return;
  }

  const items = Array.isArray(unavailableMetrics) ? unavailableMetrics : [];
  if (items.length === 0) {
    detailUnavailableList.replaceChildren(makeUnavailableItem("All requested NVML metrics returned for this GPU.", "ok"));
    return;
  }

  detailUnavailableList.replaceChildren(
    ...items.map((item) =>
      makeUnavailableItem(`${formatMetricName(item.metric)} unavailable: ${item.reason || "No reason reported."}`, "warning"),
    ),
  );
}

function renderDetailProcessList(processPayload) {
  if (!detailProcessList || !detailProcessNotices) {
    return;
  }

  const items = Array.isArray(processPayload?.items) ? processPayload.items : [];
  const unavailableSources = Array.isArray(processPayload?.unavailable_sources)
    ? processPayload.unavailable_sources
    : [];
  const count = Number.isFinite(processPayload?.count) ? processPayload.count : items.length;
  const redactedFields = Array.isArray(processPayload?.redacted_fields)
    ? processPayload.redacted_fields
    : [];
  const hasHiddenProcessDetails = redactedFields.includes("processes");

  if (detailProcessCount) {
    detailProcessCount.textContent = hasHiddenProcessDetails
      ? count === 1
        ? "1 hidden process"
        : `${count} hidden processes`
      : count === 1
        ? "1 process"
        : `${count} processes`;
  }

  detailProcessNotices.replaceChildren();
  if (processPayload?.redacted) {
    const redactionLabel = redactedFields.length > 0
      ? redactedFields.map(formatMetricName).join(", ")
      : "configured process fields";
    detailProcessNotices.appendChild(
      makeProcessNotice(
        processPayload.redaction_reason ||
          `Runtime privacy redaction active for ${redactionLabel}.`,
      ),
    );
  }

  unavailableSources.forEach((source) => {
    detailProcessNotices.appendChild(
      makeProcessNotice(`${formatMetricName(source.metric)} unavailable: ${source.reason}`),
    );
  });

  if (hasHiddenProcessDetails) {
    detailProcessList.replaceChildren(
      makeDetailEmpty("GPU process details are hidden by server privacy settings."),
    );
    return;
  }

  if (items.length === 0) {
    detailProcessList.replaceChildren(makeDetailEmpty("No GPU processes are reported for this GPU."));
    return;
  }

  detailProcessList.replaceChildren(...items.map(makeProcessItem));
}

function renderDetailHistoryCharts(history, accent) {
  renderDetailHistoryChart(detailHistoryUtilization, history, "utilization", 100, accent.color, {
    axisTicks: [0, 50, 100],
    axisSuffix: "%",
    enableTooltip: true,
    tooltipTitle: "GPU Utilization",
    tooltipLabel: "Utilization",
    formatTooltipValue: formatPercent,
  });
  renderDetailHistoryChart(detailHistoryMemory, history, "memory_gb", OVERVIEW_MEMORY_BAR_MAX_GB, "#f3bb52", {
    axisTicks: [0, 12, 24],
    axisSuffix: " GB",
    enableTooltip: true,
    tooltipTitle: "Memory Used",
    tooltipLabel: "Used",
    formatTooltipValue: formatGb,
  });
  renderDetailHistoryChart(detailHistoryTemperature, history, "temperature", 110, "#3ee59a", {
    axisTicks: [0, 55, 90, 110],
    axisSuffix: " C",
    dangerZoneStart: 90,
    enableTooltip: true,
    tooltipTitle: "Temperature",
    tooltipLabel: "Temperature",
    formatTooltipValue: formatTemperature,
  });
}

function renderDetailHistoryChart(svg, history, metric, maxValue, color, options = {}) {
  if (!svg) {
    return;
  }

  const box = parseViewBox(svg, 620, 180);
  const padding = {
    top: 18,
    right: 18,
    bottom: 18,
    left: 62,
  };
  const plotWidth = box.width - padding.left - padding.right;
  const sourceHistory = Array.isArray(history) ? history : [];
  const axisTicks = options.axisTicks || [0, maxValue];
  const gridLines = axisTicks.map((tick) => {
    const y = yForChartValue(tick, maxValue, box, padding);
    const className = tick === 0 || tick === maxValue ? "overview-chart-boundary" : "overview-chart-gridline";
    return `<line class="${className}" x1="${padding.left}" y1="${y.toFixed(1)}" x2="${box.width - padding.right}" y2="${y.toFixed(1)}"></line>`;
  });
  const axisLabels = axisTicks
    .map((tick) => {
      const y = yForChartValue(tick, maxValue, box, padding);
      return `<text class="overview-chart-axis-label" x="${padding.left - 9}" y="${y.toFixed(1)}" text-anchor="end" dominant-baseline="middle">${tick}${options.axisSuffix || ""}</text>`;
    })
    .join("");
  const dangerZone = Number.isFinite(options.dangerZoneStart)
    ? makeChartDangerZone(box, padding, maxValue, options.dangerZoneStart)
    : "";
  const values = sourceHistory.map((point) => point[metric]).filter(Number.isFinite);
  const hitArea = options.enableTooltip
    ? `<rect class="overview-chart-hit-area" x="0" y="0" width="${box.width}" height="${box.height}"></rect>`
    : "";

  if (options.enableTooltip) {
    svg._tooltipData = {
      box,
      color,
      formatTooltipValue: options.formatTooltipValue,
      history: sourceHistory,
      maxValue,
      metric,
      padding,
      tooltipLabel: options.tooltipLabel,
      tooltipTitle: options.tooltipTitle,
    };
  } else {
    delete svg._tooltipData;
  }

  if (values.length === 0) {
    svg.innerHTML = `${dangerZone}${gridLines.join("")}${axisLabels}${makeEmptyChartLine(box, padding.left, padding.right, padding.bottom)}${hitArea}`;
    return;
  }

  const points = values.map((value, index) => {
    const x =
      values.length === 1
        ? padding.left
        : padding.left + (index / (values.length - 1)) * plotWidth;
    const y = yForChartValue(value, maxValue, box, padding);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  if (values.length === 1) {
    points.push(`${(box.width - padding.right).toFixed(1)},${points[0].split(",")[1]}`);
  }

  svg.innerHTML = `
    ${dangerZone}
    ${gridLines.join("")}
    ${axisLabels}
    <polyline class="overview-chart-line" style="--series-color: ${color}" points="${points.join(" ")}"></polyline>
    ${hitArea}
  `;
}

function makeDetailMetricItem(label, value, detail) {
  const item = document.createElement("article");
  item.className = "detail-metric";
  if (value === "Unavailable") {
    item.dataset.status = "warning";
  }

  const labelElement = document.createElement("span");
  labelElement.className = "metric-label";
  labelElement.textContent = label;

  const valueElement = document.createElement("strong");
  valueElement.textContent = value;

  const detailElement = document.createElement("small");
  detailElement.textContent = detail;

  item.append(labelElement, valueElement, detailElement);
  return item;
}

function makeMemoryBar(label, value, percent, kind) {
  const row = document.createElement("div");
  row.className = "memory-breakdown-row";
  row.dataset.kind = kind;

  const header = document.createElement("div");
  header.className = "memory-breakdown-header";

  const labelElement = document.createElement("span");
  labelElement.textContent = label;

  const valueElement = document.createElement("strong");
  valueElement.textContent = value;

  const track = document.createElement("span");
  track.className = "memory-breakdown-track";

  const fill = document.createElement("span");
  fill.className = "memory-breakdown-fill";
  fill.style.width = Number.isFinite(percent) ? `${percent}%` : "0%";
  track.appendChild(fill);

  const percentElement = document.createElement("small");
  percentElement.textContent = Number.isFinite(percent) ? formatPercent(percent) : "Unavailable";

  header.append(labelElement, valueElement);
  row.append(header, track, percentElement);
  return row;
}

function makeUnavailableItem(message, level) {
  const item = document.createElement("li");
  item.dataset.status = level;
  item.textContent = message;
  return item;
}

function makeDetailEmpty(message) {
  const empty = document.createElement("p");
  empty.className = "detail-empty";
  empty.textContent = message;
  return empty;
}

function makeProcessNotice(message) {
  const notice = document.createElement("p");
  notice.className = "process-notice";
  notice.textContent = message;
  return notice;
}

function updateGpuCard(card, gpu) {
  const health = getGpuHealth(gpu);
  const utilization = normalizePercent(gpu.utilization?.gpu_percent);
  const memoryPercent = normalizePercent(gpu.memory?.percent);
  const history = histories.get(getGpuKey(gpu)) || [];
  const accent = getGpuAccent(gpu.index);

  card.style.setProperty("--gpu-accent", accent.color);
  card.style.setProperty("--gpu-accent-rgb", accent.rgb);
  card.href = `#gpu-${gpu.index ?? 0}`;
  card.setAttribute("aria-label", `Open details for GPU ${gpu.index ?? "--"} ${gpu.name || "NVIDIA GPU"}`);
  card.querySelector(".gpu-index").textContent = `GPU ${gpu.index ?? "--"}`;
  card.querySelector(".gpu-name").textContent = gpu.name || "NVIDIA GPU";
  card.querySelector(".gpu-health").textContent = health.label;
  card.querySelector(".gpu-health").dataset.status = health.level;
  card.querySelector(".utilization-value").textContent = formatPercent(utilization);
  card.querySelector(".memory-value").textContent = formatMemory(gpu.memory);
  card.querySelector(".temperature-value").textContent = formatTemperature(gpu.temperature_c);
  card.querySelector(".power-value").textContent = formatPower(gpu.power);
  card.querySelector(".fan-value").textContent = formatFan(gpu.fan_speed_percent);
  card.querySelector(".utilization-bar").style.width = `${utilization ?? 0}%`;
  card.querySelector(".memory-bar").style.width = `${memoryPercent ?? 0}%`;
  renderChart(card.querySelector(".chart-utilization"), history, "utilization", 100);
  renderChart(card.querySelector(".chart-memory"), history, "memory", 100);
  renderChart(card.querySelector(".chart-temperature"), history, "temperature", 100);
}

function renderPollFailure(error) {
  if (!hasRenderedSnapshot) {
    renderError(error);
    return;
  }

  const stale = failureCount >= STALE_FAILURE_THRESHOLD;
  statePanel.dataset.state = stale ? "stale" : "loading";
  stateMessage.textContent = stale
    ? `Telemetry is stale after ${failureCount} failed refresh attempts. Retrying automatically.`
    : `Refresh failed. Retrying automatically. ${error.message || ""}`.trim();
  setOverallStatus(stale ? "Stale" : "Retrying", "warning");
}

function renderError(error) {
  currentSnapshot = null;
  renderGpuNavigation([]);
  clearGpuCards();
  statePanel.dataset.state = "error";
  stateMessage.textContent = error.message || "GPU telemetry could not be loaded.";
  setOverallStatus("Offline", "error");
  renderDiagnostics(null, [{ message: error.message || "GPU telemetry could not be loaded." }]);
  renderCurrentView();
}

function setDiagnosticsLoading() {
  diagnosticsPanel.dataset.state = "loading";
  diagnosticsStatus.textContent = "Checking";
  diagnosticsStatus.dataset.status = "warning";
  diagnosticsGrid.replaceChildren();
  diagnosticsIssues.replaceChildren(makeIssueItem("Collecting NVIDIA runtime diagnostics.", "warning"));
}

function renderDiagnostics(diagnostics, errors = []) {
  diagnosticsGrid.replaceChildren();
  diagnosticsIssues.replaceChildren();

  if (!diagnostics) {
    diagnosticsPanel.dataset.state = "error";
    diagnosticsStatus.textContent = "Unavailable";
    diagnosticsStatus.dataset.status = "error";
    const issueMessages = errors.map((error) => error.message).filter(Boolean);
    if (issueMessages.length === 0) {
      issueMessages.push("Diagnostics are unavailable until the API returns a snapshot.");
    }
    issueMessages.forEach((message) => {
      diagnosticsIssues.appendChild(makeIssueItem(message, "error"));
    });
    return;
  }

  const nvml = diagnostics.nvml || {};
  const nvidiaSmi = diagnostics.nvidia_smi || {
    available: Boolean(diagnostics.nvidia_smi_path),
    path: diagnostics.nvidia_smi_path,
  };
  const checks = Array.isArray(diagnostics.checks) ? diagnostics.checks : [];
  const hasProblem = checks.some((check) => check.level && check.level !== "ok") || errors.length > 0;
  const status = diagnostics.status || (hasProblem ? "attention" : "ok");
  const runtimePrivacy = diagnostics.runtime_config?.privacy || {};
  const hiddenPrivacyFields = [];
  if (runtimePrivacy.show_process_details === false) {
    hiddenPrivacyFields.push("process details");
  } else {
    if (runtimePrivacy.show_command_lines === false) {
      hiddenPrivacyFields.push("command lines");
    }
    if (runtimePrivacy.show_usernames === false) {
      hiddenPrivacyFields.push("usernames");
    }
  }

  diagnosticsPanel.dataset.state = status;
  diagnosticsStatus.textContent = hasProblem ? "Attention" : "Ready";
  diagnosticsStatus.dataset.status = hasProblem ? "warning" : "ok";

  diagnosticsGrid.appendChild(
    makeDiagnosticItem(
      "NVML",
      nvml.available ? "Available" : "Unavailable",
      nvml.nvml_version ? `Version ${nvml.nvml_version}` : "Runtime library check",
      nvml.available ? "ok" : "error",
    ),
  );
  diagnosticsGrid.appendChild(
    makeDiagnosticItem(
      "Driver",
      nvml.driver_version || diagnostics.driver_version || "Unavailable",
      "Detected NVIDIA driver",
      nvml.driver_version || diagnostics.driver_version ? "ok" : "warning",
    ),
  );
  diagnosticsGrid.appendChild(
    makeDiagnosticItem(
      "nvidia-smi",
      nvidiaSmi.available ? "Found" : "Missing",
      nvidiaSmi.path || "Not found on PATH",
      nvidiaSmi.available ? "ok" : "warning",
    ),
  );
  diagnosticsGrid.appendChild(
    makeDiagnosticItem(
      "GPU Visibility",
      Number.isFinite(nvml.gpu_count) ? String(nvml.gpu_count) : "--",
      "Visible to NVML",
      Number.isFinite(nvml.gpu_count) && nvml.gpu_count > 0 ? "ok" : "warning",
    ),
  );
  diagnosticsGrid.appendChild(
    makeDiagnosticItem(
      "Privacy",
      hiddenPrivacyFields.length > 0 ? "Redacting" : "Default",
      hiddenPrivacyFields.length > 0
        ? `Hiding ${hiddenPrivacyFields.join(", ")}`
        : "Process fields visible when permissions allow",
      "ok",
    ),
  );

  const issueItems = [
    ...errors.map((error) => [firstPresent(error.message, error.hint), "error"]),
    ...checks
      .filter((check) => check.level && check.level !== "ok")
      .map((check) => [check.message, check.level]),
  ].filter(([message]) => message);

  const commonIssues = Array.isArray(diagnostics.common_issues) ? diagnostics.common_issues : [];
  if (issueItems.length === 0) {
    diagnosticsIssues.appendChild(makeIssueItem("No runtime issues reported.", "ok"));
  } else {
    issueItems.forEach(([message, level]) => {
      diagnosticsIssues.appendChild(makeIssueItem(message, level));
    });
  }

  commonIssues.forEach((message) => {
    diagnosticsIssues.appendChild(makeIssueItem(`Check: ${message}`, hasProblem ? "warning" : "ok"));
  });
}

function makeDiagnosticItem(label, value, detail, level) {
  const item = document.createElement("article");
  item.className = "diagnostic-item";
  item.dataset.status = level;

  const labelElement = document.createElement("span");
  labelElement.className = "metric-label";
  labelElement.textContent = label;

  const valueElement = document.createElement("strong");
  valueElement.textContent = value;

  const detailElement = document.createElement("small");
  detailElement.textContent = detail;

  item.append(labelElement, valueElement, detailElement);
  return item;
}

function makeIssueItem(message, level) {
  const item = document.createElement("li");
  item.dataset.status = level;
  item.textContent = message;
  return item;
}

function makeProcessItem(process) {
  const item = document.createElement("article");
  item.className = "process-item";
  const redactedFields = Array.isArray(process.redacted_fields) ? process.redacted_fields : [];

  const primary = document.createElement("div");
  primary.className = "process-primary";

  const name = document.createElement("strong");
  name.textContent = process.name || `PID ${process.pid ?? "--"}`;

  const type = document.createElement("span");
  type.textContent = formatProcessTypes(process.types);

  primary.append(name, type);

  const meta = document.createElement("div");
  meta.className = "process-meta";
  [
    `PID ${process.pid ?? "--"}`,
    redactedFields.includes("username") ? "Username redacted" : process.username || "User unavailable",
    process.status || "Status unavailable",
    formatProcessMemory(process),
  ].forEach((value) => {
    const piece = document.createElement("span");
    piece.textContent = value;
    meta.appendChild(piece);
  });

  const command = document.createElement("p");
  command.className = "process-command";
  command.textContent = redactedFields.includes("command_line")
    ? "Command line redacted"
    : process.command_line || "Command line unavailable";

  item.append(primary, meta, command);

  const unavailable = Array.isArray(process.detail_unavailable) ? process.detail_unavailable : [];
  if (unavailable.length > 0) {
    const details = document.createElement("p");
    details.className = "process-notice";
    details.textContent = unavailable
      .map((detail) => `${formatMetricName(detail.field)}: ${detail.reason}`)
      .join(" ");
    item.appendChild(details);
  }

  return item;
}

function recordHistory(gpu) {
  const key = getGpuKey(gpu);
  const history = histories.get(key) || [];
  history.push({
    time: Date.now(),
    utilization: normalizePercent(gpu.utilization?.gpu_percent),
    memory: normalizePercent(gpu.memory?.percent),
    memory_gb: mibToGb(toFiniteMetric(gpu.memory?.used_mib)),
    temperature: clampNumber(gpu.temperature_c, 0, 110),
  });

  if (history.length > HISTORY_LIMIT) {
    history.splice(0, history.length - HISTORY_LIMIT);
  }

  histories.set(key, history);
}

function renderChart(svg, history, metric, maxValue) {
  const values = history
    .map((point) => point[metric])
    .filter((value) => Number.isFinite(value));
  const width = 120;
  const height = 42;
  const padding = 3;

  if (values.length === 0) {
    svg.innerHTML = `<line class="chart-baseline" x1="0" y1="${height - padding}" x2="${width}" y2="${height - padding}"></line>`;
    return;
  }

  const points = values.map((value, index) => {
    const x = values.length === 1 ? width : (index / (values.length - 1)) * width;
    const ratio = Math.max(0, Math.min(1, value / maxValue));
    const y = height - padding - ratio * (height - padding * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  if (values.length === 1) {
    points.unshift(`0,${points[0].split(",")[1]}`);
  }

  svg.innerHTML = `
    <line class="chart-baseline" x1="0" y1="${height - padding}" x2="${width}" y2="${height - padding}"></line>
    <polyline class="chart-line" points="${points.join(" ")}"></polyline>
  `;
}

function parseViewBox(svg, fallbackWidth, fallbackHeight) {
  const values = String(svg.getAttribute("viewBox") || "")
    .split(/\s+/)
    .map(Number);

  if (values.length === 4 && Number.isFinite(values[2]) && Number.isFinite(values[3])) {
    return { width: values[2], height: values[3] };
  }

  return { width: fallbackWidth, height: fallbackHeight };
}

function makeEmptyChartLine(box, leftPadding, rightPadding = leftPadding, bottomPadding = rightPadding) {
  const y = box.height - bottomPadding;
  return `<polyline class="overview-chart-line is-empty" points="${leftPadding},${y} ${box.width - rightPadding},${y}"></polyline>`;
}

function clearGpuCards() {
  gpuGrid.replaceChildren();
  renderedCards.clear();
}

function getOverallHealth(gpus) {
  if (gpus.some((gpu) => getGpuHealth(gpu).level === "error")) {
    return { label: "Attention", level: "error" };
  }

  if (gpus.some((gpu) => getGpuHealth(gpu).level === "warning")) {
    return { label: "Elevated", level: "warning" };
  }

  return { label: "Nominal", level: "ok" };
}

function healthDetail(level) {
  if (level === "error") {
    return "Thermal or memory pressure";
  }

  if (level === "warning") {
    return "Elevated activity detected";
  }

  return "All GPUs within range";
}

function getGpuHealth(gpu) {
  const utilization = normalizePercent(gpu.utilization?.gpu_percent);
  const memoryPercent = normalizePercent(gpu.memory?.percent);
  const temperature = Number.isFinite(gpu.temperature_c) ? gpu.temperature_c : null;

  if ((temperature ?? 0) >= 88 || (memoryPercent ?? 0) >= 95) {
    return { label: "Hot", level: "error" };
  }

  if ((temperature ?? 0) >= 80 || (utilization ?? 0) >= 90 || (memoryPercent ?? 0) >= 80) {
    return { label: "Busy", level: "warning" };
  }

  return { label: "Stable", level: "ok" };
}

function setOverallStatus(label, level) {
  overallStatus.textContent = label;
  overallStatus.dataset.status = level;
}

function formatTimestamp(value) {
  if (!value) {
    return "--";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return formatClock(date);
}

function formatClock(date) {
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatPercent(value) {
  return value === null ? "Unavailable" : `${Math.round(value)}%`;
}

function formatMemory(memory) {
  if (!memory || memory.used_mib == null || memory.total_mib == null) {
    return "Unavailable";
  }

  const used = formatMib(memory.used_mib);
  const total = formatMib(memory.total_mib);
  const percent = formatPercent(normalizePercent(memory.percent));
  return `${used} / ${total} (${percent})`;
}

function formatMibOrUnavailable(value) {
  return Number.isFinite(value) ? formatMib(value) : "Unavailable";
}

function mibToGb(value) {
  return Number.isFinite(value) ? value / 1024 : null;
}

function formatGb(value) {
  return Number.isFinite(value) ? `${value.toFixed(1)} GB` : "Unavailable";
}

function formatMib(value) {
  if (!Number.isFinite(value)) {
    return "--";
  }

  return value >= 1024 ? `${(value / 1024).toFixed(1)} GiB` : `${Math.round(value)} MiB`;
}

function formatTemperature(value) {
  return Number.isFinite(value) ? `${value} C` : "Unavailable";
}

function formatPower(power) {
  if (!power || power.draw_watts == null) {
    return "Unavailable";
  }

  const draw = `${Number(power.draw_watts).toFixed(1)} W`;
  if (power.limit_watts == null) {
    return draw;
  }

  return `${draw} / ${Number(power.limit_watts).toFixed(0)} W`;
}

function formatWatts(value, digits = 1) {
  const number = toFiniteMetric(value);
  return Number.isFinite(number) ? `${number.toFixed(digits)} W` : "Unavailable";
}

function formatFan(value) {
  return Number.isFinite(value) ? `${value}%` : "Unavailable";
}

function formatMhz(value) {
  return Number.isFinite(value) ? `${Math.round(value)} MHz` : "Unavailable";
}

function formatProcessTypes(types) {
  if (!Array.isArray(types) || types.length === 0) {
    return "GPU";
  }

  return types.map(formatMetricName).join(" + ");
}

function formatProcessMemory(process) {
  if (Number.isFinite(process.gpu_memory_mib)) {
    return `${formatMib(process.gpu_memory_mib)} GPU`;
  }

  return "GPU memory unavailable";
}

function formatMetricName(value) {
  if (!value) {
    return "Metric";
  }

  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function metricDetail(gpu, metrics, fallback) {
  const reason = findUnavailableReason(gpu, metrics);
  return reason ? `Unavailable: ${reason}` : fallback;
}

function findUnavailableReason(gpu, metrics) {
  const unavailable = Array.isArray(gpu?.unavailable_metrics) ? gpu.unavailable_metrics : [];
  const metricNames = new Set(metrics);
  const item = unavailable.find((entry) => metricNames.has(entry.metric));
  return item?.reason || "";
}

function firstPresent(...values) {
  return values.find((value) => value) || "";
}

function sumValues(values) {
  return values.reduce((total, value) => total + value, 0);
}

function averageValues(values) {
  if (values.length === 0) {
    return null;
  }

  return sumValues(values) / values.length;
}

function toFiniteMetric(value) {
  if (value == null) {
    return null;
  }

  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function normalizePercent(value) {
  if (!Number.isFinite(value)) {
    return null;
  }

  return Math.max(0, Math.min(100, Number(value)));
}

function clampNumber(value, min, max) {
  if (!Number.isFinite(value)) {
    return null;
  }

  return Math.max(min, Math.min(max, Number(value)));
}

function getGpuKey(gpu) {
  return gpu.uuid || `index-${gpu.index ?? "unknown"}`;
}

function getGpuAccent(index) {
  const safeIndex = Number.isFinite(Number(index)) ? Math.abs(Number(index)) : 0;
  return GPU_ACCENTS[safeIndex % GPU_ACCENTS.length];
}

function shortUuid(uuid) {
  if (!uuid) {
    return "--";
  }

  const text = String(uuid);
  return text.length > 18 ? `${text.slice(0, 8)}...${text.slice(-6)}` : text;
}

function firstErrorMessage(snapshot) {
  const error = Array.isArray(snapshot.errors) ? snapshot.errors[0] : null;
  if (!error) {
    return "";
  }

  return [error.message, error.hint].filter(Boolean).join(" ");
}

document.addEventListener("visibilitychange", handleVisibilityChange);
initializeTheme();
initializeRouting();
initializeChartInteractions();
requestSnapshot();
