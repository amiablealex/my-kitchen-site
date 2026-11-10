# Images

Screenshots of the app (0.29.1) and the social share card. The templates refer
to these by name, so to update one, overwrite the file and keep the filename.

| File | Where it appears | Size |
|---|---|---|
| `screenshot-stock.png` | Home → Screenshots | 1080 × 2039 |
| `screenshot-wizard.png` | Home → Screenshots | 1080 × 2039 |
| `screenshot-suggestions.png` | Home → Screenshots | 1080 × 2039 |
| `screenshot-recipe.png` | Home → Screenshots | 1080 × 2039 |
| `screenshot-kitchen.png` | Home → Screenshots | 1080 × 2039 |
| `og-image.png` | Social share card (link previews) | 1200 × 630 |

The screenshots were taken from a demo database (the two public recipes, a
believable stock list, two household members) at a 412 px wide phone viewport.
After changing one, bump the `v=` on the image URLs in `templates/index.html`
so browsers fetch the new file.
