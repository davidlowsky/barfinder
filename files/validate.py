#!/usr/bin/env python3
"""
validate.py - validates bar and offer records, computes derived tags, runs consistency checks.

Usage:  python3 validate.py
Exit code 1 if any ERROR. Warnings and notes never fail the run.

Source data (data/*.json) holds only facts and sources. Everything derived (sweetener tags,
dairy/vegan, allergens, price per bar) is computed here and must never be hand-edited.
"""
import datetime
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).parent
KW = json.loads((ROOT / "keywords.json").read_text())
BAR_SCHEMA = json.loads((ROOT / "schema" / "bar.schema.json").read_text())
OFFER_SCHEMA = json.loads((ROOT / "schema" / "offer.schema.json").read_text())
BARS = json.loads((ROOT / "data" / "bars.json").read_text())
OFFERS = json.loads((ROOT / "data" / "offers.json").read_text())

STALE_PRICE_DAYS = 90
TOL = 0.5  # rounding tolerance in grams


# ---------- matching helpers ----------

def term_re(term):
    # whole-word match with optional plural 's'
    return re.compile(r"(?<![a-z0-9])" + re.escape(term) + r"s?(?![a-z0-9])")


AND_OR = re.compile(r"[^,()]*\band/or\b[^,()]*")


def split_ambiguous(text):
    """Return (ambiguous items, text with those items removed)."""
    items = [m.group(0).strip() for m in AND_OR.finditer(text)]
    return items, AND_OR.sub(" ", text)


def expand_and_or(item):
    """'sunflower and/or soy lecithin' -> also 'sunflower lecithin' and 'soy lecithin'."""
    out = [item]
    m = re.search(r"(\w+) and/or (\w+)\s+(\w+)\W*$", item)
    if m:
        a, b, tail = m.groups()
        out += [f"{a} {tail}", f"{b} {tail}"]
    return " ; ".join(out)


def find(terms, definite, possible_text, exceptions=()):
    d, p = definite, possible_text
    for ex in sorted(exceptions, key=len, reverse=True):
        d, p = d.replace(ex, " "), p.replace(ex, " ")
    hit_d = [t for t in terms if term_re(t).search(d)]
    hit_p = [t for t in terms if t not in hit_d and term_re(t).search(p)]
    return hit_d, hit_p


def derive(bar):
    text = bar["ingredients_text"].lower().replace("\n", " ")
    amb_items, definite = split_ambiguous(text)
    possible_text = " ; ".join(expand_and_or(i) for i in amb_items)

    def f(terms, ex=()):
        return find(terms, definite, possible_text, ex)

    art_d, art_p = f(KW["artificial_sweeteners"])
    sa_d, sa_p = f(KW["sugar_alcohols"])
    stevia_d, stevia_p = f(KW["other_sweeteners"]["stevia"])
    monk_d, monk_p = f(KW["other_sweeteners"]["monk_fruit"])
    dairy_d, dairy_p = f(KW["dairy"], KW["dairy_exceptions"])
    animal_d, animal_p = f(KW["animal_non_dairy"])
    caveats_d, caveats_p = f(KW["possible_animal"])
    gluten_d, gluten_p = f(KW["gluten_grains"])
    seed_d, seed_p = f(KW["seed_oils"])

    allergens_d, allergens_p = {}, {}
    for name, terms in KW["allergens"].items():
        d, p = f(terms)
        if d:
            allergens_d[name] = d
        if p:
            allergens_p[name] = p
    if dairy_d:
        allergens_d["milk"] = dairy_d
    elif dairy_p:
        allergens_p["milk"] = dairy_p

    def tri(definite_hits, possible_hits):
        if definite_hits:
            return False
        return None if possible_hits else True

    return {
        "ambiguous_items": amb_items,
        "artificial_sweeteners": art_d, "artificial_sweeteners_possible": art_p,
        "sugar_alcohols": sa_d, "sugar_alcohols_possible": sa_p,
        "stevia": bool(stevia_d), "monk_fruit": bool(monk_d),
        "dairy_ingredients": dairy_d, "dairy_possible": dairy_p,
        "no_dairy_ingredients": tri(dairy_d, dairy_p),
        "animal_ingredients": animal_d + dairy_d,
        "vegan_by_ingredients": tri(animal_d + dairy_d, animal_p + dairy_p),
        "vegan_caveats": caveats_d + caveats_p,
        "allergens": sorted(allergens_d),
        "allergens_possible": sorted(set(allergens_p) - set(allergens_d)),
        "gluten_ingredients": gluten_d, "gluten_possible": gluten_p,
        "seed_oils": seed_d, "seed_oils_possible": seed_p,
        "_allergen_hits": allergens_d,
    }


# ---------- checks ----------

def upc_ok(upc):
    digits = [int(c) for c in upc]
    total = sum(digits[0:11:2]) * 3 + sum(digits[1:11:2])
    return (10 - total % 10) % 10 == digits[11]


def contains_allergens(contains_text):
    """Allergen names mentioned in a printed 'Contains:' line."""
    t = contains_text.lower()
    found = set()
    for name, terms in KW["allergens"].items():
        if any(term_re(x).search(t) for x in terms):
            found.add(name)
    if any(term_re(x).search(t) for x in KW["dairy"]):
        found.add("milk")
    return found


def check_bar(bar, dv):
    errors, warnings, notes = [], [], []
    n = bar["nutrition"]
    sa = n.get("sugar_alcohol_g")
    added = n.get("added_sugars_g")

    if bar.get("upc") and not upc_ok(bar["upc"]):
        errors.append("UPC check digit is invalid")
    if bar.get("upc") is None:
        notes.append("UPC not captured")

    if added is not None and added > n["sugars_g"] + 0.05:
        errors.append(f"added sugars ({added}g) exceed total sugars ({n['sugars_g']}g)")
    if added is None:
        warnings.append("added sugars not reported; filters must treat as unknown, not zero")

    parts = n["sugars_g"] + n["fiber_g"] + (sa or 0)
    if parts > n["carbs_g"] + TOL:
        errors.append(f"sugars + fiber + sugar alcohol ({parts}g) exceed total carbs ({n['carbs_g']}g)")

    if (n.get("sat_fat_g") or 0) + (n.get("trans_fat_g") or 0) > n["fat_g"] + TOL:
        errors.append("saturated + trans fat exceed total fat")

    p, fat, c, fib = n["protein_g"], n["fat_g"], n["carbs_g"], n["fiber_g"]
    low = (4 * p + 9 * fat + 4 * max(c - fib - (sa or 0), 0)) * 0.9
    high = (4 * p + 9 * fat + 4 * c) * 1.1
    if not (low <= n["calories"] <= high):
        warnings.append(f"calories {n['calories']} outside plausible range {low:.0f}-{high:.0f} from macros")

    declared = sa is not None and sa > 0
    if declared and not dv["sugar_alcohols"]:
        warnings.append(f"panel declares {sa}g sugar alcohol but no known sugar alcohol in ingredients")
    if dv["sugar_alcohols"] and not declared:
        warnings.append(f"ingredients include {dv['sugar_alcohols']} but panel declares no sugar alcohol")

    contains = bar["allergen_statement"]["contains_text"]
    if contains:
        stated = contains_allergens(contains)
        derived = set(dv["allergens"])
        for a in sorted(stated - derived):
            warnings.append(f"'Contains' statement lists {a} but it is not derivable from ingredients")
        for a in sorted(derived - stated):
            warnings.append(f"ingredients imply {a} but it is missing from the 'Contains' statement")
    else:
        notes.append("no 'Contains' statement captured; allergens derived from ingredients only")

    gf = bar["claims"]["labeled_gluten_free"]["value"]
    if gf and dv["gluten_ingredients"]:
        errors.append(f"labeled gluten-free but ingredients include {dv['gluten_ingredients']}")
    facility = (bar["allergen_statement"]["facility_text"] or "").lower()
    if gf and "wheat" in facility:
        notes.append("labeled gluten-free while facility statement lists wheat (shown separately, not a filter)")

    for key, claim in bar["claims"].items():
        if claim["value"] is True and claim["source"] == "none":
            errors.append(f"claim {key} is true but has no source")
        if claim["source"] != "package_photo":
            notes.append(f"claim {key} not yet confirmed on the package")

    if bar["serving"]["bars_per_serving_inferred"]:
        warnings.append("serving size has no unit; one bar assumed")

    types = {s["type"] for s in bar["sources"]}
    if not types & {"label_image", "package_photo"}:
        warnings.append("nutrition not confirmed against a label image or package photo")

    if dv["ambiguous_items"]:
        notes.append(f"ambiguous 'and/or' ingredients: {dv['ambiguous_items']}")
    if dv["vegan_caveats"]:
        notes.append(f"vegan status cannot be fully determined ({dv['vegan_caveats']})")

    v = bar["verification"]
    if v["status"] == "verified" and not (v["verified_by_human"] and v["verified_date"]):
        errors.append("status 'verified' requires verified_by_human and verified_date")
    if v["status"] != "verified":
        notes.append(f"verification status: {v['status']}")

    return errors, warnings, notes


def check_offer(offer, bars_by_id, today):
    errors, warnings = [], []
    if offer["bar_id"] not in bars_by_id:
        errors.append("bar_id does not exist")
    sale = offer.get("sale_price_usd")
    if sale is not None and sale >= offer["list_price_usd"]:
        errors.append("sale price is not below list price")
    age = (today - datetime.date.fromisoformat(offer["price_date"])).days
    if age > STALE_PRICE_DAYS:
        warnings.append(f"price is {age} days old")
    return errors, warnings


# ---------- main ----------

def main():
    all_errors = 0
    today = datetime.date.today()
    bar_val = Draft202012Validator(BAR_SCHEMA)
    offer_val = Draft202012Validator(OFFER_SCHEMA)

    ids = [b["id"] for b in BARS]
    if len(ids) != len(set(ids)):
        print("ERROR: duplicate bar ids")
        all_errors += 1
    upcs = [b["upc"] for b in BARS if b.get("upc")]
    if len(upcs) != len(set(upcs)):
        print("ERROR: duplicate UPCs")
        all_errors += 1

    bars_by_id = {}
    derived_all = {}
    for bar in BARS:
        print(f"\n== {bar['id']}")
        schema_errs = sorted(bar_val.iter_errors(bar), key=lambda e: list(e.path))
        if schema_errs:
            for e in schema_errs:
                print(f"  ERROR schema: {'/'.join(map(str, e.path))}: {e.message}")
            all_errors += len(schema_errs)
            continue
        bars_by_id[bar["id"]] = bar
        dv = derive(bar)
        derived_all[bar["id"]] = dv
        errors, warnings, notes = check_bar(bar, dv)
        for m in errors:
            print(f"  ERROR   {m}")
        for m in warnings:
            print(f"  WARN    {m}")
        for m in notes:
            print(f"  note    {m}")
        all_errors += len(errors)

        print("  derived:")
        print(f"    no sugar alcohols:        {not dv['sugar_alcohols']}  {dv['sugar_alcohols'] or ''}")
        print(f"    no artificial sweeteners: {not dv['artificial_sweeteners']}  {dv['artificial_sweeteners'] or ''}")
        print(f"    stevia / monk fruit:      {dv['stevia']} / {dv['monk_fruit']}")
        print(f"    no dairy ingredients:     {dv['no_dairy_ingredients']}  {dv['dairy_ingredients'] or ''}")
        print(f"    vegan (by ingredients):   {dv['vegan_by_ingredients']}")
        print(f"    allergens (definite):     {dv['allergens']}   possible: {dv['allergens_possible']}")
        print(f"    seed oils:                {dv['seed_oils']}   possible: {dv['seed_oils_possible']}")

    print("\n== offers")
    rows = []
    for offer in OFFERS:
        schema_errs = list(offer_val.iter_errors(offer))
        for e in schema_errs:
            print(f"  ERROR schema [{offer.get('id')}]: {e.message}")
        all_errors += len(schema_errs)
        if schema_errs:
            continue
        errors, warnings = check_offer(offer, bars_by_id, today)
        for m in errors:
            print(f"  ERROR [{offer['id']}] {m}")
        for m in warnings:
            print(f"  WARN  [{offer['id']}] {m}")
        all_errors += len(errors)
        bar = bars_by_id.get(offer["bar_id"])
        if not bar:
            continue
        price = offer["sale_price_usd"] or offer["list_price_usd"]
        per_bar = price / offer["pack_bars"]
        protein_per_bar = bar["nutrition"]["protein_g"] / bar["serving"]["bars_per_serving"]
        per20 = per_bar / protein_per_bar * 20
        sub = offer.get("subscription_price_usd")
        sub_bar = f"${sub / offer['pack_bars']:.2f}" if sub else "-"
        rows.append((offer["id"], offer["pack_bars"], per_bar, per20, sub_bar))

    print(f"  {'offer':<20}{'bars':>6}{'$/bar':>9}{'$/20g protein':>16}{'sub $/bar':>11}")
    for r in rows:
        print(f"  {r[0]:<20}{r[1]:>6}{r[2]:>9.2f}{r[3]:>16.2f}{r[4]:>11}")

    print(f"\n{len(BARS)} bars, {len(OFFERS)} offers, {all_errors} error(s). keywords v{KW['version']}")
    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())
