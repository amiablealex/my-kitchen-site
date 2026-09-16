"""My Kitchen — showcase & documentation site.

A deliberately small Flask + Jinja site that mirrors the main app's architecture
(server-rendered, no build step) and deploys the same way: gunicorn behind nginx,
restarted by the 5-minute git-pull cron. Static assets are served directly by
nginx (see deploy/nginx-mykitchen-web.conf); Flask only renders the pages.

Run locally:   flask --app app run --debug
Run in prod:   gunicorn app:app --workers 2 --bind 127.0.0.1:8008
"""

import html as _html
import json
import logging
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

from flask import Flask, Response, abort, render_template, url_for
from markupsafe import Markup, escape
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
log = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent

# Behind nginx + a Cloudflare tunnel. Trust one proxy hop for the forwarded
# host/proto so url_for and request.url reflect the public https origin.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# --------------------------------------------------------------------------- #
# Site config — the single place to edit names, URLs and the GitHub link.
# Set SITE["url"] to your real domain once DNS is live (used for canonical and
# social-share tags). Everything else is wired off this dict.
# --------------------------------------------------------------------------- #
SITE = {
    "name": "My Kitchen",
    "tagline": "The self-hosted recipe brain for your house.",
    "blurb": (
        "My Kitchen turns what's actually in your kitchen into delicious, varied "
        "recipes — and remembers everything you cook, save and stock. Self-hosted, "
        "private, and at home in Home Assistant."
    ),
    "url": "https://my-kitchen.io",
    "github": "https://github.com/amiablealex/my-kitchen",
    # The Home Assistant add-on repository URL users paste into HA. This is the
    # repo that contains repository.yaml + addon/ — i.e. the app repo.
    "ha_repo": "https://github.com/amiablealex/my-kitchen",
}

NAV = [
    ("index", "Home"),
    ("recipes", "Recipes"),
    ("get_started", "Get started"),
    ("docs", "Docs"),
    ("approach", "Approach"),
    ("faq", "FAQ"),
]


@app.context_processor
def inject_globals():
    return {"site": SITE, "nav": NAV, "year": datetime.now().year}


# --------------------------------------------------------------------------- #
# Changelog
#
# The release notes live in the app repo, not here. Rather than keeping a second
# copy in sync by hand (which would go stale within two releases), the Releases
# page reads the app's CHANGELOG.md straight from GitHub and caches it in memory.
# Write once, never touch again: a release in the app repo shows up here on its
# own. If GitHub is unreachable the page degrades to a link — nothing else on the
# site depends on this.
# --------------------------------------------------------------------------- #
_RAW = "https://raw.githubusercontent.com/amiablealex/my-kitchen/main"
# Tried in order; the first that responds wins and is remembered. Covers the
# changelog living at the repo root or inside addon/ (where HA reads it from).
CHANGELOG_URLS = (f"{_RAW}/addon/CHANGELOG.md", f"{_RAW}/CHANGELOG.md")
CHANGELOG_TTL = 3600  # seconds
CHANGELOG_TIMEOUT = 5  # seconds
MAX_RELEASES = 25

_changelog_cache = {"fetched_at": 0.0, "releases": [], "url": None}

_HEADING_RE = re.compile(r"^(?P<version>\S+)(?:\s*[-—–]\s*(?P<title>.+))?$")
_BULLET_RE = re.compile(r"^[-*]\s+(?P<text>.*)$")


def _inline(text):
    """Escape, then apply the tiny subset of Markdown the changelog actually uses."""
    out = _html.escape(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"\*([^*\n]+?)\*", r"<em>\1</em>", out)  # after ** so none remain
    out = re.sub(r"`([^`]+?)`", r"<code>\1</code>", out)
    return out


def _render_body(lines):
    """Turn a release's raw lines into paragraphs and lists.

    Deliberately forgiving: the changelog is hand-written, so bullet
    continuations appear both indented and not, and blank lines turn up between
    bullets of the same list.
    """
    chunks, para, items, gap = [], [], [], False

    def flush_para():
        nonlocal para
        if para:
            chunks.append("<p>" + _inline(" ".join(para)) + "</p>")
            para = []

    def flush_items():
        nonlocal items
        if items:
            body = "".join("<li>" + _inline(i) + "</li>" for i in items)
            chunks.append("<ul>" + body + "</ul>")
            items = []

    for raw in lines:
        line = raw.strip()
        if not line:
            flush_para()
            gap = True
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            flush_para()
            items.append(bullet.group("text").strip())
            gap = False
            continue
        if items and not gap:
            items[-1] += " " + line  # wrapped bullet
            continue
        flush_items()
        para.append(line)
        gap = False

    flush_para()
    flush_items()
    return Markup("".join(chunks))


def _parse_changelog(text):
    releases, current = [], None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            match = _HEADING_RE.match(line[3:].strip())
            if not match:
                current = None
                continue
            current = {
                "version": match.group("version"),
                "title": (match.group("title") or "").strip(),
                "lines": [],
            }
            releases.append(current)
        elif current is not None:
            current["lines"].append(line)

    return [
        {
            "version": r["version"],
            "title": r["title"],
            "body": _render_body(r["lines"]),
        }
        for r in releases
    ][:MAX_RELEASES]


def get_releases():
    """Cached changelog. Returns [] only if the fetch fails with nothing cached."""
    now = time.time()
    if _changelog_cache["releases"] and now - _changelog_cache["fetched_at"] < CHANGELOG_TTL:
        return _changelog_cache["releases"]

    # A URL that worked before is tried first; otherwise work through the list.
    known = _changelog_cache["url"]
    candidates = [known] + [u for u in CHANGELOG_URLS if u != known] if known else list(CHANGELOG_URLS)

    for url in candidates:
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "my-kitchen-site"}
            )
            with urllib.request.urlopen(request, timeout=CHANGELOG_TIMEOUT) as response:
                text = response.read().decode("utf-8", "replace")
        except (urllib.error.URLError, OSError, ValueError, UnicodeError):
            continue

        parsed = _parse_changelog(text)
        if parsed:
            _changelog_cache.update(releases=parsed, fetched_at=now, url=url)
            return parsed

    # Nothing worked. Keep serving whatever we had, and back off so a flapping
    # network doesn't mean a fetch attempt on every single request.
    _changelog_cache["fetched_at"] = now - (CHANGELOG_TTL - 60)
    return _changelog_cache["releases"]


# --------------------------------------------------------------------------- #
# Recipes
#
# Recipes exported from the app (the "Download recipe data" link on its print
# view) are committed to content/recipes/<slug>.json; the filename is the URL.
# An optional matching PDF goes in static/recipes/<slug>.pdf and gets a download
# button. Nothing else to wire up: the folder is re-read whenever a file in it
# changes, so a git pull is enough and no restart is needed.
#
# Two optional keys can be added by hand to an exported file:
#   "published": "2026-09-15"   ordering, newest first (defaults to exported_at)
#   "note": "..."               a line from our kitchen, shown under the sheet
# --------------------------------------------------------------------------- #
RECIPES_DIR = BASE_DIR / "content" / "recipes"
RECIPE_PDF_DIR = BASE_DIR / "static" / "recipes"
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

_recipes_cache = {"signature": None, "recipes": []}


def _clean(value):
    """Strip a text field; anything that isn't text-like becomes empty."""
    if value is None or isinstance(value, (dict, list, bool)):
        return ""
    return str(value).strip()


def _parse_date(value):
    try:
        return date.fromisoformat(_clean(value)[:10])
    except ValueError:
        return None


def _ingredient_line(amount, unit, text):
    """Amount + unit + text, dropping empty parts. Mirrors the app's
    ingredient_line macro (_ingredients.html)."""
    return " ".join(p for p in (_clean(amount), _clean(unit), _clean(text)) if p)


def _steps(items, with_timer=True):
    out = []
    for step in items if isinstance(items, list) else []:
        if not isinstance(step, dict) or not _clean(step.get("text")):
            continue
        timer = step.get("timer_minutes") if with_timer else None
        out.append({
            "title": _clean(step.get("title")),
            "text": _clean(step.get("text")),
            "timer_minutes": timer if isinstance(timer, int) and timer > 0 else None,
        })
    return out


def _load_recipe(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")

    ingredients = []
    for ing in data.get("ingredients") or []:
        if not isinstance(ing, dict):
            continue
        # "item" is the app's legacy ingredients_json key; accept either.
        line = _ingredient_line(ing.get("amount"), ing.get("unit"),
                                ing.get("text") or ing.get("item"))
        if line:
            ingredients.append({"line": line, "to_buy": bool(ing.get("to_buy"))})

    recipe = {
        "slug": path.stem,
        "title": _clean(data.get("title")),
        "blurb": _clean(data.get("blurb")),
        "intro": _clean(data.get("intro")),
        "servings": data.get("servings") if isinstance(data.get("servings"), int) else None,
        "meal_type": _clean(data.get("meal_type")),
        "cuisine": _clean(data.get("cuisine")),
        "time_band": _clean(data.get("time_band")),
        "source": _clean(data.get("source")) or "ai",
        "note": _clean(data.get("note")),
        "published": _parse_date(data.get("published") or data.get("exported_at")),
        "ingredients": ingredients,
        "prep": _steps(data.get("prep")),
        "cook": _steps(data.get("cook")),
        "tips": _steps(data.get("tips"), with_timer=False),
        "pdf": (RECIPE_PDF_DIR / f"{path.stem}.pdf").is_file(),
    }
    if not recipe["title"] or not recipe["ingredients"] or not recipe["cook"]:
        raise ValueError("needs a title, ingredients and cook steps")
    return recipe


def _recipes_signature():
    files = sorted(RECIPES_DIR.glob("*.json")) + sorted(RECIPE_PDF_DIR.glob("*.pdf"))
    return tuple((str(f), f.stat().st_mtime_ns, f.stat().st_size) for f in files)


def get_recipes():
    """Published recipes, newest first. Re-read only when the files change."""
    try:
        signature = _recipes_signature()
    except OSError:
        signature = ()
    if signature == _recipes_cache["signature"]:
        return _recipes_cache["recipes"]

    recipes = []
    for path in sorted(RECIPES_DIR.glob("*.json")):
        if not _SLUG_RE.match(path.stem):
            log.warning("Skipping recipe %s: filename must be lowercase-hyphenated", path.name)
            continue
        try:
            recipes.append(_load_recipe(path))
        except (OSError, ValueError) as exc:  # JSONDecodeError is a ValueError
            log.warning("Skipping recipe %s: %s", path.name, exc)

    # Newest first; undated recipes after dated ones, then alphabetical.
    recipes.sort(key=lambda r: r["title"].lower())
    recipes.sort(key=lambda r: r["published"] or date.min, reverse=True)
    _recipes_cache.update(signature=signature, recipes=recipes)
    return recipes


def _recipe_jsonld(recipe):
    """schema.org Recipe. No image, so no rich result, but still useful data."""
    def section(name, steps):
        return {
            "@type": "HowToSection",
            "name": name,
            "itemListElement": [
                {"@type": "HowToStep", "name": s["title"], "text": s["text"]}
                if s["title"] else {"@type": "HowToStep", "text": s["text"]}
                for s in steps
            ],
        }

    data = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": recipe["title"],
        "url": SITE["url"] + url_for("recipe", slug=recipe["slug"]),
        "author": {"@type": "Organization", "name": SITE["name"], "url": SITE["url"]},
        "recipeIngredient": [i["line"] for i in recipe["ingredients"]],
        "recipeInstructions": [
            section(name, recipe[key])
            for key, name in (("prep", "Prep"), ("cook", "Cook")) if recipe[key]
        ],
    }
    optional = {
        "description": recipe["blurb"],
        "recipeYield": str(recipe["servings"]) if recipe["servings"] else "",
        "recipeCategory": recipe["meal_type"],
        "recipeCuisine": recipe["cuisine"],
        "datePublished": recipe["published"].isoformat() if recipe["published"] else "",
    }
    data.update({k: v for k, v in optional.items() if v})
    return data


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return render_template("index.html", page="index")


@app.route("/get-started")
def get_started():
    return render_template("get_started.html", page="get_started")


@app.route("/docs")
def docs():
    return render_template("docs.html", page="docs")


@app.route("/approach")
def approach():
    return render_template("approach.html", page="approach")


@app.route("/faq")
def faq():
    return render_template("faq.html", page="faq")


def changelog_link():
    """The human-readable GitHub view of whichever changelog we're reading."""
    raw = _changelog_cache["url"] or CHANGELOG_URLS[0]
    return raw.replace("raw.githubusercontent.com", "github.com").replace(
        "/main/", "/blob/main/", 1
    )


@app.route("/releases")
def releases():
    return render_template(
        "releases.html",
        page="releases",
        releases=get_releases(),
        changelog_url=changelog_link(),
    )


@app.route("/privacy")
def privacy():
    return render_template("privacy.html", page="privacy")


@app.route("/recipes")
def recipes():
    return render_template("recipes.html", page="recipes", recipes=get_recipes())


@app.route("/recipes/<slug>")
def recipe(slug):
    all_recipes = get_recipes()
    index = next((i for i, r in enumerate(all_recipes) if r["slug"] == slug), None)
    if index is None:
        abort(404)
    return render_template(
        "recipe.html",
        page="recipes",
        recipe=all_recipes[index],
        prev_recipe=all_recipes[index - 1] if index > 0 else None,
        next_recipe=all_recipes[index + 1] if index + 1 < len(all_recipes) else None,
        position=index + 1,
        total=len(all_recipes),
        jsonld=_recipe_jsonld(all_recipes[index]),
    )


@app.route("/sitemap.xml")
def sitemap():
    entries = [(url_for(endpoint), None) for endpoint, _ in NAV]
    entries += [(url_for("releases"), None), (url_for("privacy"), None)]
    entries += [(url_for("recipe", slug=r["slug"]), r["published"]) for r in get_recipes()]
    body = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, lastmod in entries:
        body.append("  <url><loc>%s</loc>%s</url>" % (
            escape(SITE["url"] + path),
            "<lastmod>%s</lastmod>" % lastmod.isoformat() if lastmod else "",
        ))
    body.append("</urlset>")
    return Response("\n".join(body) + "\n", mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    text = "User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n" % SITE["url"]
    return Response(text, mimetype="text/plain")


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html", page=None), 404


if __name__ == "__main__":
    app.run(debug=True, port=8008)
