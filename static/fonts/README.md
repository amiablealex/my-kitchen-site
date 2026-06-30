# Fonts

The site uses your app's two self-hosted variable fonts. Copy them here from the
main app repo (`my-kitchen/.../static/fonts/`), keeping these exact filenames:

    grandstander-var.woff2     (display / headings)
    figtree-var.woff2          (body / UI)

The CSS references them by these names (`static/css/site.css`, `@font-face`).
Until they're present the site falls back to the system sans-serif — readable,
just not on-brand — so it's safe to deploy first and add the fonts after.
