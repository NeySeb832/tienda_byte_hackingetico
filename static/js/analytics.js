// BI dashboard charts (ECharts served locally). Data comes from a json_script block: no inline JS.
document.addEventListener("DOMContentLoaded", function () {
  "use strict";
  var source = document.getElementById("bi-data");
  if (!source || !window.echarts) { return; }
  var data = JSON.parse(source.textContent);
  var dark = document.documentElement.classList.contains("dark");
  var text = dark ? "#cbd5e1" : "#334155";
  var palette = ["#a78bfa", "#22d3ee", "#f472b6", "#a3e635", "#fbbf24", "#60a5fa", "#fb7185", "#34d399"];
  var cop = new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });
  var money = function (value) { return value == null ? "" : cop.format(value); };
  var millions = function (v) { return (v / 1e6).toFixed(0) + " M"; };
  var base = { color: palette, textStyle: { color: text } };
  var bars = function (rows, horizontal) {
    var category = { type: "category", data: rows.map(function (r) { return r.name; }), axisLabel: { color: text } };
    var value = { type: "value", axisLabel: { color: text, formatter: millions } };
    if (horizontal) { category.inverse = true; }
    return Object.assign({}, base, {
      tooltip: { trigger: "axis", valueFormatter: money },
      grid: { left: horizontal ? 160 : 50, right: 20, top: 20, bottom: 30 },
      xAxis: horizontal ? value : category,
      yAxis: horizontal ? category : value,
      series: [{ type: "bar", data: rows.map(function (r) { return r.value; }), itemStyle: { borderRadius: 6 } }],
    });
  };
  var pie = function (rows, formatter) {
    return Object.assign({}, base, {
      tooltip: { trigger: "item", valueFormatter: formatter },
      series: [{ type: "pie", radius: ["38%", "62%"], data: rows, label: { color: text, formatter: "{b}: {d} %" } }],
    });
  };
  var options = {
    monthly: Object.assign({}, base, {
      tooltip: { trigger: "axis", valueFormatter: money },
      legend: { top: 0, data: ["Ventas", "Pronóstico"], textStyle: { color: text } },
      grid: { left: 60, right: 20, top: 40, bottom: 40 },
      xAxis: { type: "category", data: data.monthly.labels, axisLabel: { color: text } },
      yAxis: { type: "value", axisLabel: { color: text, formatter: millions } },
      series: [
        { name: "Ventas", type: "line", smooth: true, areaStyle: { opacity: 0.15 }, data: data.monthly.actual },
        { name: "Pronóstico", type: "line", smooth: true, lineStyle: { type: "dashed" }, data: data.monthly.forecast },
      ],
    }),
    categories: bars(data.categories, true),
    stores: bars(data.stores, true),
    channels: pie(data.channels, money),
    segments: pie(data.segments, function (v) { return v + " clientes"; }),
    weekdays: bars(data.weekdays, false),
  };
  var charts = [];
  document.querySelectorAll("[data-chart]").forEach(function (element) {
    var chart = window.echarts.init(element, null, { renderer: "svg" });
    chart.setOption(options[element.getAttribute("data-chart")]);
    charts.push(chart);
  });
  window.addEventListener("resize", function () { charts.forEach(function (c) { c.resize(); }); });
});
