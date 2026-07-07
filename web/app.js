/* Quantum Technology Companies — client-side rendering, search, filter and sort. */

const TIER_ORDER = { Emerging: 0, Major: 1, Mega: 2 };
const TIER_CLASS = { Mega: "rag-mega", Major: "rag-major", Emerging: "rag-emerging" };

let ALL = [];
let sortKey = "raised_musd";
let sortDir = "desc"; // 'asc' | 'desc'
let domainFilter = "all";

function fmtMoney(musd) {
  if (musd === null || musd === undefined || musd === "") return "—";
  if (musd >= 1000) return "$" + (musd / 1000).toFixed(musd % 1000 === 0 ? 0 : 1) + "B";
  return "$" + musd + "M";
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
    if (sortKey === "tier") {
      av = TIER_ORDER[av];
      bv = TIER_ORDER[bv];
    }
    // push blanks to the bottom regardless of direction
    const an = av === null || av === undefined || av === "";
    const bn = bv === null || bv === undefined || bv === "";
    if (an && bn) return 0;
    if (an) return 1;
    if (bn) return -1;
    if (typeof av === "string") return av.localeCompare(bv) * dir;
    return (av - bv) * dir;
  });
}

function render() {
  const q = document.getElementById("searchInput").value.trim().toLowerCase();
  let rows = ALL;
  if (domainFilter !== "all") {
    rows = rows.filter((r) => r.domain === domainFilter);
  }
  if (q) {
    rows = rows.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        r.focus.toLowerCase().includes(q) ||
        r.hq.toLowerCase().includes(q)
    );
  }
  rows = sortRecords(rows);

  const tbody = document.getElementById("tbody");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="10" class="empty">No companies match your filters.</td></tr>`;
  } else {
    tbody.innerHTML = rows
      .map(
        (r) => `
      <tr>
        <td class="col-name">${esc(r.name)}</td>
        <td><span class="domain-pill domain-${esc(r.domain)}">${esc(r.domain)}</span></td>
        <td class="col-focus">${esc(r.focus)}</td>
        <td>${esc(r.stage)}</td>
        <td class="num mono">${r.founded ?? "—"}</td>
        <td>${esc(r.country)}</td>
        <td class="num mono">${fmtMoney(r.raised_musd)}</td>
        <td class="num mono">${fmtMoney(r.valuation_musd)}</td>
        <td><span class="rag ${TIER_CLASS[r.tier]}">${r.tier}</span></td>
        <td><a class="link" href="${esc(r.url)}" target="_blank" rel="noopener">site <span class="ext">&#8599;</span></a></td>
      </tr>`
      )
      .join("");
  }

  const suffix = domainFilter === "all" ? "" : ` · ${domainFilter}`;
  document.getElementById("count").textContent =
    `Showing ${rows.length} of ${ALL.length} companies${suffix}`;

  document.querySelectorAll("th.sortable").forEach((th) => {
    th.classList.remove("sort-asc", "sort-desc");
    if (th.dataset.key === sortKey) {
      th.classList.add(sortDir === "asc" ? "sort-asc" : "sort-desc");
    }
  });
}

function applyData(data) {
  ALL = data.records || [];
  document.getElementById("statCompanies").textContent =
    data.summary.companies_tracked.toLocaleString();
  document.getElementById("statFunding").textContent =
    "$" + data.summary.total_raised_busd + "B";
  document.getElementById("statPublic").textContent = data.summary.publicly_listed;
  document.getElementById("updated").textContent = fmtUpdated(data.generated_at);

  const counts = {};
  ALL.forEach((r) => (counts[r.domain] = (counts[r.domain] || 0) + 1));
  document.querySelectorAll(".tag-count").forEach((el) => {
    el.textContent = counts[el.dataset.count] ?? 0;
  });

  render();
}

function setDomainFilter(next) {
  domainFilter = next;
  document.querySelectorAll("#filters button").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.domain === domainFilter);
  });
  render();
}

async function loadData() {
  // "data.json" works when hosted next to the page (GitHub Pages);
  // "../data.json" works under the local dev server, where the page is in /web.
  const candidates = ["data.json", "../data.json"];
  let lastErr;
  for (const path of candidates) {
    try {
      const res = await fetch(path + "?_=" + Date.now());
      if (res.ok) {
        applyData(await res.json());
        return;
      }
      lastErr = new Error("HTTP " + res.status);
    } catch (err) {
      lastErr = err;
    }
  }
  throw new Error("data.json not found — run build_data.py first (" + lastErr + ")");
}

function wireUp() {
  document.getElementById("searchInput").addEventListener("input", render);

  document.querySelectorAll("#filters button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next =
        btn.dataset.domain === domainFilter && domainFilter !== "all"
          ? "all"
          : btn.dataset.domain;
      setDomainFilter(next);
    });
  });

  document.querySelectorAll("th.sortable").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (sortKey === key) {
        sortDir = sortDir === "asc" ? "desc" : "asc";
      } else {
        sortKey = key;
        // text columns default A→Z; numbers and tier default high-first
        sortDir = ["name", "domain", "stage", "country"].includes(key) ? "asc" : "desc";
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
      await fetch("/api/refresh", { method: "POST" });
    } catch (_) {
      /* static host without the endpoint — just reload the snapshot */
    }
    try {
      await loadData();
    } catch (_) {}
    btn.textContent = original;
    btn.disabled = false;
  });
}

wireUp();
loadData().catch((err) => {
  document.getElementById("tbody").innerHTML =
    `<tr><td colspan="10" class="empty">${esc(err.message)}</td></tr>`;
});
