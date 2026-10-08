# Setting up the private test link

Result: every time you push a change to GitHub, a private copy of the site is rebuilt and the link updates in about a minute. If the data has an error, the build fails and the link keeps showing the last good version.

The test site includes every bar, tags the unchecked ones, shows a "Test version" banner, and tells search engines to stay away. Anyone you give the link to can open it, unless you also do step 3.

## 1. Put the project on GitHub (private)
1. On github.com choose New repository. Name it `barfinder`. Choose **Private**. Do not add a README or other files.
2. Unzip `barfinder-repo.zip` so the files (`data/`, `build_site.py`, `.github/` and the rest) are at the top level of one folder.
3. In that folder, in a terminal:
```
git init
git add .
git commit -m "First version"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/barfinder.git
git push -u origin main
```
No terminal? On the new repository's page choose "uploading an existing file" and drag in everything from the unzipped folder. Check that the hidden `.github` folder came across, and add it again if not.

The `check` action under the repository's Actions tab should turn green. It runs the validator and builds the test site.

## 2. Connect Cloudflare Pages
1. Create a free Cloudflare account. Go to Workers & Pages, create a **Pages** project, and choose **Connect to Git**. Cloudflare may ask you to authorize its GitHub app. Pick **only** the `barfinder` repository.
2. Build settings:
   - Framework preset: None
   - Build command: `pip install -r requirements.txt && python3 validate.py && python3 build_site.py --private`
   - Build output directory: `public`
   - Environment variable: `PYTHON_VERSION` = `3.12` (if the build complains about the version, delete this variable and try again)
3. Save and deploy. When it finishes you get an address like `barfinder.pages.dev`. Every later push to `main` rebuilds it. Menu names change now and then, so follow Cloudflare's current "Git integration" guide if a label differs.

## 3. Lock it with a login (recommended before sharing unchecked allergen data)
1. In Cloudflare open Zero Trust, then Access, and add a **Self-hosted** application.
2. Application domains: `barfinder.pages.dev` and `*.barfinder.pages.dev` (the second covers the extra address every deployment gets).
3. Add an **Allow** policy that lists the testers' email addresses, or "emails ending in" a domain.
4. Make sure the One-time PIN login method is on (Zero Trust, Settings, Authentication, Login methods). Testers type their email and receive a code.
5. Free for up to 50 users at the time of writing. Check Cloudflare's current limits.

Without this step the link is unlisted but not secure: anyone who gets it can open it.

## Everyday use
1. You receive new `data/bars.json` and `data/offers.json` from me (and sometimes `site_src/` or `build_site.py`).
2. Replace the files in the repository (commit and push, or edit through the GitHub web page).
3. Wait about a minute and reload the link.

If the build fails, open the failed build in Cloudflare or the red check under Actions. The message says which record is wrong. Send it to me.

## Later: the public launch
Create a second Pages project from the same repository with build command `pip install -r requirements.txt && python3 validate.py && python3 build_site.py` and output directory `site`. That build shows only verified bars, with no banner and no noindex. Before that, set `SITE_URL` and `SITE_NAME` near the top of `build_site.py`.

## Things to remember
- The repository is private, but the data in it is not secret. Never put passwords or tokens in it.
- Don't paste access tokens into a chat. Pushing the files yourself keeps your accounts yours.
- Unchecked bars may be wrong. The banner says so. Keep it.
