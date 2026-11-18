"""Shared helpers for the data update scripts."""
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UA = "Mozilla/5.0 (compatible; personal-shopping-list/1.0; +https://samdepetter.github.io/Shopping-Cart/)"

STOP = {"de", "het", "een", "en", "met", "van", "in", "op", "voor", "alle", "of", "x", "st", "stuks",
        "g", "kg", "ml", "cl", "l", "gr", "pak", "fles", "flessen", "blik", "blikken", "doos", "bak",
        "verpakking", "verpakkingen", "per", "ca", "dagvers", "vers"}


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def slug(s):
    return norm(s).replace(" ", "-")


def tokens(s):
    """Meaningful words of a product name (no sizes, no filler)."""
    out = set()
    for t in norm(s).split():
        if t in STOP or len(t) < 3 or re.fullmatch(r"\d+([a-z]{1,2})?", t) or re.fullmatch(r"\d+x\d+[a-z]*", t):
            continue
        out.add(t)
    return out


def similarity(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def load(name, default):
    p = DATA / name
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save(name, obj):
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def euro(s):
    """'€ 1.234,56' / '1,49' -> 1234.56 / 1.49"""
    s = re.sub(r"[^\d,.]", "", str(s)).replace(".", "").replace(",", ".")
    return float(s) if s else None
