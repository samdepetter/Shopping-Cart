# Shopping-Cart

Colruyt grocery spending and shopping-list projects, exported from Claude artifacts.

## `colruyt-uitgaven/` — spending dashboard
- `page.html` — dashboard page (runs inside the claude.ai Dashboard artifact type; uses its `dash` + `d3` runtime)
- `meta.json`, `datasets/*.json` — dashboard title and dataset definitions
- `data/tickets.csv` — one row per receipt (date, store, total)
- `data/artikelen.csv` — one row per receipt line (product, category, amount, discount, net)

Live artifact: https://claude.ai/artifact/2ZtJXaA5tqUTmzCeTNR884

## `boodschappen-gerechten/` — groceries & recipes
- `index.html` — standalone page
- `data/catalog.json`, `data/history.json`, `data/recipes.json` — its shared data store

Live artifact: https://claude.ai/artifact/5nrQT9ae9Xsu4wYwCDdgPx

Snapshot taken 2026-11-17.
