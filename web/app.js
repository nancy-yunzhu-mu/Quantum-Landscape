/* npm Supply-Chain Concentration — client-side rendering, search and sort. */

const RISK_ORDER = { Low: 0, Medium: 1, High: 2 };
const RISK_CLASS = { Low: "rag-low", Medium: "rag-med", High: "rag-high" };

let ALL = [];
let sortKey = "deps";
let sortDir = "desc"; // 'asc' | 'desc'

function fmtBytes(n) {
  if (!n && n !== 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v >= 100 || i === 0 ? 0 : v >= 10 ? 1 : 2)} ${units[i]}`;
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function fmtUpdated(iso) {
  if (!iso) return "—";
  return String(iso).replace("T", " ").replace(/\.\d+.*$/, "").replace("+00:00", "") + " UTC";
}

function sortRecords(rows) {
  const dir = sortDir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    let av = a[sortKey];
    let bv = b[sortKey];
    if (sortKey === "risk") {
      av = RISK_ORDER[av];
      bv = RISK_ORDER[bv];
    }
    if (typeof av === "string") return av.localeCompare(bv) * dir;
    return (av - bv) * dir;
  });
}

function render() {
  const q = document.getElementById("searchInput").value.trim().toLowerCase();
  let rows = ALL;
  if (q) {
    rows = rows.filter(
      (r) =>
        r.package.toLowerCase().includes(q) ||
        r.heaviest_dep.toLowerCase().includes(q)
    );
  }
  rows = sortRecords(rows);

  const tbody = document.getElementById("tbody");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="10" class="empty">No packages match "${esc(q)}".</td></tr>`;
  } else {
    tbody.innerHTML = rows
      .map(
        (r) => `
      <tr>
        <td class="col-name">${esc(r.package)}</td>
        <td class="mono">${esc(r.version)}</td>
        <td class="num mono">${r.deps.toLocaleString()}</td>
        <td class="num mono">${r.largest_pct.toFixed(1)}%</td>
        <td class="num mono">${r.top3_pct.toFixed(1)}%</td>
        <td class="num mono">${r.hhi.toFixed(4)}</td>
        <td><span class="rag ${RISK_CLASS[r.risk]}">${r.risk}</span></td>
        <td><span class="dep-name">${esc(r.heaviest_dep)}</span></td>
        <td class="num mono">${fmtBytes(r.install_bytes)}</td>
        <td><a class="link" href="${esc(r.npm_url)}" target="_blank" rel="noopener">npm <span class="ext">&#8599;</span></a></td>
      </tr>`
      )
      .join("");
  }

  document.getElementById("count").textContent =
    `Showing ${rows.length} of ${ALL.length} packages`;

  document.querySelectorAll("th.sortable").forEach((th) => {
    th.classList.remove("sort-asc", "sort-desc");
    if (th.dataset.key === sortKey) {
      th.classList.add(sortDir === "asc" ? "sort-asc" : "sort-desc");
    }
  });
}

function applyData(data) {
  ALL = data.records || [];
  document.getElementById("statPackages").textContent =
    data.summary.packages_tracked.toLocaleString();
  document.getElementById("statHigh").textContent = data.summary.high_risk_count;
  document.getElementById("statHhi").textContent = data.summary.median_hhi.toFixed(3);
  document.getElementById("updated").textContent = fmtUpdated(data.generated_at);
  render();
}

async function loadData() {
  const res = await fetch("../data.json?_=" + Date.now());
  if (!res.ok) throw new Error("data.json not found — run fetch_data.py first");
  applyData(await res.json());
}

function wireUp() {
  document.getElementById("searchInput").addEventListener("input", render);

  document.querySelectorAll("th.sortable").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (sortKey === key) {
        sortDir = sortDir === "asc" ? "desc" : "asc";
      } else {
        sortKey = key;
        // numbers and risk default to high-first; names default to A-Z
        sortDir = key === "package" || key === "version" ? "asc" : "desc";
      }
      render();
    });
  });

  const btn = document.getElementById("refreshBtn");
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = "Refreshing…";
    try {
      const res = await fetch("/api/refresh", { method: "POST" });
      if (res.ok) {
        await loadData();
      } else {
        // Static hosting without the refresh endpoint: just reload the snapshot.
        await loadData();
      }
    } catch (e) {
      try { await loadData(); } catch (_) {}
    } finally {
      btn.textContent = original;
      btn.disabled = false;
    }
  });
}

wireUp();
loadData().catch((err) => {
  document.getElementById("tbody").innerHTML =
    `<tr><td colspan="10" class="empty">${esc(err.message)}</td></tr>`;
});
