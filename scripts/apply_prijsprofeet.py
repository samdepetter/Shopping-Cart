"""Apply Colruyt shelf prices and promotions looked up on PrijsProfeet (www.prijsprofeet.be).

Input: a TSV file, one product per line:
  key <TAB> PrijsProfeet product name <TAB> size <TAB> normal price [<TAB> promo price <TAB> promo until (YYYY-MM-DD) <TAB> product url]
Lines whose name is "-" (nothing found) are skipped.

A price is only applied when the pack size matches the product in data/catalog.json, so a
different pack of the same brand never overwrites your price. Price changes are recorded in
data/prices.json like receipt prices; promotions are added to data/promos.json (source "prijsprofeet").
PrijsProfeet's terms ask for attribution: items get "src": "PrijsProfeet" and the app links to it.
"""
import datetime as dt
import re
import sys

from common import load, norm, save

SIZE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:x\s*(\d+(?:[.,]\d+)?))?\s*(kg|gr|g|l|cl|ml|st)\b", re.I)
TO_BASE = {"kg": ("g", 1000), "gr": ("g", 1), "g": ("g", 1), "l": ("ml", 1000), "cl": ("ml", 10), "ml": ("ml", 1), "st": ("st", 1)}


def sizes_of(s):
    """'6st 480g' -> {'st': 6, 'g': 480}; '24x33cl' -> {'ml': 7920}; {} if no size."""
    out = {}
    for m in SIZE.finditer(str(s).replace("±", "")):
        a = float(m.group(1).replace(",", "."))
        b = float(m.group(2).replace(",", ".")) if m.group(2) else None
        unit, f = TO_BASE[m.group(3).lower()]
        out[unit] = round((a * b if b else a) * f, 1)
    return out


def same_size(cat_name, pp_name_and_size):
    """True/False when both have comparable sizes; None when the catalog name has no size."""
    a, b = sizes_of(cat_name), sizes_of(pp_name_and_size)
    if not a:
        return None
    common = set(a) & set(b)
    if not common:
        return False
    return all(abs(a[u] - b[u]) <= 0.03 * a[u] for u in common)


def main(path):
    today = dt.date.today().isoformat()
    doc = load("catalog.json", {"items": []})
    by_key = {i["key"]: i for i in doc["items"]}
    prices = load("prices.json", {"history": {}, "changes": [], "seen": []})
    hist, changes = prices["history"], prices["changes"]
    promos_doc = load("promos.json", {"promos": []})
    promos = [p for p in promos_doc["promos"] if p.get("source") != "prijsprofeet"]
    applied, skipped, new_changes = 0, [], []

    for line in open(path, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if len(f) < 4 or f[1] == "-" or f[0] not in by_key:
            continue
        key, name, size, price = f[0], f[1], f[2], float(f[3])
        it = by_key[key]
        ok = same_size(it["name"], f"{name} {size}")
        if not ok:  # other pack, or a loose product without size: don't guess
            skipped.append((it["name"], name, size)); continue
        per_kg = None
        if it.get("kgPrice"):  # weighed product: keep the price per kg
            g = sizes_of(size).get("g")
            if not g:
                skipped.append((it["name"], name, size)); continue
            per_kg = round(price / (g / 1000), 2)

        value = per_kg if per_kg is not None else price
        h = hist.setdefault(key, [])
        last = h[-1] if h else None
        if not last or abs(last[1] - value) >= max(0.015, last[1] * 0.005):
            if last and last[0] != today:
                c = {"key": key, "name": it["name"], "from": last[1], "to": value, "date": today, "perKg": per_kg is not None}
                changes.append(c); new_changes.append(c)
            if last and last[0] == today:
                last[1] = value
            else:
                h.append([today, value])
        if per_kg is not None:
            it["kgPrice"] = per_kg
            it["price"] = round(per_kg * it.get("avgKg", 1), 2)
        else:
            it["price"] = price
        it["priced"] = today
        it["src"] = "PrijsProfeet"
        it["ppName"] = f"{name} ({size})"
        applied += 1

        if len(f) >= 7 and f[4]:
            promo = float(f[4])
            if promo < price:
                promos.append({"id": f"pp-{key}", "key": key, "matched": True, "name": it["name"], "until": f[5] or None,
                               "type": "price", "price": promo, "regular": price, "label": None,
                               "source": "prijsprofeet", "url": f[6]})

    doc["pricedAt"] = today
    promos_doc["promos"] = promos
    prices["changes"] = changes
    save("catalog.json", doc)
    save("prices.json", prices)
    save("promos.json", promos_doc)
    print(f"{applied} prices applied from PrijsProfeet, {len(skipped)} skipped (other pack size)")
    for a, b, s in skipped:
        print(f"  skipped: {a}  <>  {b} ({s})")
    for c in new_changes:
        u = "/kg" if c["perKg"] else ""
        print(f"  {'goedkoper' if c['to'] < c['from'] else 'duurder'}: {c['name']}  € {c['from']:.2f}{u} -> € {c['to']:.2f}{u}")


if __name__ == "__main__":
    main(sys.argv[1])
