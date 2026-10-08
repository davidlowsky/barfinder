"""Helper for adding bars: builds records and appends them to data/bars.json and data/offers.json
in the same layout as the existing file. Used when onboarding batches of flavors."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
J = lambda x: json.dumps(x, ensure_ascii=False)


def claim(value, source, note):
    return {"value": value, "source": source, "note": note}


def make_bar(*, id, brand, line, flavor, upc=None, serving_text, serving_g=None, bars_per_serving=1, inferred=False,
             servings_per_container=None, n, ingredients, contains=None, facility=None,
             organic=(False, "brand_page", "No organic claim on page. Confirm on package."),
             nongmo=(None, "none", "Not mentioned on page."),
             gf=(None, "none", "Not stated on the product page. Check the package."),
             claims_raw=(), sources, flags=(), availability=None, name_variants=()):
    nut = dict(calories=n["cal"], protein_g=n["protein"], fat_g=n["fat"], sat_fat_g=n.get("sat"), trans_fat_g=n.get("trans", 0),
               carbs_g=n["carbs"], fiber_g=n["fiber"], sugars_g=n["sugars"], added_sugars_g=n.get("added"),
               sugar_alcohol_g=n.get("sa"), sodium_mg=n["sodium"])
    if n.get("less_than"):
        nut["less_than"] = n["less_than"]
    rec = {"id": id}
    if availability:
        rec["availability"] = availability
    rec.update({"upc": upc, "brand": brand, "product_line": line, "flavor": flavor, "name_variants": list(name_variants),
                "serving": {"serving_size_text": serving_text, "serving_size_g": serving_g, "bars_per_serving": bars_per_serving,
                            "bars_per_serving_inferred": inferred, "servings_per_container": servings_per_container},
                "nutrition": nut, "ingredients_text": ingredients,
                "allergen_statement": {"contains_text": contains, "facility_text": facility},
                "claims": {"usda_organic": claim(*organic), "non_gmo_project_verified": claim(*nongmo), "labeled_gluten_free": claim(*gf)},
                "claims_raw": list(claims_raw), "sources": sources,
                "verification": {"status": "draft", "verified_by_human": False, "verified_date": None, "fields_checked": [],
                                 "notes": "Not yet human-verified."},
                "image": {"source": "none", "url": None}, "review_flags": list(flags)})
    return rec


def src(url, date, note):
    return {"type": "brand_text", "url": url, "retrieved": date, "note": note}


def fmt_bar(r):
    L = ["  {"]
    keys = [k for k in r if k not in ()]
    def line(k, v, last=False):
        return f'    "{k}": {v}{"" if last else ","}'
    out = []
    for k in keys:
        v = r[k]
        if k in ("serving", "nutrition", "allergen_statement"):
            inner = [f'      "{a}": {J(b)}' for a, b in v.items()]
            out.append(f'    "{k}": {{\n' + ",\n".join(inner) + "\n    }")
        elif k == "claims":
            inner = [f'      "{a}": {J(b).replace(chr(34)+": ", chr(34)+": ").replace("{", "{ ", 1).replace("}", " }") if False else "{ " + ", ".join(f"{J(x)}: {J(y)}" for x, y in b.items()) + " }"}' for a, b in v.items()]
            out.append('    "claims": {\n' + ",\n".join(inner) + "\n    }")
        elif k == "sources":
            inner = ["      { " + ", ".join(f"{J(x)}: {J(y)}" for x, y in s.items()) + " }" for s in v]
            out.append('    "sources": [\n' + ",\n".join(inner) + "\n    ]")
        elif k in ("verification", "image"):
            out.append(f'    "{k}": ' + "{ " + ", ".join(f"{J(x)}: {J(y)}" for x, y in v.items()) + " }")
        elif k in ("claims_raw", "review_flags"):
            if v:
                out.append(f'    "{k}": [\n' + ",\n".join(f"      {J(i)}" for i in v) + "\n    ]")
            else:
                out.append(f'    "{k}": []')
        else:
            out.append(f'    "{k}": {J(v)}')
    return "  {\n" + ",\n".join(out) + "\n  }"


def fmt_offer(o):
    return "  {\n" + ",\n".join(f'    "{k}": {J(v)}' for k, v in o.items()) + "\n  }"


def make_offer(*, id, bar_id, retailer, url, pack, list_price, date, sale=None, sub=None, in_stock=True, note=None, shipping=False):
    o = {"id": id, "bar_id": bar_id, "retailer": retailer, "url": url, "pack_bars": pack, "list_price_usd": list_price,
         "sale_price_usd": sale, "subscription_price_usd": sub, "price_date": date, "shipping_included": shipping}
    if not in_stock:
        o["in_stock"] = False
    o["note"] = note
    return o


def append(path, items, fmt):
    p = ROOT / path
    existing = json.loads(p.read_text())
    have = {e["id"] for e in existing}
    new = [i for i in items if i["id"] not in have]
    if not new:
        return 0
    text = p.read_text().rstrip()
    assert text.endswith("]")
    p.write_text(text[:-1].rstrip() + ",\n" + ",\n".join(fmt(i) for i in new) + "\n]\n")
    json.loads(p.read_text())
    return len(new)
