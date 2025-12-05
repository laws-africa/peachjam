# Developing PeachJam

## Prerequisites

- PostgreSQL
- pip
- Elasticsearch
- global Sass

## Local setup

1. Clone the repository:

   ```bash
   git clone https://github.com/laws-africa/peach-jam.git
   ```

2. Set up and activate a Python 3.6+ virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -e .[dev]
   pip install psycopg[binary]==3.2.12
   ```

4. Ensure PostgreSQL is running, then create a `peachjam` user and database:

   ```bash
   sudo su - postgres -c 'createuser -d -P peachjam'
   sudo su - postgres -c 'createdb peachjam'
   ```

5. Optionally export a custom connection string to override the default:

   ```bash
   export DATABASE_URL=postgres://<USER>:<PASSWORD>@<HOST>:<PORT>/<DATABASE_NAME>
   ```

6. Run migrations and initial data setup:

   ```bash
   python manage.py migrate
   python manage.py setup_countries_languages
   python manage.py loaddata ./peachjam/fixtures/documents/sample_documents.json
   ```

7. Create an admin user:

   ```bash
   python manage.py createsuperuser
   ```

8. Start the dev server:

   ```bash
   python manage.py runserver
   ```

## Setup pre-commit

The project has linting enabled using pre-commit. It runs on the CI pipeline, so you need to enable locally as well. Run
the following to allow Precommit to format and fix any linting errors on your code.
```
pre-commit install
```

## Adding translation strings

Translations for strings are added on [CrowdIn](https://laws-africa.crowdin.com/).

Django translations are stored in the `locale` directories under each sub-project. Javascript and Vue translations are stored in `peachjam/js/locale/en/translation.json`.

If you have added or changed strings that need translating, you must [tell Django to update the .po files](https://docs.djangoproject.com/en/3.2/topics/i18n/translation/#localization-how-to-create-language-files) so that translations can be supplied through CrowdIn.

```bash
scripts/extract-translations.sh
```

And then commit the changes. CrowdIn will pick up any changed strings and make them available for translation. Once they are translated, it will open a pull request to merge the changes into `main`.

## Front-end build workflow

Peachjam's TypeScript and Vue source lives under `peachjam/js` and is compiled into static JavaScript with webpack.
During local development run;

```
npx webpack -w --mode development
```

from the project root to watch and rebuild assets whenever you save. Do not commit the generated files in
`peachjam/static/js/`, that will be built automatically on `main` as described below.

Any time a change lands on `main`, [the build workflow](.github/workflows/build.yml) runs webpack and compares the
compiled output with the previous commit. If real differences are detected, the workflow commits the updated bundles
back to `main`. That follow-up commit is what ultimately lands the production-ready JavaScript in the repository, so
developers do not need to worry about checking in built assets themselves. This commit includes `[nobuild]` in the
commit message to prevent a circular build loop.

The same push to `main` also triggers [the deployment workflow](.github/workflows/deploy.yml) which pushes the code to
each Dokku target in turn. If you are merging a pull request and want to avoid that deploy, include `nodeploy` anywhere
in your merge commit message so that the workflow skips its jobs.

## Caching

This project serves one shared, cacheable HTML to everyone (anonymous and signed-in), and then hydrates small, per-user “islands” after page load. This keeps pages fast via public caches, while still showing user-specific UI (menu/profile chip, favourites, flash messages, etc.).

Below is what’s implemented, why, and how to build new pages without breaking caching.

### Goals

* Speed for everyone: aggressive shared caching (CDN + browser) on public pages.
* Zero cache leaks: no user-specific data in cacheable HTML.
* Clean separation: per-user content loads from private endpoints (not cacheable).
* Predictable behavior: guardrails via middleware and a few conventions.

### What’s Implemented

#### Public HTML + Private Islands

* Cacheable pages (e.g. documents, listings, home) render no user-specific content.
* Headers (example): Cache-Control: public, max-age=60, stale-while-revalidate=120, stale-if-error=600
* Per-user islands (loaded after DOM ready via htmx GETs)
* On every pageload, htmx GETs /user/loaded (private, no-store) to get user info (name, avatar), messages (toasts), and other per-user bits.
* Restricted pages (permissioned docs/taxonomies): not cacheable (private, no-store).

Reasoning: Public HTML becomes identical for all users → the CDN can reuse it broadly. Personalization moves to private endpoints that are safe to call with cookies and can set/refresh cookies without polluting caches.

#### Cookies, Sessions, and Messages

* We use signed-cookie sessions only for authenticated users.
* Django messages use the default SessionStorage, but are never rendered in cacheable HTML.
* Instead, view classes use messages.info(...), and /user/loaded returns the messages as HTML for a toast UI.
* CSRF is not emitted in public HTML. Use /_token to set the cookie, then send X-CSRFToken on unsafe requests.

Reasoning: Keeps public pages cookie-agnostic and avoids Set-Cookie on cacheable responses.

#### i18n & URLs

* Language for multi-language sites is in the URL prefix (/en/..., /fr/...), not in cookies.

Reasoning: Distinct URLs → distinct cache keys and SEO-friendly.

#### Middleware Guardrails

* Sanity middleware (last in stack): if a response is cacheable, it asserts:
* no Set-Cookie
* no Vary: Cookie
* no CSRF hidden inputs in HTML (heuristic)

Reasoning: Fail fast in dev; avoid accidental cache poisoning in prod.

### How to Build New Pages

When your page is public/cacheable

#### Do

* Render no user-specific data (assume the viewer is anonymous).
* Load any personalized bits via htmx GET islands.
* If a form uses POST, use `data-csrf` to ensure it automatically gets a CSRF token when submitted.

#### Don’t

* Touch request.session, messages, or get_token() during render.
* Include {% csrf_token %} in the template.
* Emit Set-Cookie or Vary: Cookie.

### Tips

If your page is private / personalized / restricted, mark as not cacheable with `never_cache` or equivalent.

In that case, it’s fine if it reads/writes the session, sets cookies, renders {% csrf_token %}, or displays messages inline.

When you need a form or unsafe POST on a public page, render the form via a private island (htmx GET) so the response can set CSRF safely,
or use `data-csrf` on the form to fetch /_token automatically.

Per-user islands (htmx):

* Endpoints must return small JSON or HTML fragments and be private, no-store.
* Batch where possible (e.g., ?ids=1,2,3 for favourites).
* Keep payloads and DB work tiny—these run on every page view for signed-in users.

### Common Footguns (and how we avoid them)

* Vary: Cookie on public pages → stripped by last middleware if the page is truly public.
* Accidental CSRF fields in public HTML → sanity middleware fails the request.
* Messages rendered on public pages → moved to /user/loaded (private).

If you’re unsure whether something belongs in the cacheable HTML or an island, default to island. It’s easy to merge later; it’s much harder to unwind a cache leak.

## Favicons

To generate or update a favicon for a site:

1. `pip install favicons`
2. create a .PNG of the icon and put it into lii-name/static/images/lii-name-icon.png
3. run the favicons CLI as follows (it seems a bit broken):

```
python .env/lib/python3.10/site-packages/favicons/cli.py generate --source lii-name/static/images/lii-name-icon.png --output-directory t
```

That will generate a bunch of icons in the director `t/`.

Copy only certain files into the project:

```
cp t/favicon.ico t/favicon-16x16.png t/favicon-32x32.png t/favicon-96x96.png t/favicon-180x180.png lii-name/static/images/
```

## Admin theme

Peachjam customises the Django admin view using [Django Jazzmin](https://django-jazzmin.readthedocs.io/). We build
a custom bundle of Bootstrap 4 specifically for the admin area from the [jazzmin-theme](jazzmin-theme) directory.

To make changes to it:

```bash
cd jazzmin-theme
npm i
# make your changes to peachjam-jazzmin.scss
# ...
npm run watch
```

Once you're done, run:

```bash
npm run build
```

and commit both your changes, and the updated [peachjam/static/stylesheets/peachjam-jazzmin.css](peachjam/static/stylesheets/peachjam-jazzmin.css).
