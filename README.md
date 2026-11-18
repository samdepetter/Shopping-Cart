# Shopping-Cart

Boodschappen — shopping list for Colruyt Collect&Go.

Live: https://samdepetter.github.io/Shopping-Cart/

- **Lijst** — your list grouped by category; tap an item to tick it off while shopping.
- **Zoeken** — search the product list and add items, or add any item of your own.
- **Promoties** — current deals, the ones on products you buy shown first.
- **Gerechten** — recipes; add all ingredients to your list in one tap.

When a product on your list has a multi-buy deal, the list tells you how many to take and the price per unit.

## Files

- `index.html` — the app (no build step)
- `data/catalog.json` — products and prices
- `data/promos.json` — current promotions (see below)
- `data/recipes.json` — recipes
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

Expired promotions (`until` in the past) are hidden automatically.
