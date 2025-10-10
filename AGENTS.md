# Repository Guidelines

## Project Structure & Module Organization
The core Django app lives in `peachjam/`, which includes templates, templatetags, migrations, locale data, and the TypeScript/Vue source under `peachjam/js`.

Supporting packages (`peachjam_api/`, `peachjam_search/`, `peachjam_subs/`) encapsulate API endpoints, search adapters, and subscription flows with their migrations, fixtures, and tests alongside code.

Jurisdiction shells such as `zambialii/` and `malawilii/` contain per-site settings while sharing compiled assets in `peachjam/static/` and collected output in `staticfiles/`.

Custom admin styling sits in `jazzmin-theme/` (ignore this directory).

Reusable scripts (data imports, translation extraction) live in `scripts/`.

## Build, Test, and Development Commands
- `pip install -e .[dev]` inside an activated virtualenv installs Django and tooling; add `pip install psycopg2-binary==2.9.3` when system headers are missing.
- `python manage.py migrate` primes the database; `python manage.py setup_countries_languages` and `python manage.py loaddata peachjam/fixtures/documents/sample_documents.json` populate reference data.
- Run the site with `python manage.py runserver`; warm Elasticsearch before testing search.
- Run automated checks with `python manage.py test` (or scoped to an app), `pre-commit run --all-files`, and `scripts/extract-translations.sh`.
- Ignore the `jazzmin-theme` directory, and you don't.
- You don't need to compile javascript or SCSS before committing, CI handles that.

## Coding Style & Naming Conventions
Python code is formatted by Black and ordered with isort (Black profile) while Flake8 enforces a 120-character limit and ignores E203. Use 4-space indentation, descriptive module names, and keep Django apps cohesive.

Templates must pass djLint and remain free of user-specific content when cached. Front-end files follow the ESLint Standard + Vue 3 configuration with mandatory semicolons; co-locate shared helpers under `peachjam/js/utils`.

Don't use a leading underscore for protected or private method names on classes.

## Testing Guidelines
Prefer Django `TestCase` classes located in `<app>/tests.py`, loading fixtures from `<app>/fixtures/`. Cover caching-sensitive paths, exercise view logic with `self.client`, and patch `timezone.now` for time-dependent assertions.

Keep fixtures lean so `python manage.py test` completes quickly.

## Commit & Pull Request Guidelines
Use short, present-tense commit subjects (e.g., `simplify account page`); append tags like `[nodeploy]` only when required. Ensure migrations, fixtures, and translation catalogs remain in sync. Pull requests should explain intent, link issues, call out database or cache impacts, and include screenshots for UI changes. List the checks you ran to ease reviewer verification.

## Caching Guardrails
Cacheable views must omit session access, `Set-Cookie`, and inline CSRF tokens. Load personalised islands via htmx endpoints and rely on the caching sanity middleware to catch leaks—fix violations before merging.
