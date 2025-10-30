# Developing PeachJam

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

## Common Footguns (and how we avoid them)

* Vary: Cookie on public pages → stripped by last middleware if the page is truly public.
* Accidental CSRF fields in public HTML → sanity middleware fails the request.
* Messages rendered on public pages → moved to /user/loaded (private).

If you’re unsure whether something belongs in the cacheable HTML or an island, default to island. It’s easy to merge later; it’s much harder to unwind a cache leak.
