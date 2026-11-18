"""Update product prices from Colruyt digital receipts.

Usage:
  python3 update_prices.py RECEIPT.txt [...]      text of receipt PDFs (one file each)
  python3 update_prices.py --csv artikelen.csv    seed from an export (ticket,datum,...,product,categorie,aantal,kg,bedrag,...)

Only shelf prices and product names are written to the repo (data/catalog.json,
data/prices.json). Receipts themselves (store, cashier, payment) are never stored.
Prices that came with a volume discount are recorded as the regular shelf price.
"""
import csv
import datetime as dt
import hashlib
import re
import sys

from common import euro, load, norm, save, slug

# ---------- receipt text parsing ----------
VOLUME = re.compile(r"Hoeveelheidsvoordeel toegekend:\s*€\s*([\d.,]+)\s*\(in prijs verrekend\)")
ITEM = re.compile(
    r"\s*(?P<name>\S.*?)\s+(?P<art>\d{2,6})\s+[ABCD]\s+"
    r"(?:(?P<kg>\d+,\d{3})\s*kg|(?P<qty>-?\d+))\s+"
    r"(?P<money>(?:-?\d+,\d{2,3}\s+){1,2}-?\d+,\d{2})(?=\s|$)")


def parse_receipt(txt):
    t = re.sub(r"\s+", " ", txt)
    date = re.search(r"(\d{2})/(\d{2})/(\d{4})\s+\d{2}:\d{2}", t)
    if not date:
        raise ValueError("no date on receipt")
    day = f"{date.group(3)}-{date.group(2)}-{date.group(1)}"
    start = re.search(r"Bedrag\s+INC EUR", t)
    end = re.search(r"Uw totale hoeveelheidsvoordeel|Totale korting met Xtra|TE BETALEN", t)
    seg = t[start.end() if start else 0: end.start() if end else len(t)]
    seg = seg.replace("GEWICHTSARTIKELEN EUR/kg", " ")
    parts = VOLUME.split(seg)  # text, amount, text, amount, ...
    lines = []
    for i in range(0, len(parts), 2):
        for m in ITEM.finditer(parts[i]):
            money = [euro(x) for x in m.group("money").split()]
            unit, amount = money[-2], money[-1]
            if m.group("kg"):
                kg = float(m.group("kg").replace(",", "."))
                lines.append({"name": m.group("name").strip(), "art": m.group("art"), "kg": kg,
                              "qty": 1, "unit": unit, "amount": amount, "volume": 0.0})
            else:
                q = int(m.group("qty"))
                if q <= 0:
                    continue  # returns / empties
                lines.append({"name": m.group("name").strip(), "art": m.group("art"), "kg": None,
                              "qty": q, "unit": unit, "amount": amount, "volume": 0.0})
        if i + 1 < len(parts) and lines:
            lines[-1]["volume"] += euro(parts[i + 1]) or 0.0
    for ln in lines:  # shelf price = paid + volume discount
        if ln["kg"]:
            ln["shelf"] = round(ln["unit"], 2)
        else:
            ln["shelf"] = round((ln["amount"] + ln["volume"]) / ln["qty"], 2)
    return day, lines


def from_csv(path):
    by_day = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        bedrag = float(r["bedrag"] or 0)
        kg = float(r["kg"]) if r.get("kg") else None
        qty = int(float(r["aantal"] or 1))
        if bedrag <= 0 or qty <= 0:
            continue
        shelf = round(bedrag / kg, 2) if kg else round(bedrag / qty, 2)
        by_day.setdefault(r["datum"], []).append({"name": r["product"], "art": None, "kg": kg, "qty": qty,
                                                  "shelf": shelf, "cat": r.get("categorie")})
    return sorted(by_day.items())


# ---------- catalog update ----------
def apply(day, lines, catalog, hist, changes):
    by_name = {norm(i["name"]): i for i in catalog}
    by_art = {i["art"]: i for i in catalog if i.get("art")}
    for ln in lines:
        it = (ln.get("art") and by_art.get(ln["art"])) or by_name.get(norm(ln["name"]))
        perkg = bool(ln["kg"])
        if not it:
            key = slug(ln["name"])
            while any(i["key"] == key for i in catalog):
                key += "-2"
            it = {"key": key, "name": ln["name"], "cat": ln.get("cat") or "Overige"}
            catalog.append(it)
            by_name[norm(ln["name"])] = it
        if not it.get("cat") and ln.get("cat"):
            it["cat"] = ln["cat"]
        if ln.get("art"):
            it["art"] = ln["art"]
            by_art[ln["art"]] = it
        if perkg:
            it["kgPrice"] = ln["shelf"]
            w = it.get("avgKg")
            it["avgKg"] = round(ln["kg"] if not w else (w * 3 + ln["kg"]) / 4, 3)
            price = ln["shelf"]
        else:
            price = ln["shelf"]
        h = hist.setdefault(it["key"], [])
        last = h[-1] if h else None
        if last and day < last[0]:
            continue  # older than what we know
        if last and day == last[0] and abs(last[1] - price) >= 0.01:
            # same day seen again (e.g. receipt corrects a CSV line): replace, don't add a change
            last[1] = price
            for c in changes:
                if c["key"] == it["key"] and c["date"] == day:
                    c["to"] = price
            changes[:] = [c for c in changes if abs(c["from"] - c["to"]) >= 0.01]
        elif not last or abs(last[1] - price) >= max(0.015, last[1] * 0.005):  # ignore rounding noise
            if last:
                changes.append({"key": it["key"], "name": it["name"], "from": last[1], "to": price,
                                "date": day, "perKg": perkg})
            h.append([day, price])
        it["price"] = round(price * it["avgKg"], 2) if perkg else price
        it["priced"] = day
        it.pop("src", None)


def main(argv):
    catalog_doc = load("catalog.json", {"items": []})
    catalog = catalog_doc["items"]
    prices = load("prices.json", {"history": {}, "changes": [], "seen": []})
    hist, seen = prices["history"], set(prices.get("seen", []))
    changes = prices.get("changes", [])
    before = {(c["key"], c["date"]) for c in changes}
    batches = []
    if argv[:1] == ["--csv"]:
        batches = from_csv(argv[1])
    else:
        for p in argv:
            txt = open(p, encoding="utf-8").read()
            h = hashlib.sha1(re.sub(r"\s+", " ", txt).encode()).hexdigest()[:16]
            if h in seen:
                continue
            seen.add(h)
            batches.append(parse_receipt(txt))
        batches.sort()
    for day, lines in batches:
        apply(day, lines, catalog, hist, changes)
    if batches:
        catalog_doc["pricedAt"] = max(catalog_doc.get("pricedAt") or "", batches[-1][0])
    catalog.sort(key=lambda i: (i.get("cat") or "", i["name"].lower()))
    # keep the last 90 days of changes for the app
    cutoff = (dt.date.today() - dt.timedelta(days=90)).isoformat()
    allchg = [c for c in changes if c["date"] >= cutoff]
    prices.update({"history": hist, "changes": allchg, "seen": sorted(seen)})
    save("catalog.json", catalog_doc)
    save("prices.json", prices)
    n = sum(len(l) for _, l in batches)
    print(f"{len(batches)} receipts, {n} lines, {len(catalog)} products")
    for c in [c for c in changes if (c["key"], c["date"]) not in before]:
        unit = "/kg" if c["perKg"] else ""
        arrow = "goedkoper" if c["to"] < c["from"] else "duurder"
        print(f"  {arrow}: {c['name']}  € {c['from']:.2f}{unit} -> € {c['to']:.2f}{unit} ({c['date']})")


if __name__ == "__main__":
    main(sys.argv[1:])
