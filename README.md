# npm Supply-Chain Concentration

> Turn a package's dependency tree into its real install footprint — ranked and comparable.

A live dashboard that pulls the latest release of each npm package from the public
[npm registry](https://registry.npmjs.org) and converts its raw dependency list into a
fast, searchable, comparable view of each package's **diversification** and heaviest
exposures.

It is a portfolio-concentration analysis, applied to software supply chains instead of
funds. Each package's direct runtime dependencies are treated as a portfolio; every
dependency is weighted by its own install footprint; and the dashboard ranks packages by
the same concentration statistics an equity analyst runs on a fund's holdings.

![dashboard preview](docs/preview.png)

## The metrics

For a package `P`, let its direct runtime dependencies be weighted by their **unpacked
install size** (bytes of each dependency's latest release, `w_i`), with shares
`s_i = w_i / Σ w`:

| Column         | Meaning                                                             |
| -------------- | ------------------------------------------------------------------- |
| **Deps**       | number of direct runtime dependencies with a measurable size        |
| **Largest %**  | `max(s_i)` — the single heaviest dependency's share of the footprint |
| **Top 3 %**    | combined share of the three heaviest dependencies                   |
| **HHI**        | `Σ s_i²` — Herfindahl-Hirschman Index (0–1); higher = more concentrated |
| **Risk**       | RAG tag from the HHI                                                 |
| **Heaviest Dep** | the dependency that dominates the install footprint               |
| **Install Size** | total unpacked size of all direct dependencies                    |

The **risk tag** buckets the HHI with the U.S. DOJ / FTC merger-guideline thresholds
(1500 / 2500 points, i.e. `0.15` and `0.25` on the normalized 0–1 scale):

- 🟢 **Low** — HHI < 0.15 (footprint spread across many dependencies)
- 🟡 **Medium** — 0.15 ≤ HHI < 0.25
- 🔴 **High** — HHI ≥ 0.25 (one or two dependencies dominate the install)

A high score is the software analogue of single-name concentration risk: most of what you
install — and most of your supply-chain surface — rides on one package.

## Run it

No dependencies beyond Python 3.8+ (standard library only).

```bash
# 1. Pull live data from the npm registry and build data.json
python3 fetch_data.py

# 2. Serve the dashboard (the Refresh button re-runs step 1)
python3 server.py
# → open http://localhost:8000
```

`data.json` is committed so the dashboard renders immediately; re-run `fetch_data.py`
(or click **Refresh**) to pull the latest numbers.

## View it in the browser (no terminal)

Two ways to see the dashboard without running anything locally:

**GitHub Pages — a hosted URL.** A workflow (`.github/workflows/pages.yml`) publishes
the dashboard as a static site. To turn it on once: repo **Settings → Pages → Build and
deployment → Source: GitHub Actions**. After the next push it goes live at
`https://<owner>.github.io/<repo>/`. Pages usually deploys from the default branch, so you
may need to merge this branch to `main` first. On Pages the table, search and sorting all
work; the **Refresh** button just reloads the committed snapshot (there's no Python server
to re-fetch), and the daily refresh workflow keeps that snapshot current.

**GitHub Codespaces — run it in the browser, works on this branch now.** On the repo page:
**Code ▸ Codespaces ▸ Create codespace on this branch**, then in the Codespace terminal run
`python3 server.py` and click the forwarded port. This runs the real server, so the
**Refresh** button re-fetches live.

## Configure which packages are tracked

Edit [`packages.txt`](packages.txt) — one npm package name per line. Any package with
fewer than three sized runtime dependencies is skipped automatically (you can't talk about
concentration across two holdings).

## How it works

```
packages.txt ──▶ fetch_data.py ──▶ data.json ──▶ web/ (index.html + app.js)
                     │
                     └─ GET registry.npmjs.org/<pkg>/latest      (the "fund")
                        GET registry.npmjs.org/<dep>/latest ...  (its "holdings", by size)
```

- `fetch_data.py` — fetches manifests concurrently, caches shared dependencies, computes
  the concentration statistics, and writes `data.json`.
- `web/` — a static dark-themed dashboard: client-side search, sortable columns, RAG badges.
- `server.py` — a stdlib static server plus a `POST /api/refresh` endpoint for the button.

## Notes & caveats

- Weighting uses each dependency's own latest unpacked size (a shallow, direct-dependency
  view), not a fully resolved transitive tree — it's a fast, comparable proxy, not an
  exact `node_modules` measurement.
- `unpackedSize` is populated by npm for modern releases; the rare dependency without one
  is dropped from that package's weights.
- The registry is a public, unauthenticated, read-only API. Be a good citizen about how
  often you refresh.
