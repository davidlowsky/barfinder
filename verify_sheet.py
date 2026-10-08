#!/usr/bin/env python3
"""
verify_sheet.py - writes verify/sheet.html, a page for checking draft bars against their brand pages.

Usage:
    python3 verify_sheet.py                  every bar that is not yet verified
    python3 verify_sheet.py --ids a,b,c      only these bar ids
    python3 verify_sheet.py --all            every bar (for practice or re-checks)

Open verify/sheet.html in your browser. For each bar:
  1. Open the brand page (link at the top of the bar).
  2. Compare each value on the sheet with the page. Click "Matches" or "Wrong" (and type the right value).
  3. Click "Copy results" at the bottom and paste the text into the chat.
Nothing is saved to your data files until the results are applied.
"""
import argparse
import html
import json
import datetime
from pathlib import Path

import validate as v

ROOT = Path(__file__).parent
OUT = ROOT / "verify"


def esc(s):
    return html.escape(str(s), quote=True)


def num(x):
    if x is None:
        return None
    return str(int(x)) if float(x).is_integer() else str(round(x, 2)).rstrip("0").rstrip(".")


def nutrient_rows(bar):
    n = bar["nutrition"]
    lt = set(n.get("less_than") or [])
    s = bar["serving"]

    def val(field, unit):
        x = n.get(field)
        if x is None:
            return "not on the page"
        return ("<" if field in lt else "") + num(x) + unit

    return [
        ("serving", "Serving size", s["serving_size_text"] + (" (assumed one bar)" if s["bars_per_serving_inferred"] else "")),
        ("nutrition.calories", "Calories", val("calories", "")),
        ("nutrition.protein_g", "Protein", val("protein_g", "g")),
        ("nutrition.fat_g", "Total fat", val("fat_g", "g")),
        ("nutrition.sat_fat_g", "Saturated fat", val("sat_fat_g", "g")),
        ("nutrition.trans_fat_g", "Trans fat", val("trans_fat_g", "g")),
        ("nutrition.carbs_g", "Total carbohydrate", val("carbs_g", "g")),
        ("nutrition.fiber_g", "Dietary fiber", val("fiber_g", "g")),
        ("nutrition.sugars_g", "Total sugars", val("sugars_g", "g")),
        ("nutrition.added_sugars_g", "Added sugars", val("added_sugars_g", "g")),
        ("nutrition.sugar_alcohol_g", "Sugar alcohol", val("sugar_alcohol_g", "g")),
        ("nutrition.sodium_mg", "Sodium", val("sodium_mg", "mg")),
    ]


def control(key, kind="text", options=None):
    """OK / Wrong buttons. 'Wrong' reveals a box for the right value."""
    if kind == "select":
        box = "<select class='fix'>" + "".join(f"<option>{esc(o)}</option>" for o in options) + "</select>"
    elif kind == "area":
        box = "<textarea class='fix' rows='3' placeholder='Type the correct text'></textarea>"
    else:
        box = "<input class='fix' type='text' placeholder='Correct value'>"
    return (f"<div class='ctl' data-key='{esc(key)}'><button type='button' class='ok'>Matches</button>"
            f"<button type='button' class='bad'>Wrong</button>{box}</div>")


def risk_reasons(bar, known_brands, warnings):
    out = []
    if bar["brand"] in known_brands:
        out.append("Same brand as a bar you already verified. The page layout is familiar, but flavors still differ in numbers, ingredients and claims.")
    else:
        out.append("New brand: check everything closely, including where on the page each thing is.")
    types = {s["type"] for s in bar["sources"]}
    if "label_image" in types:
        out.append("Some numbers were read from an image: compare digit by digit.")
    if "brand_text_pasted" in types:
        out.append("Some text came from a paste: make sure it matches the live page.")
    if bar["serving"]["bars_per_serving_inferred"]:
        out.append("The serving size has no unit on the page, so one bar was assumed.")
    if (bar["nutrition"].get("less_than")):
        out.append("A value is printed as '<X': confirm it.")
    for w in warnings:
        out.append("Validator: " + w)
    for f in bar.get("review_flags", []):
        out.append("Open issue: " + f)
    return out


def bar_block(bar, known_brands):
    dv = v.derive(bar)
    _, warnings, _ = v.check_bar(bar, dv)
    bid = bar["id"]
    links = "".join(
        f"<a class='open' href='{esc(s['url'])}' target='_blank' rel='noopener'>Open page ({esc(s['type'].replace('_', ' '))})</a>"
        for s in bar["sources"] if s.get("url"))
    reasons = "".join(f"<li>{esc(r)}</li>" for r in risk_reasons(bar, known_brands, warnings))

    claim_names = [("usda_organic", "USDA Organic seal"), ("non_gmo_project_verified", "Non-GMO Project Verified"),
                   ("labeled_gluten_free", "Labeled gluten-free")]
    claims = ""
    for key, label in claim_names:
        c = bar["claims"][key]
        shown = {True: "Yes", False: "No claim found", None: "Unknown"}[c["value"]]
        claims += (f"<tr><th>{label}</th><td><b>{shown}</b><div class='note'>Source: {esc(c['source'].replace('_', ' '))}. {esc(c.get('note') or '')}</div></td>"
                   f"<td>{control('claims.' + key, 'select', ['Yes', 'No claim found', 'Unknown'])}</td></tr>")

    a = bar["allergen_statement"]
    ing = (f"<tr><th>Ingredient list</th><td class='mono'>{esc(bar['ingredients_text'])}</td><td>{control('ingredients', 'area')}</td></tr>"
           f"<tr><th>&ldquo;Contains&rdquo; line</th><td>{esc(a['contains_text']) if a['contains_text'] else '<i>none captured</i>'}</td><td>{control('allergen.contains', 'text')}</td></tr>"
           f"<tr><th>&ldquo;May contain&rdquo; or facility line</th><td>{esc(a['facility_text']) if a['facility_text'] else '<i>none captured</i>'}</td><td>{control('allergen.facility', 'text')}</td></tr>")

    nums = "".join(f"<tr><th>{esc(label)}</th><td><b>{esc(value)}</b></td><td>{control(key, 'text')}</td></tr>"
                   for key, label, value in nutrient_rows(bar))

    derived = (f"Derived from the ingredients: artificial sweeteners: {', '.join(dv['artificial_sweeteners']) or 'none'}; "
               f"sugar alcohols: {', '.join(dv['sugar_alcohols']) or 'none'}; dairy: {', '.join(dv['dairy_ingredients']) or 'none'}; "
               f"allergens: {', '.join(dv['allergens']) or 'none'}.")

    return f"""<section class="bar" id="{esc(bid)}" data-bar="{esc(bid)}">
<header><div><div class="brand">{esc(bar['brand'])}</div><h2>{esc(bar['flavor'])}</h2></div>
<div class="prog"><span class="done">0</span> of <span class="total">0</span> checked</div></header>
<div class="links">{links or "<i>No page link saved</i>"}</div>
<div class="look"><b>Look at first</b><ul>{reasons}</ul></div>
<h3>1. Seals and claims <button type="button" class="all" data-group="claims">All match</button></h3>
<table class="grid" data-group="claims">{claims}</table>
<h3>2. Ingredients and allergen lines <button type="button" class="all" data-group="ing">All match</button></h3>
<table class="grid" data-group="ing">{ing}</table>
<p class="note">{esc(derived)} These come from the ingredient list, so they are right if the list is right.</p>
<h3>3. Numbers per bar <button type="button" class="all" data-group="nums">All match</button></h3>
<table class="grid" data-group="nums">{nums}</table>
<h3>4. Seen at Whole Foods?</h3>
<p class="note">Only you can answer this. Leave it as "Not checked" if you didn't look. Now: <b>{esc((bar.get('whole_foods') or {}).get('status', 'unknown').replace('_', ' '))}</b>.</p>
<p style="margin:6px 14px"><select class="wf"><option value="">Not checked</option><option value="carried">Carried at Whole Foods</option><option value="not found">Not found at Whole Foods</option></select></p>
<h3>Notes</h3>
<textarea class="notes" rows="2" placeholder="Anything odd about this bar or its page"></textarea>
</section>"""


CSS = """
:root{--ink:#000;--muted:#4a4f57;--hair:#c7ccd3;--hi:#ffe14d;--bad:#9e1b1b;--ok:#0b5d2a}
*{box-sizing:border-box}body{margin:0;background:#eceef1;color:#000;font:16px/1.45 "Helvetica Neue",Helvetica,Arial,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:16px}
h1{font-size:34px;letter-spacing:-.03em;margin:8px 0}
.intro{background:#fff;border:1px solid #000;padding:12px 14px;margin:12px 0}
.intro ol{margin:6px 0 0 20px;padding:0}
.summary{width:100%;border-collapse:collapse;background:#fff;border:1px solid #000;margin:12px 0}
.summary th,.summary td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--hair);font-size:15px}
.summary a{font-weight:800}
.bar{background:#fff;border:1px solid #000;margin:22px 0;padding:0 0 14px}
.bar header{display:flex;justify-content:space-between;align-items:flex-end;padding:12px 14px 8px;border-bottom:8px solid #000}
.brand{font-weight:700;color:var(--muted)}.bar h2{margin:0;font-size:28px;letter-spacing:-.02em}
.prog{font-weight:800}.prog.full{background:var(--hi);padding:2px 8px}
.links{padding:10px 14px;display:flex;gap:10px;flex-wrap:wrap}
.open{background:#000;color:#fff;text-decoration:none;font-weight:800;padding:8px 12px;border-radius:3px;font-size:14px}
.look{margin:4px 14px 8px;padding:10px 12px;border:2px solid #000;background:#fff8cc}
.look ul{margin:6px 0 0 18px;padding:0}
h3{margin:16px 14px 6px;font-size:18px;border-bottom:3px solid #000;padding-bottom:4px;display:flex;justify-content:space-between;align-items:center}
.all{border:1.5px solid #000;background:#fff;border-radius:3px;padding:6px 10px;font-weight:700;cursor:pointer}
.grid{width:calc(100% - 28px);margin:0 14px;border-collapse:collapse}
.grid th{width:24%;text-align:left;vertical-align:top;padding:8px 8px 8px 0;border-bottom:1px solid var(--hair)}
.grid td{padding:8px 8px 8px 0;border-bottom:1px solid var(--hair);vertical-align:top}
.grid td.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:14px}
.note{font-size:13px;color:var(--muted);margin:2px 14px}.grid .note{margin:2px 0}
.ctl{display:flex;flex-wrap:wrap;gap:6px;align-items:flex-start;min-width:200px}
.ctl button{border:1.5px solid #000;background:#fff;border-radius:3px;padding:6px 10px;font-weight:700;cursor:pointer}
.ctl.ok .ok{background:var(--ok);color:#fff;border-color:var(--ok)}
.ctl.wrong .bad{background:var(--bad);color:#fff;border-color:var(--bad)}
.fix{display:none;width:100%;padding:6px;border:1.5px solid var(--bad);font:inherit}
.ctl.wrong .fix{display:block}
.notes{width:calc(100% - 28px);margin:0 14px;padding:8px;font:inherit;border:1.5px solid #000}
.out{background:#fff;border:2px solid #000;padding:14px;margin:24px 0}
.out button{background:#000;color:#fff;border:0;border-radius:3px;padding:12px 18px;font-weight:800;font-size:16px;cursor:pointer}
.out textarea{width:100%;margin-top:10px;min-height:200px;font:13px/1.4 ui-monospace,Menlo,Consolas,monospace;padding:8px}
.status{margin-left:10px;font-weight:700}
@media(max-width:700px){.grid,.grid tbody,.grid tr,.grid th,.grid td{display:block;width:100%}.grid th{border:0;padding-bottom:0}}
"""

JS = """
(function(){
  var KEY = 'verify-' + document.body.getAttribute('data-sheet');
  var saved = {}; try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}
  function save(){ try { localStorage.setItem(KEY, JSON.stringify(collect())); } catch (e) {} }
  function $$(s, r){ return Array.prototype.slice.call((r||document).querySelectorAll(s)); }
  function collect(){
    var d = {};
    $$('.bar').forEach(function(bar){
      var id = bar.getAttribute('data-bar'), o = {c:{}, notes: bar.querySelector('.notes').value, wf: bar.querySelector('.wf').value};
      $$('.ctl', bar).forEach(function(c){
        var st = c.classList.contains('ok') ? 'ok' : c.classList.contains('wrong') ? 'wrong' : '';
        if (st) o.c[c.getAttribute('data-key')] = {s: st, v: c.querySelector('.fix').value};
      });
      d[id] = o;
    });
    return d;
  }
  function progress(bar){
    var all = $$('.ctl', bar), done = all.filter(function(c){ return c.classList.contains('ok') || c.classList.contains('wrong'); });
    var p = bar.querySelector('.prog'); p.querySelector('.done').textContent = done.length; p.querySelector('.total').textContent = all.length;
    p.classList.toggle('full', done.length === all.length);
    var row = document.querySelector('[data-sum="' + bar.getAttribute('data-bar') + '"]');
    if (row) row.textContent = done.length + ' of ' + all.length;
  }
  function setState(c, st, val){
    c.classList.remove('ok','wrong'); if (st) c.classList.add(st);
    if (val != null) c.querySelector('.fix').value = val;
  }
  $$('.ctl').forEach(function(c){
    c.querySelector('.ok').addEventListener('click', function(){ setState(c, c.classList.contains('ok') ? '' : 'ok'); progress(c.closest('.bar')); save(); });
    c.querySelector('.bad').addEventListener('click', function(){ setState(c, c.classList.contains('wrong') ? '' : 'wrong'); progress(c.closest('.bar')); save(); var f = c.querySelector('.fix'); if (c.classList.contains('wrong')) f.focus(); });
    c.querySelector('.fix').addEventListener('input', save);
  });
  $$('.all').forEach(function(b){
    b.addEventListener('click', function(){
      var t = b.closest('.bar').querySelector('table[data-group="' + b.getAttribute('data-group') + '"]');
      $$('.ctl', t).forEach(function(c){ if (!c.classList.contains('wrong')) setState(c, 'ok'); });
      progress(b.closest('.bar')); save();
    });
  });
  $$('.notes').forEach(function(n){ n.addEventListener('input', save); });
  $$('.wf').forEach(function(n){ n.addEventListener('change', save); });
  // restore
  $$('.bar').forEach(function(bar){
    var s = saved[bar.getAttribute('data-bar')];
    if (s) { bar.querySelector('.notes').value = s.notes || ''; bar.querySelector('.wf').value = s.wf || '';
      $$('.ctl', bar).forEach(function(c){ var x = s.c[c.getAttribute('data-key')]; if (x) setState(c, x.s, x.v); }); }
    progress(bar);
  });
  document.getElementById('copy').addEventListener('click', function(){
    var lines = ['VERIFICATION RESULTS ' + document.body.getAttribute('data-date')];
    $$('.bar').forEach(function(bar){
      var id = bar.getAttribute('data-bar'), ok = [], wrong = [], unchecked = [];
      $$('.ctl', bar).forEach(function(c){
        var k = c.getAttribute('data-key');
        if (c.classList.contains('ok')) ok.push(k);
        else if (c.classList.contains('wrong')) wrong.push(k + ' = ' + (c.querySelector('.fix').value || '(no value typed)').replace(/\\n/g, ' '));
        else unchecked.push(k);
      });
      lines.push('', '== ' + id);
      lines.push('matches: ' + (ok.join(', ') || 'none'));
      lines.push('wrong: ' + (wrong.length ? '' : 'none')); wrong.forEach(function(w){ lines.push('  - ' + w); });
      lines.push('not checked: ' + (unchecked.join(', ') || 'none'));
      lines.push('whole foods: ' + (bar.querySelector('.wf').value || 'not checked'));
      var n = bar.querySelector('.notes').value.trim(); if (n) lines.push('notes: ' + n.replace(/\\n/g, ' '));
    });
    var ta = document.getElementById('result'); ta.value = lines.join('\\n'); ta.select();
    var st = document.getElementById('status');
    try { document.execCommand('copy'); st.textContent = 'Copied. Paste it into the chat.'; } catch (e) { st.textContent = 'Select the text and copy it.'; }
  });
})();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", help="comma-separated bar ids")
    ap.add_argument("--all", action="store_true", help="include verified bars too")
    args = ap.parse_args()

    if args.ids:
        want = set(args.ids.split(","))
        bars = [b for b in v.BARS if b["id"] in want]
    elif args.all:
        bars = list(v.BARS)
    else:
        bars = [b for b in v.BARS if b["verification"]["status"] != "verified"]
    if not bars:
        raise SystemExit("Nothing to verify. Every bar is already verified (use --all or --ids to re-check).")

    known = {b["brand"] for b in v.BARS if b["verification"]["status"] == "verified" and b not in bars}
    today = datetime.date.today().isoformat()
    summary = "".join(
        f"<tr><td><a href='#{esc(b['id'])}'>{esc(b['brand'])} {esc(b['flavor'])}</a></td>"
        f"<td>{'known brand' if b['brand'] in known else '<b>new brand</b>'}</td><td data-sum='{esc(b['id'])}'>0</td></tr>"
        for b in bars)
    blocks = "\n".join(bar_block(b, known) for b in bars)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Verification sheet</title><style>{CSS}</style></head>
<body data-sheet="{esc(today)}-{len(bars)}" data-date="{esc(today)}"><div class="wrap">
<h1>Verification sheet</h1>
<div class="intro"><b>How to use this</b><ol>
<li>For each bar, open its brand page with the black button.</li>
<li>Compare each value here with the page. Click <b>Matches</b>, or <b>Wrong</b> and type the right value. <b>All match</b> marks a whole section.</li>
<li>When you are done, click <b>Copy results</b> at the bottom and paste the text into the chat. Anything you did not check stays unverified.</li></ol>
<p class="note" style="margin:8px 0 0">Your clicks are kept in this browser if you close the page. Compare against the brand's own page, not a store listing.</p></div>
<table class="summary"><tr><th>Bar</th><th>Brand</th><th>Checked</th></tr>{summary}</table>
{blocks}
<div class="out"><button type="button" id="copy">Copy results</button><span class="status" id="status"></span>
<textarea id="result" readonly placeholder="Your results appear here"></textarea></div>
</div><script>{JS}</script></body></html>"""
    OUT.mkdir(exist_ok=True)
    (OUT / "sheet.html").write_text(page, encoding="utf-8")
    print(f"Wrote {OUT / 'sheet.html'} with {len(bars)} bar(s). Open it in your browser.")


if __name__ == "__main__":
    main()
