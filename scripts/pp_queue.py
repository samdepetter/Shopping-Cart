"""Print which products the daily task should look up on PrijsProfeet: key <TAB> search term.

Usage: python3 pp_queue.py [N]   (default 60) — products priced longest ago first, among those
PrijsProfeet already knows plus recipe ingredients and products bought in the last 6 months.
Look each one up with PrijsProfeet fetch("schap:<search term>") and write the Colruyt line to a TSV
for apply_prijsprofeet.py.
"""
import datetime as dt
import re
import sys

from common import load


def term(name):
    n = re.sub(r"[±~]?\d+([.,]\d+)?\s*(x\s*\d+([.,]\d+)?)?\s*(kg|g|gr|ml|cl|l|st|stuks)\b", "", name, flags=re.I)
    n = re.sub(r"\d+([.,]\d+)?%", "", n)
    n = re.sub(r"[^\w\s&+'-]", " ", n)
    return " ".join(n.lower().split()[:5])


def main(n):
    items = load("catalog.json", {"items": []})["items"]
    recipes = load("recipes.json", {"recipes": []})["recipes"]
    in_recipe = {g["item"] for r in recipes for g in r.get("ing", [])}
    since = (dt.date.today() - dt.timedelta(days=183)).isoformat()
    todo = [i for i in items if not i["key"].startswith("promo-")
            and (i.get("src") == "PrijsProfeet" or i["key"] in in_recipe or (i.get("priced") or "") >= since)]
    todo.sort(key=lambda i: i.get("priced") or "")
    for i in todo[:n]:
        print(f"{i['key']}\t{term(i['name'])}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
