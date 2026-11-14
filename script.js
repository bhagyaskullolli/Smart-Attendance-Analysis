/* ===== Smart Attendance Analyser - front-end helpers ===== */
(function () {
  "use strict";

  // ---------- colours used by every chart ----------
  var C = { blue: "#2563eb", blueSoft: "rgba(37,99,235,.15)", green: "#16a34a", red: "#ef4444",
            yellow: "#f59e0b", grid: "rgba(100,116,139,.15)" };

  if (window.Chart) {
    Chart.defaults.font.family = "Poppins, system-ui, sans-serif";
    Chart.defaults.color = "#64748b";
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
  }

  function ctx(id) {
    var el = document.getElementById(id);
    return el ? el.getContext("2d") : null;
  }

  // Chart helpers - templates call these with data that came from the database.
  window.SAA = {
    doughnut: function (id, present, absent) {
      var c = ctx(id); if (!c) return;
      new Chart(c, {
        type: "doughnut",
        data: { labels: ["Present", "Absent"],
                datasets: [{ data: [present, absent], backgroundColor: [C.green, C.red], borderWidth: 0, hoverOffset: 6 }] },
        options: { maintainAspectRatio: false, cutout: "68%", plugins: { legend: { position: "bottom" } } }
      });
    },
    line: function (id, labels, values, label) {
      var c = ctx(id); if (!c) return;
      new Chart(c, {
        type: "line",
        data: { labels: labels,
                datasets: [{ label: label || "Attendance %", data: values, borderColor: C.blue, backgroundColor: C.blueSoft,
                             fill: true, tension: .38, pointRadius: 4, pointBackgroundColor: "#fff",
                             pointBorderColor: C.blue, pointBorderWidth: 2, spanGaps: true }] },
        options: { maintainAspectRatio: false,
                   scales: { y: { min: 0, max: 100, grid: { color: C.grid }, ticks: { callback: function (v) { return v + "%"; } } },
                             x: { grid: { display: false } } },
                   plugins: { legend: { display: false } } }
      });
    },
    // stacked present/absent bars + percentage line (daily / weekly / monthly)
    stackedWithLine: function (id, labels, present, absent, percent) {
      var c = ctx(id); if (!c) return;
      new Chart(c, {
        data: { labels: labels,
                datasets: [
                  { type: "bar", label: "Present", data: present, backgroundColor: C.green, borderRadius: 6, stack: "s", yAxisID: "y" },
                  { type: "bar", label: "Absent", data: absent, backgroundColor: C.red, borderRadius: 6, stack: "s", yAxisID: "y" },
                  { type: "line", label: "Attendance %", data: percent, borderColor: C.blue, backgroundColor: C.blue,
                    tension: .35, pointRadius: 3, yAxisID: "y1", spanGaps: true }
                ] },
        options: { maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
                   scales: { x: { stacked: true, grid: { display: false } },
                             y: { stacked: true, beginAtZero: true, grid: { color: C.grid }, title: { display: true, text: "Records" } },
                             y1: { position: "right", min: 0, max: 100, grid: { display: false },
                                   ticks: { callback: function (v) { return v + "%"; } } } },
                   plugins: { legend: { position: "bottom" } } }
      });
    },
    hbar: function (id, labels, values, label) {
      var c = ctx(id); if (!c) return;
      var colors = values.map(function (v) { return v === null ? "#cbd5e1" : v < 75 ? C.red : v < 85 ? C.yellow : v >= 90 ? C.green : C.blue; });
      new Chart(c, {
        type: "bar",
        data: { labels: labels, datasets: [{ label: label || "Attendance %", data: values, backgroundColor: colors, borderRadius: 8 }] },
        options: { maintainAspectRatio: false, indexAxis: "y",
                   scales: { x: { min: 0, max: 100, grid: { color: C.grid }, ticks: { callback: function (v) { return v + "%"; } } },
                             y: { grid: { display: false } } },
                   plugins: { legend: { display: false } } }
      });
    }
  };

  document.addEventListener("DOMContentLoaded", function () {

    // ---------- mobile sidebar ----------
    var sidebar = document.getElementById("sidebar");
    var overlay = document.getElementById("overlay");
    var menuBtn = document.getElementById("menuBtn");
    function toggleMenu(open) {
      if (!sidebar) return;
      sidebar.classList.toggle("open", open);
      if (overlay) overlay.classList.toggle("show", open);
    }
    if (menuBtn) menuBtn.addEventListener("click", function () { toggleMenu(!sidebar.classList.contains("open")); });
    if (overlay) overlay.addEventListener("click", function () { toggleMenu(false); });

    // ---------- confirm before delete (forms with data-confirm) ----------
    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
      form.addEventListener("submit", function (e) {
        if (!window.confirm(form.getAttribute("data-confirm"))) e.preventDefault();
      });
    });

    // ---------- auto-hide success / info messages ----------
    setTimeout(function () {
      document.querySelectorAll(".alert.auto-hide").forEach(function (a) {
        a.style.transition = "opacity .5s"; a.style.opacity = "0";
        setTimeout(function () { a.remove(); }, 500);
      });
    }, 5000);

    // ---------- auto-submit filter forms ----------
    document.querySelectorAll("form[data-autosubmit] select, form[data-autosubmit] input[type=date]").forEach(function (el) {
      el.addEventListener("change", function () { el.form.submit(); });
    });

    // ---------- print buttons ----------
    document.querySelectorAll("[data-print]").forEach(function (b) {
      b.addEventListener("click", function () { window.print(); });
    });

    // ---------- show / hide password ----------
    document.querySelectorAll("[data-toggle-password]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var input = document.getElementById(btn.getAttribute("data-toggle-password"));
        if (!input) return;
        var show = input.type === "password";
        input.type = show ? "text" : "password";
        btn.innerHTML = show ? '<i class="bi bi-eye-slash"></i>' : '<i class="bi bi-eye"></i>';
      });
    });

    // ---------- Mark Attendance page ----------
    var markForm = document.getElementById("markForm");
    if (markForm) {
      var rows = Array.prototype.slice.call(markForm.querySelectorAll("tr[data-student]"));
      var cP = document.getElementById("cntPresent"), cA = document.getElementById("cntAbsent"), cT = document.getElementById("cntTotal");

      function recount() {
        var p = markForm.querySelectorAll('input[value="Present"]:checked').length;
        var a = markForm.querySelectorAll('input[value="Absent"]:checked').length;
        if (cP) cP.textContent = p; if (cA) cA.textContent = a; if (cT) cT.textContent = rows.length;
      }
      markForm.addEventListener("change", recount);
      recount();

      function setAll(value) {
        rows.forEach(function (r) {
          if (r.style.display === "none") return;     // only the rows currently visible
          var radio = r.querySelector('input[value="' + value + '"]');
          if (radio) radio.checked = true;
        });
        recount();
      }
      var allP = document.getElementById("markAllPresent"), allA = document.getElementById("markAllAbsent");
      if (allP) allP.addEventListener("click", function () { setAll("Present"); });
      if (allA) allA.addEventListener("click", function () { setAll("Absent"); });

      var search = document.getElementById("studentFilter");
      if (search) search.addEventListener("input", function () {
        var q = search.value.toLowerCase();
        rows.forEach(function (r) { r.style.display = r.textContent.toLowerCase().indexOf(q) > -1 ? "" : "none"; });
      });
    }
  });
})();
