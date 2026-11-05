// Theme toggle + theme-aware Plotly charts + Mermaid diagrams.
(function () {
  const root = document.documentElement;
  const KEY = "cdsh-theme";

  function stored() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function store(v) {
    try { localStorage.setItem(KEY, v); } catch (e) { /* private mode */ }
  }
  function current() {
    const t = root.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark" : "light";
  }

  const saved = stored();
  if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);

  function renderCharts() {
    if (!window.Plotly) return;
    const mode = current();
    document.querySelectorAll("[data-chart]").forEach(function (el) {
      const name = el.getAttribute("data-chart");
      const url = "assets/charts/" + name + "." + mode + ".json";
      fetch(url).then(function (r) { return r.json(); }).then(function (fig) {
        fig.layout = fig.layout || {};
        fig.layout.autosize = true;
        delete fig.layout.width;
        window.Plotly.react(el, fig.data, fig.layout, {
          responsive: true, displaylogo: false, topojsonURL: "assets/topojson/",
          modeBarButtonsToRemove: ["select2d", "lasso2d"]
        });
      }).catch(function () {
        el.innerHTML = '<p class="chart-fallback">Chart could not be loaded.</p>';
      });
    });
  }

  function renderMermaid() {
    if (!window.mermaid) return;
    const nodes = document.querySelectorAll("pre.mermaid");
    nodes.forEach(function (n) {
      if (!n.dataset.src) n.dataset.src = n.textContent;
      n.removeAttribute("data-processed");
      n.textContent = n.dataset.src;
    });
    window.mermaid.initialize({
      startOnLoad: false, securityLevel: "strict",
      theme: current() === "dark" ? "dark" : "neutral",
      fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif'
    });
    window.mermaid.run({ nodes: nodes });
  }

  function label(btn) {
    btn.textContent = current() === "dark" ? "☀ Light" : "☾ Dark";
    btn.setAttribute("aria-label", "Switch to " + (current() === "dark" ? "light" : "dark") + " theme");
  }

  document.addEventListener("DOMContentLoaded", function () {
    const btn = document.querySelector(".theme-toggle");
    if (btn) {
      label(btn);
      btn.addEventListener("click", function () {
        const next = current() === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", next);
        store(next);
        label(btn);
        renderCharts();
        renderMermaid();
      });
    }
    renderCharts();
    renderMermaid();
    if (window.matchMedia) {
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
        if (!root.getAttribute("data-theme")) { renderCharts(); renderMermaid(); if (btn) label(btn); }
      });
    }
  });
})();
