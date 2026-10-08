#!/usr/bin/env python3
"""
build_site.py - builds the static website into ./site from data/*.json.

Usage:
    python3 build_site.py                   build with verified bars only
    python3 build_site.py --include-drafts  also include bars not yet verified (for previews)

Then open site/index.html in a browser. To publish, upload the whole ./site folder to any static host.

All filter logic runs in the browser (site_src/app.js). Every bar also gets its own plain HTML page
(site/bars/<id>.html) so search engines can read it. Derived tags come from validate.py, so the
website and the validator can never disagree.
"""
import argparse
import datetime
import html
import json
import re
import shutil
import sys
from pathlib import Path

import validate as v

ROOT = Path(__file__).parent
SRC = ROOT / "site_src"
OUT = ROOT / "site"

# ---- configuration (change these) ----
SITE_NAME = "Nutrition Bar Finder"        # working title; brand and domain are still undecided
SITE_URL = ""                   # e.g. "https://example.com" (needed for the sitemap and canonical links)
PRIVATE = False                 # set by --private: deploy build for a private test link (all bars, noindex, banner)
AFFILIATE_LINKS = False         # set True once affiliate links are used; changes the disclosure text

GENERIC_LINES = {"Protein Bars", "Bars", "Original Bars"}   # lines that are not part of the display name


def add_group_names(bars, records):
    """Brand name shown on the site: the product line is included when it is a named line (CLIF Builders, David Gold)."""
    lines = {}
    for bar in bars:
        lines.setdefault(bar["brand"], set()).add(bar["product_line"])
    for bar, rec in zip(bars, records):
        split = len(lines[bar["brand"]]) > 1 or bar["product_line"] not in GENERIC_LINES
        rec["gname"] = f"{bar['brand']} {bar['product_line']}" if split else bar["brand"]


ALLERGEN_NAMES = {"peanut": "peanuts", "tree_nuts": "tree nuts", "soy": "soy", "milk": "milk",
                  "egg": "egg", "wheat": "wheat", "sesame": "sesame", "fish": "fish"}


# ---------- small helpers ----------

def esc(s):
    return html.escape(str(s), quote=True)


def num(x):
    """16.0 -> '16', 2.5 -> '2.5'."""
    if x is None:
        return "?"
    return str(int(x)) if float(x).is_integer() else str(round(x, 2)).rstrip("0").rstrip(".")


def money(x):
    return f"${x:,.2f}"


def nice_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def initials(brand):
    words = re.findall(r"[A-Za-z0-9]+", brand)
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return (words[0][:2] if words else "?").upper()


def hue(brand):
    return sum(ord(c) * 31 for c in brand.lower()) % 360


def join_list(items):
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


# ---------- data preparation ----------

def make_record(bar, offers):
    n = bar["nutrition"]
    k = bar["serving"]["bars_per_serving"]

    def per(x):
        return None if x is None else round(x / k, 2)

    dv = v.derive(bar)
    protein = per(n["protein_g"])

    offer_rows = []
    for o in offers:
        eff = o["sale_price_usd"] or o["list_price_usd"]
        per_bar = eff / o["pack_bars"]
        sub = o.get("subscription_price_usd")
        offer_rows.append({
            "id": o["id"], "retailer": o["retailer"], "url": o["url"], "packBars": o["pack_bars"],
            "price": eff, "list": o["list_price_usd"], "sub": sub,
            "perBar": round(per_bar, 4),
            "per20": round(per_bar / protein * 20, 4) if protein else None,
            "subPerBar": round(sub / o["pack_bars"], 4) if sub else None,
            "inStock": o.get("in_stock", True), "date": o["price_date"], "note": o.get("note"),
        })
    offer_rows.sort(key=lambda r: (not r["inStock"], r["perBar"]))
    best = offer_rows[0] if offer_rows else None

    ct = bar["allergen_statement"]["contains_text"]
    stated = v.contains_allergens(ct) if ct else set()
    # The printed "Contains" line always counts: it settles "and/or" ingredients and also catches allergens
    # the ingredient list does not show (for example soy from a source that is not listed).
    allergens = set(dv["allergens"]) | (set(dv["allergens_possible"]) & stated) | stated
    possible = set(dv["allergens_possible"]) - allergens
    names = [ALLERGEN_NAMES.get(a, a) for a in sorted(allergens)]
    names += [ALLERGEN_NAMES.get(a, a) + " (possible)" for a in sorted(possible)]
    every = allergens | possible

    sweet = [t for t in dv["artificial_sweeteners"] + dv["artificial_sweeteners_possible"]]
    sweet += [t for t in dv["sugar_alcohols"] + dv["sugar_alcohols_possible"]]
    if dv["stevia"]:
        sweet.append("stevia")
    if dv["monk_fruit"]:
        sweet.append("monk fruit")
    if dv["allulose"]:
        sweet.append("allulose")

    claims = bar["claims"]
    return {
        "id": bar["id"], "brand": bar["brand"], "flavor": bar["flavor"], "line": bar["product_line"],
        "avail": bar.get("availability", "regular"),
        "draft": bar["verification"]["status"] != "verified",
        "mono": initials(bar["brand"]), "hue": hue(bar["brand"]),
        "protein": protein, "cal": per(n["calories"]), "fat": per(n["fat_g"]), "carbs": per(n["carbs_g"]),
        "fiber": per(n["fiber_g"]), "sugars": per(n["sugars_g"]), "added": per(n["added_sugars_g"]),
        "sa": per(n["sugar_alcohol_g"]), "sodium": per(n["sodium_mg"]),
        "claims": {"organic": claims["usda_organic"]["value"],
                   "nongmo": claims["non_gmo_project_verified"]["value"],
                   "gf": claims["labeled_gluten_free"]["value"]},
        "noDairy": dv["no_dairy_ingredients"], "vegan": dv["vegan_by_ingredients"],
        "has": {
            "artificial": bool(dv["artificial_sweeteners"] or dv["artificial_sweeteners_possible"]),
            "sugar_alcohol": bool(dv["sugar_alcohols"] or dv["sugar_alcohols_possible"]),
            "stevia": dv["stevia"], "monk": dv["monk_fruit"], "allulose": dv["allulose"],
            "peanut": "peanut" in every, "tree_nuts": "tree_nuts" in every, "soy": "soy" in every,
            "egg": "egg" in every, "seed_oil": bool(dv["seed_oils"] or dv["seed_oils_possible"]),
        },
        "sweet": [s.capitalize() for s in sweet],
        "allergenNames": names,
        "offers": offer_rows, "best": best,
        "perBar": best["perBar"] if best else None, "per20": best["per20"] if best else None,
    }, dv


# ---------- ingredient highlighting ----------

HIGHLIGHT_CATS = [
    ("sweet-artificial", "Artificial sweetener", v.KW["artificial_sweeteners"]),
    ("sweet-alcohol", "Sugar alcohol", v.KW["sugar_alcohols"]),
    ("sweet-other", "Stevia, monk fruit or allulose",
     v.KW["other_sweeteners"]["stevia"] + v.KW["other_sweeteners"]["monk_fruit"] + v.KW["other_sweeteners"]["allulose"]),
    ("dairy", "Dairy ingredient", v.KW["dairy"]),
    ("animal", "Other animal ingredient", v.KW["animal_non_dairy"]),
    ("allergen", "Common allergen", [t for terms in v.KW["allergens"].values() for t in terms]),
    ("oil", "Seed oil", v.KW["seed_oils"]),
]


def highlight(text):
    low = text.lower()
    skip = []
    for phrase in v.KW["dairy_exceptions"]:
        skip += [(m.start(), m.end(), "dairy") for m in re.finditer(re.escape(phrase), low)]
    for phrase in v.KW.get("ingredient_negations", []):
        skip += [(m.start(), m.end(), "*") for m in re.finditer(re.escape(phrase), low)]
    found = []
    for cls, label, terms in HIGHLIGHT_CATS:
        for term in terms:
            for m in v.term_re(term).finditer(low):
                s, e = m.start(), m.end()
                if any(a <= s and e <= b and (c == "*" or c == cls) for a, b, c in skip):
                    continue
                found.append((s, e, cls, label))
    found.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    out, pos, used = [], 0, {}
    for s, e, cls, label in found:
        if s < pos:
            continue
        out.append(esc(text[pos:s]))
        out.append(f'<mark class="hl hl-{cls}" title="{esc(label)}">{esc(text[s:e])}</mark>')
        used[cls] = label
        pos = e
    out.append(esc(text[pos:]))
    return "".join(out), used


# ---------- page pieces ----------

def head(title, desc, css, canonical=None):
    canon = f'<link rel="canonical" href="{esc(canonical)}">' if canonical else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{'<meta name="robots" content="noindex, nofollow">' if PRIVATE else ''}
{canon}
<link rel="stylesheet" href="{css}">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
"""


def top(home):
    banner = ('<div class="testbanner"><div class="wrap"><b>Test version.</b> Some bars are still being checked against the brands\u2019 own pages '
              'and are tagged \u201cNot yet checked.\u201d If you have an allergy, read the package. Do not rely on this site.</div></div>\n') if PRIVATE else ""
    return f"""<header class="top"><div class="wrap">
<a class="wordmark" href="{home}">{esc(SITE_NAME)}</a>
<span class="top-note">US products</span>
</div></header>
{banner}"""


def footer(updated):
    if AFFILIATE_LINKS:
        aff = "<p><b>Affiliate disclosure.</b> Some links on this site are affiliate links. We may earn a commission if you buy through them, at no extra cost to you.</p>"
    else:
        aff = "<p><b>Links.</b> Shop links go to each brand's own store. We don't earn money from them yet. If that changes, this page will say so.</p>"
    return f"""<footer class="foot-site"><div class="wrap">
<p><b>Check the package.</b> {"Bars tagged 'Not yet checked' have not been checked by a person yet. The rest were checked against the brand's own label page" if PRIVATE else "Every bar here was checked by a person against the brand's own label page"}{f' (most recently {esc(nice_date(updated))})' if updated else ''}. Brands change recipes, and pages can be out of date. Always read the label before you buy, and especially if you have an allergy or a medical diet. This site does not give medical or allergy advice.</p>
<p>"Labeled" means the brand's page says so. "No dairy ingredients" and "Vegan by ingredients" are worked out from the ingredient list only. Prices are approximate and change often.</p>
{aff}
</div></footer>
</body>
</html>
"""


STEPS = [
    ("minProtein", "Protein", "at least", [10, 15, 20, 25], lambda x: f"{x}g+"),
    ("maxCal", "Calories", "at most", [150, 200, 250, 300], lambda x: f"{x}"),
    ("maxAdded", "Added sugar", "at most", [0, 1, 3, 5, 10], lambda x: f"{x}g"),
    ("maxBarPrice", "Price per bar", "at most", [2, 2.5, 3], lambda x: money(x)),
    ("maxPer20", "Price per 20g of protein", "at most", [2.5, 3.5, 5], lambda x: money(x)),
]
MORE = [
    ("minFiber", "Fiber", "at least", [3, 5, 10], lambda x: f"{x}g+"),
    ("maxCarbs", "Carbs", "at most", [10, 20, 30], lambda x: f"{x}g"),
    ("maxFat", "Fat", "at most", [5, 10], lambda x: f"{x}g"),
    ("maxSodium", "Sodium", "at most", [200, 300, 500], lambda x: f"{x}mg"),
]
EXCLUDE_GROUPS = [
    ("Sweeteners", [
        ("artificial", "Artificial sweeteners", "Sucralose, aspartame, acesulfame potassium, saccharin, neotame, advantame."),
        ("sugar_alcohol", "Sugar alcohols", "Erythritol, maltitol, xylitol, sorbitol and similar. Vegetable glycerin is not counted."),
        ("stevia", "Stevia", ""),
        ("monk", "Monk fruit", ""),
        ("allulose", "Allulose", "A rare sugar that labels don't count as sugar."),
    ]),
    ("Allergens", [
        ("peanut", "Peanuts", ""),
        ("tree_nuts", "Tree nuts", "Almonds, cashews, walnuts and similar."),
        ("soy", "Soy", ""),
        ("egg", "Egg", ""),
    ]),
    ("Other", [
        ("seed_oil", "Seed oils", "Sunflower, soybean, canola and similar."),
    ]),
]
MUST_HAVE = [
    ("organic", "USDA Organic", "The brand's page shows the seal."),
    ("nongmo", "Non-GMO Project Verified", "The brand's page shows the verified seal, not just a non-GMO claim."),
    ("gf", "Labeled gluten-free", "The bar's own claim. Not a guarantee for celiac disease."),
    ("nodairy", "No dairy ingredients", "From the ingredient list. Some of these still say \u201cmay contain milk.\u201d"),
    ("vegan", "Vegan by ingredients", "No animal ingredients listed. \u201cNatural flavor\u201d can't be traced."),
]
SORT_OPTIONS = [
    ("protein", "Most protein"), ("per20", "Lowest price per 20g protein"), ("perBar", "Lowest price per bar"),
    ("cal", "Fewest calories"), ("added", "Least added sugar"), ("ratio", "Most protein per calorie"),
    ("fiber", "Most fiber"),
]


def steps_row(key, label, qual, values, fmt):
    btns = "".join(
        f'<button type="button" class="step" data-key="{key}" data-value="{x}" aria-pressed="false">{esc(fmt(x))}</button>'
        for x in values)
    return (f'<fieldset class="row"><legend>{esc(label)} <small>{esc(qual)}</small></legend>'
            f'<div class="steps">{btns}</div></fieldset>')


def checkbox(attr, key, label, hint):
    h = f"<em>{esc(hint)}</em>" if hint else ""
    return (f'<label class="check"><input type="checkbox" data-{attr}="{key}">'
            f'<span>{esc(label)}{h}</span></label>')


def filter_panel(review=False):
    main = "".join(steps_row(*s) for s in STEPS)
    more = "".join(steps_row(*s) for s in MORE)
    ex = ""
    for title, items in EXCLUDE_GROUPS:
        ex += f'<div class="sub-title">{esc(title)}</div>' + "".join(checkbox("ex", k, l, h) for k, l, h in items)
    items = MUST_HAVE + ([("draft", "Not yet checked", "Review build only: bars nobody has checked against the brand page yet.")] if review else [])
    must = "".join(checkbox("must", k, l, h) for k, l, h in items)
    return f"""<aside id="filters" class="panel" aria-label="Filters">
<div class="label-head"><h2 class="label-title">Your bar</h2><button type="button" class="sheet-close" id="close-sheet">Close</button></div>
<p class="label-sub">Set a limit on any line. A bar has to meet every limit to show up.</p>
<div class="heavy"></div>
{main}
<details class="more"><summary>More amounts</summary>{more}</details>
<div class="heavy"></div>
<h3 class="group-title">Leave out</h3>
{ex}
<div class="heavy"></div>
<h3 class="group-title">Must have</h3>
{must}
<p class="fine">Bars that don't state a seal on the brand's page stay hidden when you ask for it. Check the package to be sure.</p>
<div class="panel-foot"><button type="button" class="clear" id="clear">Clear all</button><button type="button" class="show" id="show">Show bars</button></div>
</aside>"""


def render_index(records, updated, preview=False, review=False):
    data = {"bars": records, "updated": updated}
    if review:
        data["review"] = True
    if preview:
        data["preview"] = True
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    sort_opts = "".join(f'<option value="{k}">{esc(t)}</option>' for k, t in SORT_OPTIONS)
    browse = "".join(f'<li><a href="bars/{esc(r["id"])}.html">{esc(r["gname"])} {esc(r["flavor"])}</a></li>'
                     for r in sorted(records, key=lambda r: (r["gname"].lower(), r["flavor"])))
    title = f"Find the right nutrition bar for you | {SITE_NAME}"
    desc = ("Compare nutrition bars by protein, calories, carbs, sweeteners, ingredients and price. "
            + ("Test version: some bars are still being checked against the brand's own label page." if PRIVATE else "Every bar is checked against the brand's own label page."))
    canon = f"{SITE_URL}/" if SITE_URL else None
    return (head(title, desc, "style.css", canon) + top("./") + f"""<main id="main">
<section class="hero"><div class="wrap">
<h1>Find the right nutrition bar for you</h1>
<p>Set limits for protein, added sugar, sweeteners and ingredients. {len(records)} bars so far, each checked against the brand's own label page.</p>
<button type="button" class="cta" id="cta">Find your bar</button>
<div class="presets-wrap"><div class="presets-title">Or start with</div>
<ul class="presets">
<li><button type="button" class="chip" data-preset="protein" aria-pressed="false">High protein <small>20g+</small></button></li>
<li><button type="button" class="chip" data-preset="sugar" aria-pressed="false">Low added sugar <small>5g or less</small></button></li>
<li><button type="button" class="chip" data-preset="cal" aria-pressed="false">Lower calorie <small>200 or less</small></button></li>
<li><button type="button" class="chip" data-preset="organic" aria-pressed="false">USDA Organic</button></li>
<li><button type="button" class="chip" data-preset="artificial" aria-pressed="false">No artificial sweeteners</button></li>
<li><button type="button" class="chip" data-preset="sa" aria-pressed="false">No sugar alcohols</button></li>
</ul></div>
</div></section>
<div class="wrap layout">
{filter_panel(review)}
<section id="results" aria-label="Results">
<div class="results-head"><h2 class="count" id="count"></h2>
<div class="tools"><label class="sort">Sort by <select id="sort">{sort_opts}</select></label>
<div class="seg" role="group" aria-label="Layout"><button type="button" data-layout="brands" aria-pressed="false">Brands</button><button type="button" data-layout="rows" aria-pressed="false">Rows</button><button type="button" data-layout="cards" aria-pressed="false">Cards</button></div>
<label class="grp"><input type="checkbox" id="group"> Group by brand</label></div></div>
<div id="active" class="active"></div>
<ul id="list" class="list"></ul>
<noscript><p class="empty">Filtering needs JavaScript. You can still open any bar from the list below.</p></noscript>
<div class="browse"><h2>All bars</h2><ul>{browse}</ul></div>
</section>
</div>
</main>
<div id="live" class="sr" aria-live="polite"></div>
<div class="scrim" id="scrim"></div>
<div class="dock"><button type="button" id="open-sheet">Filters <span id="filter-badge"></span></button><div class="dock-count" id="dock-count" aria-hidden="true"></div></div>
<script id="bar-data" type="application/json">{blob}</script>
<script src="app.js"></script>
""" + footer(updated))


# ---------- bar page ----------

def nf_row(label, value, cls="", hl=False):
    return f'<div class="r {cls}{" hl" if hl else ""}"><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>'


def render_bar(bar, rec, dv, updated, known_brands=None):
    n = bar["nutrition"]
    k = bar["serving"]["bars_per_serving"]
    lt = set(n.get("less_than") or [])

    def val(field, unit, scale=True):
        x = n.get(field)
        if x is None:
            return None
        x = x / k if scale else x
        return ("<" if field in lt else "") + num(x) + unit

    rows = [nf_row("Total Fat", val("fat_g", "g"), "top")]
    if n.get("sat_fat_g") is not None:
        rows.append(nf_row("Saturated Fat", val("sat_fat_g", "g"), "sub"))
    if n.get("trans_fat_g") is not None:
        rows.append(nf_row("Trans Fat", val("trans_fat_g", "g"), "sub"))
    rows.append(nf_row("Sodium", val("sodium_mg", "mg"), "top"))
    rows.append(nf_row("Total Carbohydrate", val("carbs_g", "g"), "top"))
    rows.append(nf_row("Dietary Fiber", val("fiber_g", "g"), "sub"))
    rows.append(nf_row("Total Sugars", val("sugars_g", "g"), "sub"))
    if n.get("added_sugars_g") is not None:
        rows.append(nf_row("Includes Added Sugars", val("added_sugars_g", "g"), "sub2"))
    if n.get("sugar_alcohol_g") is not None:
        rows.append(nf_row("Sugar Alcohol", val("sugar_alcohol_g", "g"), "sub"))
    rows.append(nf_row("Protein", val("protein_g", "g"), "top"))

    s = bar["serving"]
    serving = esc(s["serving_size_text"])
    if s["bars_per_serving_inferred"]:
        serving = "1 bar <span class='small'>(the page doesn't print a unit; one bar assumed)</span>"
    nf = f"""<div class="nf">
<h2>Nutrition Facts</h2>
<div class="srv"><b>Serving size</b> {serving}</div>
<div class="cal"><span>Calories</span><b>{num(n['calories'] / k)}</b></div>
<dl>{''.join(rows)}</dl>
<p class="foot">Values per bar, as printed on the brand's label page. Daily Values are not shown.</p>
</div>"""

    ing_html, used = highlight(bar["ingredients_text"])
    order = [c for c, _, _ in HIGHLIGHT_CATS]
    legend = "".join(f'<span class="hl hl-{c}">{esc(used[c])}</span>' for c in order if c in used)
    legend = f'<div class="legend" aria-label="Highlight key">{legend}</div>' if legend else ""

    # what the rules found
    found = []
    if dv["artificial_sweeteners"] or dv["artificial_sweeteners_possible"]:
        found.append("artificial: " + join_list(dv["artificial_sweeteners"] + dv["artificial_sweeteners_possible"]))
    if dv["sugar_alcohols"] or dv["sugar_alcohols_possible"]:
        found.append("sugar alcohol: " + join_list(dv["sugar_alcohols"] + dv["sugar_alcohols_possible"]))
    others = [x for x, flag in (("stevia", dv["stevia"]), ("monk fruit", dv["monk_fruit"]), ("allulose", dv["allulose"])) if flag]
    if others:
        found.append("other: " + join_list(others))
    sweet_line = "; ".join(found) if found else "None of the artificial sweeteners, sugar alcohols, stevia, monk fruit or allulose we look for"
    dairy_line = join_list(dv["dairy_ingredients"]) if dv["dairy_ingredients"] else "None listed"
    animal = [a for a in dv["animal_ingredients"] if a not in dv["dairy_ingredients"]]
    animal_line = join_list(animal) if animal else "None listed"
    ct = bar["allergen_statement"]["contains_text"]
    stated = v.contains_allergens(ct) if ct else set()
    names = [ALLERGEN_NAMES.get(a, a) for a in dv["allergens"]]
    for a in sorted(stated - set(dv["allergens"]) - set(dv["allergens_possible"])):
        names.append(ALLERGEN_NAMES.get(a, a) + " (named on the \u201cContains\u201d line, not in the ingredient list)")
    for a in dv["allergens_possible"]:
        if a in stated:
            names.append(ALLERGEN_NAMES.get(a, a))
        else:
            names.append(ALLERGEN_NAMES.get(a, a) + " (possible: the ingredient list says \u201cand/or\u201d)")
    allergen_line = join_list(names) if names else "None of the allergens we look for"
    oil_line = join_list(dv["seed_oils"] + [o + " (possible)" for o in dv["seed_oils_possible"]]) or "None listed"

    a = bar["allergen_statement"]
    printed = ""
    if a["contains_text"] or a["facility_text"]:
        printed = "<dl class='kv'>"
        if a["contains_text"]:
            printed += f"<dt>Contains</dt><dd>{esc(a['contains_text'])}</dd>"
        if a["facility_text"]:
            printed += f"<dt>Also on the page</dt><dd>{esc(a['facility_text'])}</dd>"
        printed += "</dl>"
    else:
        printed = "<p class='small'>The brand's page doesn't show a &ldquo;Contains&rdquo; or &ldquo;may contain&rdquo; statement. Check the package.</p>"

    def claim_row(label, c):
        if c is True:
            t = '<span class="yes">Yes, per the brand\'s page</span>'
        elif c is False:
            t = '<span class="no">No claim found on the brand\'s page</span>'
        else:
            t = '<span class="unk">Not confirmed</span>'
        return f"<tr><th>{esc(label)}</th><td>{t}</td></tr>"

    def derived_row(label, value, no_text):
        if value is True:
            t = '<span class="yes">Yes, from the ingredient list</span>'
        elif value is False:
            t = f'<span class="no">No: {esc(no_text)}</span>'
        else:
            t = '<span class="unk">Can\'t tell: an ingredient is listed as &ldquo;and/or&rdquo;</span>'
        return f"<tr><th>{esc(label)}</th><td>{t}</td></tr>"

    animal_all = dv["animal_ingredients"]
    cl = bar["claims"]
    claims = ("<table class='claims'>" +
              claim_row("USDA Organic seal", cl["usda_organic"]["value"]) +
              claim_row("Non-GMO Project Verified", cl["non_gmo_project_verified"]["value"]) +
              claim_row("Labeled gluten-free", cl["labeled_gluten_free"]["value"]) +
              derived_row("No dairy ingredients", dv["no_dairy_ingredients"], "lists " + join_list(dv["dairy_ingredients"])) +
              derived_row("Vegan by ingredients", dv["vegan_by_ingredients"], "lists " + join_list(animal_all)) + "</table>")

    offers = ""
    for o in rec["offers"]:
        stock = "" if o["inStock"] else "<br><span class='small unk'>Out of stock when checked</span>"
        sub = f"<br><span class='small'>Subscribe: {money(o['sub'])} ({money(o['subPerBar'])} per bar)</span>" if o["sub"] else ""
        offers += (f"<tr><td data-label='Shop'>{esc(o['retailer'])}</td><td data-label='Pack'>{o['packBars']} bars</td>"
                   f"<td class='n' data-label='Price'><span>{money(o['price'])}{stock}{sub}</span></td>"
                   f"<td class='n' data-label='Per bar'>{money(o['perBar'])}</td>"
                   f"<td class='n' data-label='Per 20g protein'>{money(o['per20'])}</td>"
                   f"<td class='act'><a class='buy' href='{esc(o['url'])}' target='_blank' rel='noopener'>View shop</a></td></tr>")
    dates = sorted({o["date"] for o in rec["offers"]})
    price_date = nice_date(dates[-1]) if dates else ""
    offers_html = (f"<table class='offers'><thead><tr><th>Shop</th><th>Pack</th><th>Price</th><th>Per bar</th>"
                   f"<th>Per 20g protein</th><th></th></tr></thead><tbody>{offers}</tbody></table>"
                   f"<p class='small' style='margin-top:10px'>Prices as of {esc(price_date)}, before shipping and tax. They change often, so check the shop.</p>"
                   ) if offers else "<p>No price found yet.</p>"

    ver = bar["verification"]
    seasonal = ""
    if bar.get("availability", "regular") != "regular":
        kind = "seasonal flavor" if bar["availability"] == "seasonal" else "limited-run flavor"
        seasonal = f'<p class="small" style="margin-top:8px"><b>This is a {kind}.</b> It may not be on shelves all year, and the price below may be out of date.</p>'
    if ver["status"] == "verified":
        stamp = f'<span class="stamp">Checked against the brand\'s label page on {esc(nice_date(ver["verified_date"]))}</span>'
    else:
        stamp = '<span class="stamp draft">Not yet checked by a person</span>'

    title = f"{rec['gname']} {bar['flavor']}: {num(rec['protein'])}g protein, {num(rec['cal'])} calories | {SITE_NAME}"
    added_txt = f"{num(rec['added'])}g added sugar" if rec["added"] is not None else "added sugar not listed"
    desc = (f"{rec['gname']} {bar['flavor']} nutrition bar: {num(rec['protein'])}g protein, {num(rec['cal'])} calories, "
            f"{added_txt}. Ingredients, sweeteners and prices" + (" from the brand's label page (some bars not yet checked)." if PRIVATE else ", checked against the brand's label page."))
    canon = f"{SITE_URL}/bars/{bar['id']}.html" if SITE_URL else None
    src = next((s["url"] for s in bar["sources"] if s.get("url") and s["type"] == "brand_text"), None)
    brand_link = f'<p class="small" style="margin-top:10px"><a href="{esc(src)}" target="_blank" rel="noopener">Open the brand\'s page</a></p>' if src else ""

    reviewer = ""
    if known_brands is not None and bar["verification"]["status"] != "verified":
        import verify_sheet as vs
        _, warns, _ = v.check_bar(bar, dv)
        links = "".join(f"<li><a href='{esc(x['url'])}' target='_blank' rel='noopener'>{esc(x['type'].replace('_', ' '))}: {esc(x['url'])}</a>"
                        f"{(' <span class=small>(' + esc(x['note']) + ')</span>') if x.get('note') else ''}</li>"
                        for x in bar["sources"] if x.get("url"))
        look = "".join(f"<li>{esc(r)}</li>" for r in vs.risk_reasons(bar, known_brands, warns))
        notes = "".join(f"<li><b>{esc(k.replace('_', ' '))}</b>: {esc(c['source'].replace('_', ' '))}. {esc(c.get('note') or '')}</li>"
                        for k, c in bar["claims"].items())
        reviewer = f"""<section class="sect"><h2>For the reviewer</h2><div class="body">
<p><b>Compare this page with the brand's page,</b> then tell me what matches and what is wrong.</p>
<ul class="rev">{links or '<li>No page link saved</li>'}</ul>
<p style="margin-top:10px"><b>Look at first</b></p><ul class="rev">{look}</ul>
<p style="margin-top:10px"><b>How each seal was decided</b></p><ul class="rev">{notes}</ul>
<p class="small" style="margin-top:10px">UPC stored: {esc(bar.get('upc') or 'none')}.</p></div></section>"""
    return (head(title, desc, "../style.css", canon) + top("../") + f"""<main id="main" class="wrap">
<p class="crumb"><a href="../index.html">&larr; All bars</a></p>
<div class="bar-head"><span class="mono" style="background:hsl({rec['hue']},48%,34%)" aria-hidden="true">{esc(rec['mono'])}</span>
<div><div class="brand">{esc(bar['brand'])} &middot; {esc(bar['product_line'])}</div><h1>{esc(bar['flavor'])}</h1>{stamp}{seasonal}</div></div>
<div class="bar-grid">
<div>{nf}</div>
<div>
{reviewer}
<section class="sect"><h2>Ingredients</h2><div class="body"><p class="ingredients">{ing_html}</p>{legend}
<dl class="kv" style="margin-top:14px">
<dt>Sweeteners</dt><dd>{esc(sweet_line)}</dd>
<dt>Dairy</dt><dd>{esc(dairy_line)}</dd>
<dt>Other animal</dt><dd>{esc(animal_line)}</dd>
<dt>Allergens</dt><dd>{esc(allergen_line)}</dd>
<dt>Seed oils</dt><dd>{esc(oil_line)}</dd>
</dl>{brand_link}</div></section>
<section class="sect"><h2>What the brand's page says about allergens</h2><div class="body">{printed}</div></section>
<section class="sect"><h2>Seals and claims</h2><div class="body">{claims}
<p class="small" style="margin-top:10px">&ldquo;Not confirmed&rdquo; means the brand's page doesn't say. Confirm any seal on the package.</p></div></section>
<section class="sect"><h2>Where to buy</h2><div class="body">{offers_html}</div></section>
</div></div>
<div class="notice" style="margin-bottom:40px"><b>Verify on the package.</b> Recipes change and pages go out of date. If you have an allergy, rely on the package, not this page.</div>
</main>
""" + footer(updated))



# ---------- single-file preview (for sharing one link; not for the real site) ----------

PREVIEW_ROUTER = """
(function () {
  var home = document.getElementById('home'), view = document.getElementById('bar-view');
  function route() {
    var m = /(?:^|&)view=([a-z0-9-]+)/.exec(location.hash.replace(/^#/, ''));
    var tpl = m && document.getElementById('view-' + m[1]);
    if (tpl) {
      view.innerHTML = tpl.innerHTML;
      home.hidden = true; view.hidden = false;
      var h = view.querySelector('h1'); if (h) document.title = h.textContent + ' | Bar Finder (preview)';
      window.scrollTo(0, 0);
    } else {
      view.hidden = true; home.hidden = false;
      document.title = 'Bar Finder (preview)';
    }
  }
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('[data-back]');
    if (!a) return;
    e.preventDefault();
    if (history.length > 1) history.back(); else location.hash = '';
  });
  window.addEventListener('hashchange', route);
  route();
})();
"""


def render_preview(bars, records, derived, updated, review=False):
    idx = render_index(records, updated, preview=True, review=review)
    known = {b['brand'] for b in v.BARS if b['verification']['status'] == 'verified'} if review else None
    css = (SRC / "style.css").read_text()
    js = (SRC / "app.js").read_text()
    safe = ":root{box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}html{scroll-padding-top:env(safe-area-inset-top,0px)}"
    idx = idx.replace('<link rel="stylesheet" href="style.css">', f"<style>{css}\n{safe}</style>")
    idx = idx.replace('content="width=device-width, initial-scale=1"', 'content="width=device-width, initial-scale=1, viewport-fit=cover"')
    idx = idx.replace("<meta charset=\"utf-8\">", "<meta charset=\"utf-8\">\n<meta name=\"robots\" content=\"noindex\">")
    idx = idx.replace("<title>Find the right nutrition bar for you | " + SITE_NAME + "</title>", "<title>" + SITE_NAME + (" (review build)" if review else " (preview)") + "</title>")
    idx = idx.replace('<span class="top-note">US products</span>', f'<span class="top-note">{"Review build" if review else "Preview"} &middot; {len(records)} bars</span>')
    if review:
        idx = idx.replace("Every bar here was checked by a person against the brand's own label page", "Bars marked 'Not yet checked' have not been checked by a person yet. The rest were checked against the brand's own label page")
        idx = idx.replace("each checked against the brand's own label page.", "some still waiting to be checked against the brand's own label page.")
    # wrap the filter page so it can be hidden while a bar is open
    idx = idx.replace('<main id="main">', '<div id="home">\n<main id="main">', 1)
    marker = '<script id="bar-data"'
    i = idx.index(marker)
    idx = idx[:i] + '</div>\n<div id="bar-view" hidden></div>\n' + idx[i:]
    # bar pages become templates inside the same file
    tpls = ""
    for bar, rec in zip(bars, records):
        page = render_bar(bar, rec, derived[bar["id"]], updated, known)
        m = re.search(r'<main id="main" class="wrap">.*?</main>', page, re.S)
        body = m.group(0).replace('<a href="../index.html">', '<a href="#" data-back>')
        tpls += f'<template id="view-{bar["id"]}">{body}</template>\n'
    idx = re.sub(r'href="bars/([a-z0-9-]+)\.html"', r'href="#view=\1"', idx)  # the plain "All bars" list
    idx = idx.replace('<script src="app.js"></script>', f"{tpls}<script>{js}</script>\n<script>{PREVIEW_ROUTER}</script>")
    return idx


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-drafts", action="store_true", help="include bars that are not yet verified")
    ap.add_argument("--preview", action="store_true", help="also write preview.html, one self-contained file for sharing a link")
    ap.add_argument("--private", action="store_true", help="deploy build for a private test link: all bars, noindex, test banner, written to public/")
    args = ap.parse_args()
    global PRIVATE
    if args.private:
        PRIVATE = True
        args.include_drafts = True

    bars = [b for b in v.BARS if args.include_drafts or b["verification"]["status"] == "verified"]
    if not bars:
        sys.exit("No verified bars to build. Use --include-drafts for a preview.")
    by_bar = {}
    for o in v.OFFERS:
        by_bar.setdefault(o["bar_id"], []).append(o)

    records, derived = [], {}
    for b in bars:
        rec, dv = make_record(b, by_bar.get(b["id"], []))
        records.append(rec)
        derived[b["id"]] = dv
    add_group_names(bars, records)
    dates = [b["verification"]["verified_date"] for b in bars if b["verification"]["verified_date"]]
    updated = max(dates) if dates else ""

    out = ROOT / ("public" if args.private else "site_review" if args.include_drafts else "site")  # review builds never touch the real site folder
    if out.exists():
        shutil.rmtree(out)
    (out / "bars").mkdir(parents=True)
    shutil.copy(SRC / "style.css", out / "style.css")
    shutil.copy(SRC / "app.js", out / "app.js")
    idx_html = render_index(records, updated)
    if args.private:
        idx_html = idx_html.replace("each checked against the brand's own label page.", "some still waiting to be checked against the brand's own label page.")
    (out / "index.html").write_text(idx_html, encoding="utf-8")
    for b, rec in zip(bars, records):
        (out / "bars" / f"{b['id']}.html").write_text(render_bar(b, rec, derived[b["id"]], updated), encoding="utf-8")
    if args.private:
        (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
        (out / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow\n  Referrer-Policy: no-referrer\n  X-Content-Type-Options: nosniff\n")
    else:
        (out / "robots.txt").write_text("User-agent: *\nAllow: /\n" + (f"Sitemap: {SITE_URL}/sitemap.xml\n" if SITE_URL else ""))
    if SITE_URL and not args.private:
        urls = [f"{SITE_URL}/"] + [f"{SITE_URL}/bars/{b['id']}.html" for b in bars]
        (out / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
            "".join(f"<url><loc>{esc(u)}</loc></url>\n" for u in urls) + "</urlset>\n")
    if args.preview:
        name = "review.html" if args.include_drafts else "preview.html"
        (ROOT / name).write_text(render_preview(bars, records, derived, updated, review=args.include_drafts), encoding="utf-8")
        print(f"Wrote {ROOT / name} (single file{', includes unchecked bars' if args.include_drafts else ''})")
    print(f"Built {len(bars)} bars into {out}/ (open {out / 'index.html'})")


if __name__ == "__main__":
    main()
