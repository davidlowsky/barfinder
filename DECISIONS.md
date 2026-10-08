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

## Added after the Quest Pumpkin Pie bar
- **Allergen exclusion filters should exclude on definite OR possible.** A printed "Contains" line can resolve an "and/or" ingredient (Quest lists soy lecithin only as "sunflower and/or soy", and the label says Contains soy).
- **Net carbs** is a brand term (total carbs minus fiber minus sugar alcohols). Stored as a raw claim only; if we display it, we define it on the page.
- **"0g added sugars" can hide trace amounts.** Quest footnotes molasses and juice as adding a trivial amount. Note that rounding below 0.5g shows as 0.
- **Limited and seasonal flavors** are kept out of the launch catalog (flag in `review_flags`).

## Added after the No Cow bar
- **"<1g" label values.** Stored as the printed bound (here 1) and the field name goes in `nutrition.less_than`. Max-style filters treat it as "at most X", which errs on the safe side.
- **Plant-protein %DV is lower than 20g/50g.** Aloha (14g) shows 17% and No Cow (20g) shows 22%, while soy and dairy bars show 40%. Not stored; a possible later "protein quality" note.
- **Reformulation risk.** No Cow's wrapper carries a "New Great Taste" badge and reviews mention changed formulas, so retailer data for it may be stale.

## Evidence rule for claims (added after the No Cow correction)
- A claim counts only if it appears in visible page text, a visible icon or badge, the label image, the package, or the brand's own certifications page. **Hidden meta tags (meta description, og:description) and machine-readable summaries do not count.** A claim found only there is recorded as unknown and noted.

## Website decisions
- **Built with a small Python script, not Astro or Next.js.** It reuses the validator's tag logic, needs no Node or npm, and produces plain static files. Easy to review; can be swapped for a framework later if needed.
- **Verified bars only** appear by default. `--include-drafts` is for previews.
- **Filters:** every limit must be met (AND). Exclusions hide a bar if an ingredient is definite or possible ("and/or"). "Must have" shows only bars where the claim is confirmed. A bar with an unknown value is hidden when a filter needs that value.
- **Price shown is the cheapest in-stock pack** (sale price if there is one), labeled with its pack size. Subscription prices are shown on the bar page only.
- **Default sort is most protein.** Open question: whether the default should be something else.
- **Plain-language wording:** "Labeled", "No dairy ingredients", "Vegan by ingredients", "Not confirmed". No bar page says a bar "is" gluten-free.
- **No affiliate links yet.** The footer says so; flip `AFFILIATE_LINKS` in `build_site.py` when that changes.

## Layout decisions (list of results)
- **Flavor stays the unit.** Brand cards would hide per-flavor differences and break sorting. Grouping is a toggle instead.
- **Rows are the default on phones, cards on wide screens.** A row is about 95px tall and a card about 320px. Rows show protein, calories and added sugar; any other number you filter or sort on is added to the row.
- **Group by brand** puts brand headings over the bars and orders brands by their best match for the current sort.
- **Paging:** 20 bars at a time, "Show more" for the rest. When grouped, whole brands are added so a group is never cut in half.
- **Open question:** whether to compare these views again once there are 30 to 40 bars.

## Verification process (from the 10-bar pilot)
- **Every new bar is checked by a person against the brand's own page**, using the verification sheet. Claims and seals are always checked.
- **Reassess after about 30 clean bars.** If the error count stays near zero, move to checking a sample plus every risky bar. The error count will be reported before that decision.
- **Seen at Whole Foods** is recorded per bar (`whole_foods`), by the owner. It is not inferred.
- **Skip for the launch catalog:** limited and seasonal flavors, variety packs, and flavors that are sold out everywhere.

- **Quest and Non-GMO:** all Quest bars are treated as not Non-GMO Project Verified (owner decision). The claim is `false` on every Quest record, including future ones.

- **The printed "Contains" line always counts for allergen filters and display.** It settles "and/or" ingredients and also catches allergens the ingredient list does not show (found on David Bronze Peanut Butter Chocolate, where soy is named on the line but is not an ingredient).

## Brands view (prototype)
- **Brands is now the first view;** Rows and Cards are the flat flavor lists. Flavors remain the unit underneath, so every filter works at flavor level.
- **A brand with several lines becomes several cards** (David Gold and David Bronze).
- **Every brand statement is computed from the flavors** as "all", "N of M", or absent. Nothing is written by hand.
- **Brand cards show a live "N of M flavors match,"** brands with no match fade to the bottom, and opening a brand lists matching flavors first and the rest dimmed.
- **The Brands view is a comparison table** (one row per brand): protein, calories, added sugar and price ranges, then sweeteners, allergens and labels as "All", "N/M" or a dash. Red marks things some people avoid, black marks labels. The brand column stays fixed while the table scrolls sideways on a phone. Tapping a row opens the brand.
- **Opening a brand shows a flavor table** (one row per flavor) with exact numbers (protein, calories, fiber, added sugar, sugar alcohol, price) and Yes or dash for each sweetener, allergen and label. Matching flavors come first, the rest are dimmed under a divider, and tapping a row opens the single-flavor page. Organic and Non-GMO are permanent columns in both tables.
- **The filters stay visible on the left** (owner preference: it makes filtering obvious). To avoid sideways scrolling in the tables, columns are grouped under tabs. On wide screens: Macros and sweeteners, Allergens and labels, and All columns. On phones: Macros, Sweeteners, Contains, Labels, and All. The table shows every column on its own whenever they fit, and otherwise starts on the first tab; picking a tab is remembered.
- **Open question (resolved by the layout above):** the table has 15 columns. On a wide screen next to the filter panel it scrolls sideways.

- **Brand names show the product line when it is a named line** (CLIF Builders, David Gold, RXBAR Classic 12g, GoMacro MacroBar, think! High Protein) and leave out generic ones (Quest, Barebells, EPIC, No Cow, ALOHA). A brand's other lines (for example Clif's regular bars) would get their own rows.

- **Table columns (owner decisions):** the tables show Protein, Calories, Protein per 100 calories, Carbs (and Fiber in the flavor table), with Price as the last column, always visible. Added sugar is no longer a table column because syrups can keep it low while carbs stay high. It remains a filter and appears on each bar's page, in Rows and Cards.

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
