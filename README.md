# My Kitchen — website

The showcase + documentation site for [My Kitchen](https://github.com/amiablealex/my-kitchen),
a self-hosted recipe app for a household.

A small **Flask + Jinja** site, with no build step, that reuses the app's design
tokens, fonts and "Petals" components (see the app's `docs/brand-ui-guide.md`). It deploys exactly like
the app and the personal site: gunicorn behind nginx, restarted by a git-pull
cron.

---

## Layout

```
app.py                      Flask app + routes + the SITE config (edit URLs here)
requirements.txt            Flask + gunicorn
deploy.sh                   pull-and-relaunch (run from cron)
make_placeholders.py        regenerate the placeholder images (reference)
templates/
  base.html                 shell: top nav, head/meta, footer
  _icons.html               inline SVG icon macro (reused from the app)
  index.html                home
  get_started.html          install + configure
  docs.html                 documentation (sticky TOC)
  privacy.html              privacy & data
  404.html
static/
  css/site.css              tokens + Petals components (from the app) + the docs shell
  fonts/                    drop the two .woff2 here (see fonts/README.md)
  icons/                    app icons + favicon (see icons/README.md)
  img/                      screenshots + OG card (see img/README.md)
  manifest.webmanifest
deploy/
  mykitchen_web.service     systemd unit (gunicorn on :8008)
  nginx-mykitchen-web.conf  nginx server block
  cloudflare-config.example.yml
```

## Before you publish — three edits

1. **`app.py` → `SITE`**: set `"url"` to your real domain. Check `"github"` and
   `"ha_repo"` point at your app repo.
2. **`deploy/nginx-mykitchen-web.conf`**: set `server_name` to your domain.
3. **Assets**: drop the two fonts into `static/fonts/`, your app icons into
   `static/icons/`, and (when ready) real screenshots into `static/img/`. Each
   folder has a short README. The site works before you do this — fonts fall
   back to system, and the images ship as branded placeholders.

## Run it locally

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/flask --app app run --debug --port 8008
# open http://127.0.0.1:8008
```

Editing copy is just editing the templates; the dev server live-reloads.

---

## Deploy to the Pi

The site slots in beside your existing personal site: a second gunicorn service
on port **8008**, a second nginx server block, and a second Cloudflare tunnel
hostname pointing at the same nginx.

### 1. Get the code on the Pi

```bash
mkdir -p /home/pi/projects && cd /home/pi/projects
git clone <this-repo-url> my-kitchen-website
cd my-kitchen-website
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### 2. Run it as a service

```bash
sudo cp deploy/mykitchen_web.service /etc/systemd/system/mykitchen_web.service
sudo systemctl daemon-reload
sudo systemctl enable --now mykitchen_web
curl -I http://127.0.0.1:8008      # expect 200 OK
```

### 3. Point nginx at it

Set `server_name` in `deploy/nginx-mykitchen-web.conf`, then:

```bash
sudo cp deploy/nginx-mykitchen-web.conf /etc/nginx/sites-available/mykitchen-web
sudo ln -s /etc/nginx/sites-available/mykitchen-web /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

nginx now serves `/static/` off disk and proxies the rest to gunicorn — exactly
like your personal site.

### 4. Make it public (Cloudflare)

Add the new hostname to your tunnel config (`/etc/cloudflared/config.yml`),
alongside the existing one — both point at `http://localhost:80`; nginx routes
by hostname. See `deploy/cloudflare-config.example.yml`.

Create the DNS route so Cloudflare sends the hostname into the tunnel:

```bash
cloudflared tunnel route dns tunnel-name your-domain.example
sudo systemctl restart cloudflared
```

(Or add the CNAME in the Cloudflare dashboard — point the domain at the tunnel.)
Visit `https://your-domain.example` — TLS is handled by Cloudflare end-to-end.

### 5. Auto-deploy on push

Reuse your existing cron pattern with this repo's `deploy.sh`:

```bash
crontab -e
```
```
*/5 * * * * /home/pi/projects/my-kitchen-website/deploy.sh >> /home/pi/projects/my-kitchen-website/deploy.log 2>&1
```

`deploy.sh` already restarts `mykitchen_web` via `sudo systemctl restart`. If
your `pi` user doesn't already have password-less rights for that, add a
sudoers entry (mirroring your personal site's):

```
pi ALL=(root) NOPASSWD: /bin/systemctl restart mykitchen_web
```

Now editing a template on GitHub → the Pi pulls within 5 minutes → the service
restarts → the change is live.

---

## Why a separate repo

The site is kept out of the `my-kitchen` app repo on purpose: the Home Assistant
add-on clones the app repo at build time, so site assets there would bloat every
add-on build; the deploy model is one-service-per-repo; and the two have very
different change cadences. Documentation lives here; the app's README links over.
