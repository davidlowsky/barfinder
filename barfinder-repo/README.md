# Bar Finder: data and website

A static website built from two JSON files. Nothing runs on a server.

## Everyday change (what happens after each update)
1. Edit `data/bars.json` and `data/offers.json` (or replace them with the versions you are sent).
2. Commit and push to GitHub. The host rebuilds and the private test link updates in about a minute.
3. If the data has an error, the build stops and the live site stays as it was. Check the failed build log.

## Build on your own computer (optional)
Needs Python 3.12 and `pip install -r requirements.txt`.
- `python3 validate.py` checks the data. Fix any ERROR.
- `python3 build_site.py --private` writes the test site to `public/` (all bars, search engines blocked, test banner).
- `python3 build_site.py` writes the verified-only site to `site/` (the future public launch build).
- `python3 build_site.py --include-drafts --preview` also writes `review.html`, one file for quick sharing.

## Checking new bars
`python3 verify_sheet.py` writes `verify/sheet.html`: every unchecked bar next to its page links, with buttons to mark each value as matching or wrong. See `DECISIONS.md` for the rules.

## Folders
- `data/` the facts: one record per flavor (`bars.json`) and per pack and shop (`offers.json`)
- `schema/` the rules for those records
- `keywords.json` the word lists behind the derived tags
- `validate.py` checks the data and works out the derived tags
- `build_site.py` writes the website; `site_src/` holds its stylesheet and script
- `tools/` helper scripts used to add records
- `DEPLOY.md` how the private test link is set up
- `DECISIONS.md` the decisions made so far

Before the public launch: set `SITE_URL` and `SITE_NAME` near the top of `build_site.py`, and deploy the verified-only build (`python3 build_site.py`, output `site/`).
