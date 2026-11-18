"""Fetch current Colruyt promotions from promotiez.be and write data/promos.json.

Reads the public list at https://www.promotiez.be/winkels/colruyt/promoties
(allowed by its robots.txt), politely: one page at a time with a pause.
Each promotion is matched to a product in data/catalog.json when the names agree.
"""
import datetime as dt
import html
import re
import sys
import time
import urllib.request

from common import UA, euro, load, norm, save, similarity, tokens

BASE = "https://www.promotiez.be/winkels/colruyt/promoties"
MAX_PAGES = 25
PAUSE = 2.0


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "nl-BE,nl"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


CARD = re.compile(r'<a class="js-offer-link-item[^"]*"[^>]*data-offer-id="(\d+)".*?</a>', re.S)


def text(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


def parse_cards(page):
    out = []
    for m in CARD.finditer(page):
        block, oid = m.group(0), m.group(1)
        name = re.search(r'class="product__name[^"]*">(.*?)</h3>', block, re.S)
        if not name:
            continue
        badge = re.search(r'class="badge[^"]*">(.*?)</div>', block, re.S)
        days = re.search(r'class="product-date[^"]*">(.*?)</div>', block, re.S)
        img = re.search(r'<img alt="[^"]*aanbieding" src="([^"]+)"', block)
        price_block = block[block.find("product__price"):] if "product__price" in block else ""
        prices = [euro(p) for p in re.findall(r"€\s?[\d.]+,\d{2}", text(price_block))]
        out.append({
            "id": oid,
            "name": text(name.group(1)),
            "badge": text(badge.group(1)) if badge else "",
            "days": text(days.group(1)) if days else "",
            "prices": [p for p in prices if p is not None],
            "img": html.unescape(img.group(1)) if img else None,
        })
    return out


def parse_deal(badge, prices):
    """Turn the badge text + shown prices into the app's promo model.
    Shown prices are for the qualifying quantity (e.g. 4 packs for '-30% vanaf 4')."""
    b = norm(badge)
    old, new = (prices + [None, None])[:2] if len(prices) >= 2 else (None, prices[0] if prices else None)
    if old is not None and new is not None and new > old:
        old, new = new, old
    deal = {}
    if m := re.search(r"(\d+)\s*\+\s*(\d+)\s*gratis", b):
        pay, free = int(m.group(1)), int(m.group(2))
        deal = {"type": "multi", "buy": pay + free, "pay": pay}
        qty = pay + free
    elif m := re.search(r"(\d+)\s*de\s*(?:aan|tegen)\s*(\d+)", b):
        n, pct = int(m.group(1)), int(m.group(2))
        deal = {"type": "nth", "n": n, "pct": pct}
        qty = n
    elif m := re.search(r"(\d+)\s*vanaf\s*(\d+)", b):
        pct, qty = int(m.group(1)), int(m.group(2))
        deal = {"type": "percent", "pct": pct, "min": qty}
    elif m := re.fullmatch(r"(\d+)", b):  # "-25%"
        pct, qty = int(m.group(1)), 1
        deal = {"type": "percent", "pct": pct}
    else:
        qty = 1
        if old and new and new < old:
            deal = {"type": "price", "price": new}
        else:
            deal = {"type": "folder", "price": new}
    if old:
        deal["regular"] = round(old / qty, 2)
    elif deal.get("type") in ("price", "folder"):
        pass
    elif new and deal.get("type") == "percent":
        deal["regular"] = round(new / qty / (1 - deal["pct"] / 100), 2)
    deal["label"] = badge or None
    return deal


def match(name, catalog):
    best, score = None, 0.0
    tn = tokens(name)
    for it in catalog:
        s = similarity(name, it["name"])
        # brand (first word) must agree when both have one we recognise
        ti = tokens(it["name"])
        first = norm(it["name"]).split()[:1]
        # 2+ shared words, or a one-word promo that is the product's brand ("Chocomel")
        if s > score and (len(tn & ti) >= 2 or (len(tn) == 1 and first and first[0] in tn)):
            best, score = it, s
    return best["key"] if best and score >= 0.67 else None


def main():
    today = dt.date.today()
    catalog = load("catalog.json", {"items": []})["items"]
    seen, offers = set(), []
    for page in range(1, MAX_PAGES + 1):
        url = BASE if page == 1 else f"{BASE}?page={page}"
        try:
            cards = parse_cards(fetch(url))
        except Exception as e:  # network or site change
            print(f"page {page}: {e}", file=sys.stderr)
            break
        new = [c for c in cards if c["id"] not in seen]
        if not new:
            break
        for c in new:
            seen.add(c["id"])
            offers.append(c)
        time.sleep(PAUSE)

    if not offers:
        print("No promotions found; keeping existing data/promos.json", file=sys.stderr)
        return 1

    by_key = {i["key"]: i for i in catalog}
    promos, names = [], {}
    for c in offers:
        deal = parse_deal(c["badge"], c["prices"])
        d = re.search(r"(\d+)\s*dag", c["days"])
        until = (today + dt.timedelta(days=int(d.group(1)))).isoformat() if d else None
        key = match(c["name"], catalog)
        if key:
            # only a match when the pack size fits: promo unit price within range of what you pay
            ref, mine = deal.get("regular") or deal.get("price"), by_key[key].get("price")
            if ref and mine and not 0.6 <= ref / mine <= 1.6:
                key = None
        p = {"id": c["id"], "key": key or f"promo-{c['id']}", "matched": bool(key),
             "name": c["name"], "until": until, **deal}
        n = norm(c["name"])
        if not key and n in names:  # same offer listed twice: keep one
            continue
        names[n] = p
        promos.append(p)
    save("promos.json", {"updatedAt": today.isoformat(), "source": "promotiez.be", "promos": promos})
    matched = sum(p["matched"] for p in promos)
    print(f"{len(promos)} promotions, {matched} matched to your products")
    return 0


if __name__ == "__main__":
    sys.exit(main())
