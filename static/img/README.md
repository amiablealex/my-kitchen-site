# Images

These are branded **placeholders**. To use a real image, overwrite the file
**keeping the same filename** — the templates reference these names, so nothing
else needs editing.

| File | Where it appears | Recommended size |
|---|---|---|
| `screenshot-home.png` | Home hero | 1080 × 2040 (phone portrait) |
| `screenshot-wizard.png` | Home → “A look inside” | 1080 × 2040 |
| `screenshot-suggestions.png` | Home → “A look inside” | 1080 × 2040 |
| `screenshot-recipe.png` | Home → “A look inside” | 1080 × 2040 |
| `og-image.png` | Social share card (link previews) | 1200 × 630 |

Tips
- Phone screenshots can be any portrait ratio; the frame adapts. Matching the
  sizes above keeps them crisp and consistent.
- To **add** a screenshot rather than replace one, drop the file in here and add
  another `<figure class="shot">…</figure>` block in `templates/index.html`.
- To regenerate the placeholders, the original script is `make_placeholders.py`
  (kept at the repo root for reference).
