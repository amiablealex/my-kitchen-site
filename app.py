"""My Kitchen — showcase & documentation site.

A deliberately small Flask + Jinja site that mirrors the main app's architecture
(server-rendered, no build step) and deploys the same way: gunicorn behind nginx,
restarted by the 5-minute git-pull cron. Static assets are served directly by
nginx (see deploy/nginx-mykitchen-web.conf); Flask only renders the pages.

Run locally:   flask --app app run --debug
Run in prod:   gunicorn app:app --workers 2 --bind 127.0.0.1:8008
"""

from datetime import datetime

from flask import Flask, render_template
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
    # TODO: set to your real domain (no trailing slash), e.g. https://mykitchen.example
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
    ("faq", "FAQ"),
]


@app.context_processor
def inject_globals():
    return {"site": SITE, "nav": NAV, "year": datetime.now().year}


@app.route("/")
def index():
    return render_template("index.html", page="index")


@app.route("/get-started")
def get_started():
    return render_template("get_started.html", page="get_started")


@app.route("/docs")
def docs():
    return render_template("docs.html", page="docs")


@app.route("/faq")
def faq():
    return render_template("faq.html", page="faq")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html", page="privacy")


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html", page=None), 404


if __name__ == "__main__":
    app.run(debug=True, port=8008)
