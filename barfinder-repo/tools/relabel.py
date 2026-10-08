"""Apply a newer full-label image to an existing bar record and report what changed."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from entry import fmt_bar, ROOT

D = "2026-10-06"
LOG = Path("/tmp/relabel_log.json")


def relabel(bar_id, *, serving_g=62, serving_text=None, n=None, contains=None, facility=None, flags_add=(), flags_drop=(), source_note=""):
    p = ROOT / "data" / "bars.json"
    s = p.read_text()
    data = json.loads(s)
    rec = next(b for b in data if b["id"] == bar_id)
    changes = []

    def setv(container, key, new, label):
        old = container.get(key)
        if old != new:
            changes.append((label, old, new))
            container[key] = new

    sv = rec["serving"]
    setv(sv, "serving_size_text", serving_text or f"1 bar ({serving_g}g)", "serving size")
    setv(sv, "serving_size_g", serving_g, "serving grams")
    sv["bars_per_serving_inferred"] = False
    for k, label in (("cal", "calories"), ("protein", "protein"), ("fat", "fat"), ("sat", "sat fat"), ("carbs", "carbs"),
                     ("fiber", "fiber"), ("sugars", "sugars"), ("added", "added sugar"), ("sa", "sugar alcohol"), ("sodium", "sodium")):
        if n and k in n:
            key = {"cal": "calories", "protein": "protein_g", "fat": "fat_g", "sat": "sat_fat_g", "carbs": "carbs_g", "fiber": "fiber_g",
                   "sugars": "sugars_g", "added": "added_sugars_g", "sa": "sugar_alcohol_g", "sodium": "sodium_mg"}[k]
            setv(rec["nutrition"], key, n[k], label)
    if n is not None:
        lt = set(rec["nutrition"].get("less_than") or [])
        lt -= {k for k in ("fiber_g",) if n.get("fiber") is not None and n.get("fiber_lt") is not True}
        if n.get("fiber_lt"):
            lt.add("fiber_g")
        if lt:
            rec["nutrition"]["less_than"] = sorted(lt)
        else:
            rec["nutrition"].pop("less_than", None)
    if contains is not None:
        setv(rec["allergen_statement"], "contains_text", contains, "contains line")
    if facility is not None:
        setv(rec["allergen_statement"], "facility_text", facility, "may-contain line")

    # sources: replace the older label image entry with the new one
    rec["sources"] = [x for x in rec["sources"] if x["type"] != "label_image"]
    rec["sources"].append({"type": "label_image", "url": None, "retrieved": D,
                           "note": "Full nutrition label image supplied by the owner (the newer of the two versions on David's page). " + source_note})
    keep = [f for f in rec["review_flags"] if not any(f.startswith(d) for d in flags_drop)]
    rec["review_flags"] = keep + list(flags_add)

    i = s.index(f'"id": "{bar_id}"')
    a = s.rfind("  {\n", 0, i)
    b = s.index("\n  }", i) + len("\n  }")
    s = s[:a] + fmt_bar(rec) + s[b:]
    p.write_text(s); json.loads(s)
    log = json.loads(LOG.read_text()) if LOG.exists() else {}
    log[bar_id] = [[l, o, nw] for l, o, nw in changes]
    LOG.write_text(json.dumps(log))
    return changes
