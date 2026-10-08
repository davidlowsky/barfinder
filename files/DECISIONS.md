# Schema v0.1: decisions and known limits

Run `python3 validate.py` (needs `pip install jsonschema`).

## Structure
- `data/bars.json`: one record per flavor. Facts and sources only.
- `data/offers.json`: one record per purchasable pack. Price, pack size, retailer, date.
- Derived tags (sweeteners, dairy, vegan, allergens, price per bar) are computed by `validate.py`. Never hand-edit them.
- `keywords.json`: maintained lists that drive the derived tags.

## Decisions so far
- **Claims** are `true`, `false`, or `null` (unknown), each with a source. Filters match `true` only. The UI should say "not confirmed" for `null`.
  - USDA Organic = the seal. Non-GMO = Non-GMO Project Verified seal (a generic "non-GMO" badge stays `null`). Gluten-free = the bar's own label claim.
- **Dairy-free and vegan** are derived from ingredients only, worded "No dairy ingredients" and "No animal ingredients listed". "Natural flavor" is always noted as a caveat.
- **Artificial sweeteners** = sucralose, aspartame, acesulfame potassium, saccharin, neotame, advantame. Shown in a tooltip.
- **Sugar alcohols** = erythritol, xylitol, maltitol, sorbitol, mannitol, lactitol, isomalt, HSH. **Vegetable glycerin is not counted and not tagged in v1** (decision logged; revisit later).
- **Nulls matter.** `added_sugars_g: null` = not reported (not zero). `sugar_alcohol_g: null` = no line on the label.
- **Facility and "may contain" statements** are stored as verbatim text and never folded into dairy-free, vegan, or allergen tags.
- **Prices** live on offers, are labeled approximate, and carry a date. Per-bar price uses the sale price when present. Subscription price is shown separately.
- **Images:** none at launch. `image.source` is `none | own | licensed`.

## Known limits of keyword matching
- "Natural flavor" cannot be traced to its source.
- Cane sugar processed with bone char cannot be detected from a label.
- An unlisted nut butter (e.g. "pumpkin butter") could be misread as dairy butter; add it to `dairy_exceptions`.
- Coconut is not treated as a tree nut.
- "And/or" ingredients are tagged "possible", not definite.
- Lists must be tested on every new batch of bars.

## Open items
- Human verification of all three pilot bars (fields to check: protein, calories, sugars, ingredients, seals).
- UPC for the Clif bar.
- Contains and facility statements for the Clif bar and Aloha.
