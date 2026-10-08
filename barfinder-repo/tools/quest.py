"""Quest-specific wrapper around entry.py: every Quest flavor page has the same layout."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from entry import *

D = "2026-10-06"
BASE = "https://www.questnutrition.com/products/"
ICON = (True, "brand_page", "Gluten Free icon on the product page. Confirm on package.")
NOICON = (None, "none", "No gluten-free icon on this product page. The collection page FAQ says Quest Protein Bars are gluten-free. Check the package.")


def quest(slug, id, flavor, upc, n, ingredients, contains, facility, gf, packs, availability=None, claims_raw=(), flags=(), line="Protein Bars", pasted=False, serving=("1 bar (60g)", 60, 12, False)):
    """packs: [(bars, list_price, subscription_price_or_None, in_stock), ...]"""
    allflags = list(flags) + (["Barcode is the 12-count box barcode (the 4-count box has its own)."] if upc else ["UPC not captured."]) + [
        "Whole Foods carriage of this flavor not checked.",
        "No label image checked; values come from page text only."]
    source = ({"type": "brand_text_pasted", "url": BASE + slug, "retrieved": D,
               "note": "Nutrition, ingredients and allergen lines pasted by the owner from the brand page. Prices are the standard Quest prices from the collection page."}
              if pasted else src(BASE + slug, D, "Nutrition, ingredients, contains line, prices and barcodes from the product page."))
    bar = make_bar(id=id, brand="Quest", line=line, flavor=flavor, upc=upc, serving_text=serving[0], serving_g=serving[1],
                   servings_per_container=serving[2], inferred=serving[3], n=n, ingredients=ingredients, contains=contains, facility=facility, gf=gf,
                   nongmo=(False, "brand_page", "Treated as not Non-GMO Project Verified for all Quest bars (owner decision). No such claim seen on the pages checked."),
                   claims_raw=claims_raw, availability=availability,
                   sources=[source],
                   flags=allflags)
    offers = []
    for bars_, price, sub, stock in packs:
        offers.append(make_offer(id=f"{id}-direct-{bars_}", bar_id=id, retailer="questnutrition.com", url=BASE + slug, pack=bars_,
                                 list_price=price, sub=sub, date=D, in_stock=stock,
                                 note=("Subscription price is 15% off. Free shipping over $99." if sub else "Free shipping over $99.") +
                                      ("" if stock else " Sold out at retrieval.")))
    return bar, offers


STD_NOSUB = [(4, 12.49, None, True), (12, 35.49, None, True), (36, 99.97, None, True)]
STD = [(4, 12.49, 10.62, True), (12, 35.49, 30.17, True), (36, 99.97, 84.97, True)]


def add(items):
    bars = [b for b, _ in items]
    offers = [o for _, os in items for o in os]
    print(append("data/bars.json", bars, fmt_bar), "bars,", append("data/offers.json", offers, fmt_offer), "offers added")
