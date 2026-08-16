// Weather tab (historical weather, 1987-present): an interactive chart
// filterable by calendar year and by which measurements to plot, a dynamic
// legend, and PDF export. Shared between the admin app
// (/api/weather/history, JWT auth) and the Owner View
// (/api/owner-view/weather, token auth) - identical markup (same element
// IDs), same as analysis-tab.js, so this one module renders both.
//
// Years are always overlaid on a shared 1 Jan - 31 Dec x-axis, one line per
// selected year, defaulting to the most recent year on file. There used to
// be an "All Years" mode plotting one continuous line across the whole
// record instead; it was dropped once the history reached back to 1987,
// where it compressed 39 years into an unreadable smear and buried the
// year-on-year comparison this tab exists for.
const LWWeatherTab = (() => {
  let _data = null;
  let _bound = false;
  let _firstLoad = true;
  let _selectedYears = new Set();
  let _selectedMetrics = new Set();

  function bind() {
    // Same double-bind guard as analysis-tab.js: the admin app re-runs its
    // bind* helpers on every sign-in without reloading the page, so without
    // this a sign-out/sign-in cycle would stack duplicate listeners.
    if (_bound) return;
    _bound = true;

    document.getElementById("tab-weather").addEventListener("change", (e) => {
      if (e.target.classList.contains("weather-year-cb")) {
        const year = parseInt(e.target.value, 10);
        if (e.target.checked) _selectedYears.add(year); else _selectedYears.delete(year);
        if (_data) _render();
      } else if (e.target.classList.contains("weather-metric-cb")) {
        if (e.target.checked) _selectedMetrics.add(e.target.value); else _selectedMetrics.delete(e.target.value);
        if (_data) _render();
      }
    });

    // Delegated PDF export, identical mechanics to analysis-tab.js's
    // handler - LWCharts.exportPDF() needs no changes for this chart.
    document.getElementById("tab-weather").addEventListener("click", async (e) => {
      const btn = e.target.closest(".chart-pdf-btn");
      if (!btn) return;
      const target = document.getElementById(btn.dataset.target);
      if (!target) return;
      const icon = btn.querySelector("i");
      icon.className = "fa-solid fa-spinner fa-spin";
      btn.disabled = true;
      try {
        const filename = `${btn.dataset.title.replace(/[^a-zA-Z0-9]+/g, "_")}.pdf`;
        await LWCharts.exportPDF(target, { title: btn.dataset.title, filename });
      } catch (err) {
        console.error("PDF export failed:", err);
        LW.toast("Could not create PDF");
      } finally {
        icon.className = "fa-solid fa-file-pdf";
        btn.disabled = false;
      }
    });
  }

  // fetchHistory: () => Promise<data> - each screen supplies its own call
  // (admin: LW.api with a bearer token; owner: LW.api with the link's key).
  async function load(fetchHistory, { onAuthError } = {}) {
    let data;
    try {
      data = await fetchHistory();
    } catch (e) {
      if (LW.isNetworkError(e)) { LW.setOffline(true); return; }
      if (LW.isAuthError(e) && onAuthError) { onAuthError(e); return; }
      console.error("Weather load failed:", e);
      LW.toast("Could not load weather data");
      return;
    }
    LW.setOffline(false);
    _data = data;
    _rebuildFilters(data);
    document.getElementById("weatherLastSynced").textContent = data.last_synced
      ? `Weather data current to ${_formatSynced(data.last_synced)}`
      : "No weather data yet";
    _render();
  }

  // WeatherHistory.timestamp (and therefore last_synced) is naive LOCAL
  // farm time, not UTC (see models.py) - deliberately NOT run through
  // LW.parseServerDate/new Date(), which would treat it as UTC and shift
  // it. The digits are already the farm's own wall clock, so just format
  // them directly.
  function _formatSynced(iso) {
    const [datePart, timePart] = iso.split("T");
    return `${datePart} ${(timePart || "").slice(0, 5)}`;
  }

  function _rebuildFilters(data) {
    if (_firstLoad) {
      // The latest year actually on file, which is not always
      // data.current_year - a new calendar year has no weather rows until
      // the first sync of the year lands, and defaulting to an empty year
      // would open the tab on a blank chart.
      _selectedYears = new Set([data.years.length ? data.years[data.years.length - 1] : data.current_year]);
      _selectedMetrics = new Set(["temp_c"]);
    }

    // Rebuilt only when the set of years/metrics actually changes (mirrors
    // analysis-tab.js's renderVarietyYield() pattern), preserving whichever
    // of the current selection still exists.
    const yearsSig = data.years.join("|");
    const yearEl = document.getElementById("weatherYearFilter");
    if (yearEl.dataset.years !== yearsSig) {
      yearEl.innerHTML = data.years.map((y) => `
        <label class="inline-flex items-center gap-1.5 text-sm mr-3">
          <input type="checkbox" class="weather-year-cb" value="${y}" ${_selectedYears.has(y) ? "checked" : ""}>
          ${y}${y === data.current_year ? " (current)" : ""}
        </label>`).join("");
      yearEl.dataset.years = yearsSig;
    }

    const metricsSig = data.metrics.map((m) => m.key).join("|");
    const metricEl = document.getElementById("weatherMetricFilter");
    if (metricEl.dataset.metrics !== metricsSig) {
      metricEl.innerHTML = data.metrics.map((m) => `
        <label class="inline-flex items-center gap-1.5 text-sm mr-3">
          <input type="checkbox" class="weather-metric-cb" value="${m.key}" ${_selectedMetrics.has(m.key) ? "checked" : ""}>
          ${m.label}
        </label>`).join("");
      metricEl.dataset.metrics = metricsSig;
    }
    _firstLoad = false;
  }

  // day_of_year -> real date, using a fixed non-leap reference year purely
  // for formatting (1 Jan - 31 Dec calendar-year anchor, matching the
  // backend's build_weather_history() - NOT analysis-tab.js's Aug-anchored
  // season_day, a different concept for harvest data).
  function _dayOfYearToDate(dayOfYear) {
    return new Date(2001, 0, dayOfYear); // month 0 = January (0-indexed)
  }
  function _dayOfYearLabel(dayOfYear) {
    return _dayOfYearToDate(dayOfYear).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  // Color scheme: every past year is a shade of blue-gray
  // (lightest = oldest, darkest = most recent), regardless of which metric
  // it is - so a chart with several years and several metrics still reads
  // at a glance as "the past". The current, still-in-progress year is
  // always a shade from this warm/red family instead, on every metric, so
  // it's the one line that unmistakably stands out from history - varied
  // per metric (one shade each) so two metrics' current-year lines shown
  // together are still distinguishable from each other, not just from
  // history.
  const HISTORY_COLORS = ["#cbd5e1", "#94a3b8", "#64748b", "#475569", "#334155", "#1e293b"];
  const CURRENT_YEAR_COLORS = ["#dc2626", "#ea580c", "#e11d48", "#d97706", "#db2777", "#991b1b", "#9a3412", "#9f1239"];

  function _historyColor(rank, count) {
    if (count <= 1) return HISTORY_COLORS[HISTORY_COLORS.length - 1];
    const idx = Math.round((rank / (count - 1)) * (HISTORY_COLORS.length - 1));
    return HISTORY_COLORS[idx];
  }

  function _render() {
    const chartEl = document.getElementById("weatherChart");
    const legendEl = document.getElementById("weatherLegend");

    if (!_selectedMetrics.size) {
      chartEl.innerHTML = `<div class="text-sm text-slate-400 p-8 text-center">Pick at least one measurement above</div>`;
      LWCharts.legend(legendEl, []);
      return;
    }

    const metricsByKey = {};
    _data.metrics.forEach((m) => { metricsByKey[m.key] = m; });
    const metricKeys = _data.metrics.map((m) => m.key).filter((k) => _selectedMetrics.has(k));

    const years = _data.years.filter((y) => _selectedYears.has(y));
    const historyYears = years.filter((y) => y !== _data.current_year);
    const series = [];
    metricKeys.forEach((key, mi) => {
      const m = metricsByKey[key];
      years.forEach((year) => {
        const points = _data.points
          .filter((p) => p.year === year && p[key] != null)
          .map((p) => ({ x: p.day_of_year, y: p[key] }));
        if (!points.length) return;
        const isCurrent = year === _data.current_year;
        const color = isCurrent
          ? CURRENT_YEAR_COLORS[mi % CURRENT_YEAR_COLORS.length]
          : _historyColor(historyYears.indexOf(year), historyYears.length);
        series.push({
          label: `${m.label} — ${year}`, color,
          unit: m.unit, decimals: m.decimals, points, emphasize: isCurrent,
        });
      });
    });

    if (!series.length) {
      chartEl.innerHTML = `<div class="text-sm text-slate-400 p-8 text-center">Pick at least one year above</div>`;
      LWCharts.legend(legendEl, []);
      return;
    }

    const pointEvery = Math.max(1, Math.ceil(Math.max(1, ...series.map((s) => s.points.length)) / 150));

    LWCharts.normalizedLineChart(chartEl, { series, xLabel: _dayOfYearLabel, xMin: 1, pointEvery });
    LWCharts.legend(legendEl, series.map((s) => ({ label: s.label, color: s.color })));
  }

  return { bind, load };
})();
