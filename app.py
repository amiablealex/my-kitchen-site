"""My Kitchen — showcase & documentation site.

A deliberately small Flask + Jinja site that mirrors the main app's architecture
(server-rendered, no build step) and deploys the same way: gunicorn behind nginx,
restarted by the 5-minute git-pull cron. Static assets are served directly by
nginx (see deploy/nginx-mykitchen-web.conf); Flask only renders the pages.

Run locally:   flask --app app run --debug
Run in prod:   gunicorn app:app --workers 2 --bind 127.0.0.1:8008
"""

import html as _html
import re
import time
import urllib.error
import urllib.request
from datetime import datetime

from flask import Flask, render_template
from markupsafe import Markup
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)

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


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html", page=None), 404


if __name__ == "__main__":
    app.run(debug=True, port=8008)
