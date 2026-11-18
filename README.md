# Shopping-Cart

Boodschappen — shopping list for Colruyt Collect&Go.

Live: https://samdepetter.github.io/Shopping-Cart/

- **Lijst** — your list grouped by category; tap an item to tick it off while shopping.
- **Zoeken** — search the product list and add items, or add any item of your own.
- **Aanbod** — price changes on your products (cheaper / more expensive, last 30 days) and all current Colruyt promotions, the ones on products you buy first.
- **Gerechten** — 36 dishes with ingredients, amounts and step-by-step instructions; a cooking mode shows one step at a time and keeps the screen on.

When a product on your list has a multi-buy deal, the list tells you how many to take and the price per unit.

## Files

- `index.html` — the app (no build step)
- `data/catalog.json` — products and prices (from your Colruyt e-receipts)
- `data/prices.json` — price history per product and recent price changes
- `data/promos.json` — current promotions (see below)
- `data/recipes.json` — recipes
- `scripts/update_promos.py` — reads current Colruyt promotions from promotiez.be
- `scripts/update_prices.py` — reads prices from receipt text; only product names and shelf prices are stored

## Daily update

A scheduled Claude task runs every evening: it runs `update_promos.py`, reads new Colruyt e-receipts
from Hotmail, runs `update_prices.py` on them, commits the data and sends a notification with price changes
and promotions on products you buy. Colruyt's own website blocks automated visits, so prices come from receipts
(only products you buy) and promotions from the public folder listing on promotiez.be.
- `manifest.webmanifest`, `icons/`, `sw.js` — full screen from the home screen, works offline

Your list is saved on the device (browser storage), not in the repo.

## Promotions format

```json
{
  "updatedAt": "2026-11-18",
  "promos": [
    {"key": "jupiler-blik", "name": "JUPILER pils blik 50cl", "cat": "Dranken", "regular": 1.05,
     "type": "multi", "buy": 3, "pay": 2, "until": "2026-11-30"}
  ]
}
```

`key` matches a product in `catalog.json`; `name`, `cat` and `regular` are only needed for a product that isn't in it.

| type      | fields         | example                      |
|-----------|----------------|------------------------------|
| `multi`   | `buy`, `pay`   | 3 halen, 2 betalen           |
| `nth`     | `n`, `pct`     | 2de aan -50%                 |
| `volume`  | `min`, `price` | €0,79/st. vanaf 6 stuks      |
| `percent` | `pct`, `min`?  | -25%                         |
| `price`   | `price`        | tijdelijk €1,99              |
| `folder`  | `price`        | folder price, no discount known |

Expired promotions (`until` in the past) are hidden automatically.
