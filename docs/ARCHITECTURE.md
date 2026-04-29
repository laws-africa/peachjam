# Architecture

## Purpose

This repository is a reusable Django-based legal publishing platform. The shared platform is `peachjam`, and each deployed site layers a site-specific app and settings module on top of it.

At runtime, the project usually does **not** boot directly from `peachjam.settings`. Instead, entry points such as `manage.py`, `peachjam/asgi.py`, and `peachjam/wsgi.py` set `DJANGO_SETTINGS_MODULE` to a site shell like `africanlii.settings`.

## System shape

The system has four layers:

1. **Shared platform**: `peachjam`
2. **Supporting shared apps**: `peachjam_search`, `peachjam_api`, `peachjam_subs`, `peachjam_ml`
3. **Site shells**: `africanlii`, `liiweb`, `gazettes`, `open_by_laws`, and jurisdiction-specific apps such as `zambialii`, `malawilii`, `senlii`
4. **Frontend assets**: TypeScript/Vue/HTMX code under `peachjam/js`, bundled by webpack into `peachjam/static/js`

## Boot and request flow

### Backend boot

- `manage.py` starts Django admin/management commands.
- `peachjam/wsgi.py` exposes the WSGI app.
- `peachjam/asgi.py` exposes the ASGI app and defines a custom `DjangoUvicornWorker`.
- These entry points default to `africanlii.settings` in this checkout.

### Settings layering

- `peachjam/settings.py` is the base settings module for the platform.
- Site settings import from it and override:
  - `INSTALLED_APPS`
  - `ROOT_URLCONF`
  - `PEACHJAM[...]` feature flags
  - template context processors
  - middleware
  - sometimes language, branding, DB, or chat/search options

Examples:

- `africanlii.settings`: multi-jurisdiction search portal
- `liiweb.settings`: base shell used by some LII sites
- `gazettes.settings`: Gazettes.Africa-specific DB/middleware/CORS
- `open_by_laws.settings`: municipal by-laws deployment with microsite metadata
- `civlii.settings`, `senlii.settings`: add `peachjam_ml`

### URL composition

- `peachjam.urls` is the shared root URL tree.
- `peachjam.urls.i18n` holds most user-facing routes.
- `peachjam.urls.non_i18n` holds routes that must stay outside language prefixes, such as `/api/`, feeds, i18n helpers, robots, and offline/PWA endpoints.
- Site shells often prepend custom routes and then include `peachjam` URLs.

Examples:

- `africanlii.urls` adds African Union, taxonomy, and redirect routes before including `peachjam.urls`.
- `liiweb.urls.i18n` adds a legislation-focused home/navigation layer before including `peachjam.urls.i18n`.

## Main shared modules

### `peachjam`

This is the core product and domain app. It provides the common data model, views, admin integration, middleware, signals, ingestion hooks, and supporting utilities.

Primary responsibilities:

- Core legal document model hierarchy
- User-facing document/list/detail pages
- Admin tools and editorial workflows
- User accounts, profiles, permissions, and saved content
- Document ingestion and external adapter registration
- Caching, HTMX, and request middleware
- Email, timeline, and background task orchestration
- Shared templates, static assets, translations, and frontend bootstrap

Important subareas:

- `peachjam/models`
  - Main domain model surface.
  - Key groupings:
    - `core_document`, `legislation`, `judgment`, `generic_document`, `gazette`, `article`, `bill`, `journals_books`, `law_reports`, `arbitration`
    - `annotation`, `relationships`, `citations`, `flynote`, `enrichments`
    - `taxonomies`, `author`, `partner`, `entity_profile`, `custom_property`
    - `save_document`, `timeline`, `user_following`, `user_profile`, `document_access_group`
    - `ingestors`, `external_document`, `attachments`
    - `chat`
- `peachjam/views`
  - Main page and action handlers, split by content type and feature area.
  - Common classes of views:
    - listing/detail pages for legal content
    - account and auth flows
    - user features under `my/` and `user/`
    - admin utilities such as anonymisation/autocomplete
    - offline and widget endpoints
- `peachjam/urls`
  - Route modules grouped by feature or content family.
- `peachjam/adapters`
  - External import/integration adapters, registered on app startup.
  - Includes Indigo, judgments, gazettes, GitBook, ratifications.
- `peachjam/middleware.py`
  - Cross-cutting request behavior.
  - Includes cache sanity checks, cache variation for HTMX, redirect handling, preferred language, terms acceptance, and request/user ID headers.
- `peachjam/tasks.py`
  - Shared scheduled/background jobs such as ranking works, follow updates, and timeline email alerts.
- `peachjam/apps.py`
  - Startup hooks:
    - register adapters and signals
    - customize Jazzmin theme
    - patch country URLs
    - configure docpipe/LibreOffice execution limits
    - queue ingestor tasks and recurring jobs in non-debug mode
- `peachjam/auth.py`, `forms.py`, `permissions.py`, `decorators.py`
  - Authentication, allauth customization, permission helpers, and form layer.
- `peachjam/context_processors.py`, `translation.py`, `resources.py`, `feeds.py`, `storage.py`, `resolver.py`, `registry.py`
  - Shared support modules used across templates, admin, APIs, and content resolution.

### `peachjam_search`

Search and search analytics app built around Elasticsearch.

Primary responsibilities:

- Search UI and APIs
- Elasticsearch document/index registration
- Facets, suggestions, explains, and downloads
- Saved searches and search alerts
- Search click and trace logging
- Search feedback capture
- Query classification / ML-assisted search features

Important modules:

- `documents.py`: Elasticsearch document/index definitions
- `engine.py`: query construction and search execution
- `views/search.py`, `views/api.py`: UI and API handlers
- `models.py`: search traces, clicks, feedback, saved searches
- `classifier/`: query classification model support
- `tasks.py`: maintenance jobs such as pruning traces
- `apps.py`: registers indexes and enforces `peachjam_ml` presence when semantic search is enabled

### `peachjam_api`

REST API app using Django REST Framework.

Primary responsibilities:

- Internal APIs used by frontend components
- Public read-only API for external consumers
- API permissions and serializers
- OpenAPI schema and documentation endpoints
- Ingestor webhook endpoint

Important modules:

- `urls.py`: internal API, public API inclusion, schema routes
- `urls_public.py`: public API URL tree
- `views.py`, `public_views.py`: API viewsets and public endpoints
- `serializers.py`: API data contracts
- `permissions.py`: object/document access control for API consumers

### `peachjam_subs`

Subscription, product catalog, and entitlement app.

Primary responsibilities:

- Product/feature catalog
- Pricing plans and offerings
- Subscription lifecycle/state management
- Access entitlements tied to products
- Subscription-aware UI and checks
- Customer.io integration

Important model concepts:

- `Feature`: bundle of Django permissions
- `Product`: subscription tier and limits
- `PricingPlan`: billing period and price
- `ProductOffering`: concrete product + pricing plan pairing
- `Subscription`: user entitlement over time
- `SubscriptionSettings`: singleton controlling default/trial/key offerings

Important modules:

- `models.py`: catalog and subscription state
- `views.py`: subscribe/check/cancel flows
- `tasks.py`: scheduled subscription updates
- `mixins.py`: subscription-aware view helpers
- `customerio.py`: Customer.io integration

### `peachjam_ml`

Optional machine-learning extension app. It is not installed for every deployment.

Primary responsibilities:

- Semantic/hybrid search support
- Embeddings and vector-backed related-document features
- Similar documents views
- ML-driven augmentation of document detail pages

Important modules:

- `apps.py`
  - connects ML context modification into `BaseDocumentDetailView`
  - switches `PortionSearchEngine.mode` to `hybrid`
- `embeddings.py`, `models.py`, `tasks.py`: vector/embedding pipeline
- `views.py`, `urls.py`: similar-documents endpoints

## Site-shell modules

These apps customize the shared platform for specific deployments. They usually provide settings, templates, static files, translations, and sometimes views/routes/models.

### `africanlii`

Multi-jurisdiction portal shell.

Responsibilities:

- top-level site branding
- African Union and taxonomy browsing pages
- multi-jurisdiction search configuration
- redirect middleware and legacy URL handling

### `liiweb`

Reusable LII shell sitting between `peachjam` and specific country sites.

Responsibilities:

- common legislation-oriented homepage and navigation
- old LII URL redirects
- shared court/citation helpers
- base URL/settings pattern for some LII deployments

### Jurisdiction shells

Examples: `zambialii`, `malawilii`, `namiblii`, `seylii`, `senlii`, `civlii`.

Typical responsibilities:

- prepend one site app to `INSTALLED_APPS`
- set `ROOT_URLCONF` when needed
- override branding and language labels
- enable/disable features such as chat or ML
- add site-specific templates/static assets

### `gazettes`

Specialized deployment for Gazettes.Africa.

Responsibilities:

- own DB/default app settings
- custom middleware and context processor
- multi-jurisdiction gazette-focused behavior

### `open_by_laws`

Municipal by-laws deployment layered on `liiweb`.

Responsibilities:

- branding and microsite metadata
- single-language configuration
- extra context processor for by-law microsites

### `obl_microsites`

Supporting microsite app for Open By-laws deployments.

Responsibilities:

- microsite-specific templates/assets/routing customizations

## Frontend architecture

Frontend code lives under `peachjam/js` and is bundled by `webpack.config.js`.

Entry points:

- `peachjam/js/app.ts`: bootstraps the JS app and exposes `window.peachjam`
- `peachjam/js/peachjam.ts`: runtime coordinator

Frontend responsibilities:

- instantiate DOM-bound components from `data-component`
- mount Vue components from `data-vue-component`
- integrate HTMX lifecycle hooks
- initialize analytics and Sentry
- configure Bootstrap JS features
- manage saved-document UI and other interactive widgets

Key frontend patterns:

- `peachjam/js/components/index.ts` is the registration map for both data-components and Vue components.
- Server-rendered HTML remains the default; JS progressively enhances it.
- HTMX-inserted content is re-scanned so components must be safe to instantiate repeatedly.

## Cross-cutting platform concerns

### Caching

Caching is a first-class concern. The middleware stack includes:

- cache sanity checks
- update/fetch cache middleware
- HTMX header variation

Views and templates must avoid leaking user-specific state into cacheable responses.

### Background jobs

Background work is handled through `django-background-tasks-updated`.

Tasks are defined in `tasks.py` modules across the platform and supporting apps. They are queued on demand and sometimes
also scheduled to run at intervals.

Treat `tasks.py` as an entrypoint for background work. The task code short be short and focused on loading the state
necessary to run the task by delegating to business logic code elsewhere in the codebase. In particular, when running
a task related to a specific django object, the task should load the object by ID (handling the fact it may no longer
exist), and then delegate to a method on the object or a related service function.

Scheduled on app startup in non-debug mode:

- ingestion tasks from `peachjam`
- ranking and follow/timeline jobs from `peachjam.tasks`
- trace pruning from `peachjam_search.tasks`
- subscription reconciliation from `peachjam_subs.tasks`

### Search

Search is shared infrastructure, but site shells can alter:

- active indexes
- whether multiple jurisdictions/localities are supported
- whether suggestions or semantic search are enabled
- chat/ML features

### Authentication and permissions

- allauth provides account and social login flows
- guardian provides object permissions
- subscriptions layer on top of permissions for feature access
- APIs apply document-type and object-level access rules

### Ingestion and external systems

Notable integrations:

- `docpipe` for document processing
- Elasticsearch for search
- Customer.io for lifecycle/subscription messaging
- Sentry for error reporting
- Laws.Africa APIs via configuration in `PEACHJAM`
- optional OpenAI/agent and embedding stack through ML-related modules

## How to navigate the codebase

For common task types, start here:

- New page or view behavior: `peachjam/views`, then matching `peachjam/urls/*`, templates under `peachjam/templates` or site app templates
- Search changes: `peachjam_search/engine.py`, `peachjam_search/views/*`, `peachjam_search/documents.py`
- API changes: `peachjam_api/views.py`, `peachjam_api/public_views.py`, `peachjam_api/serializers.py`, `peachjam_api/urls*.py`
- Subscription/access changes: `peachjam_subs/models.py`, `peachjam_subs/views.py`, `peachjam_subs/mixins.py`
- Site-specific UI or routing: the active site app’s `settings.py`, `urls.py` or `urls/`, templates, and static files
- Interactive frontend changes: `peachjam/js/app.ts`, `peachjam/js/peachjam.ts`, `peachjam/js/components/index.ts`, then the specific component
- Data model changes: `peachjam/models/*` or the relevant supporting app’s models/migrations
- Startup behavior and scheduled jobs: `apps.py`, `signals.py`, `tasks.py`

## Mental model for future agents

When making changes, treat the repository as:

- one shared legal-publishing platform
- plus several optional capability apps
- plus multiple branded/site-specific shells

Before changing behavior, identify:

1. which settings module/site shell is active for the task
2. whether the change belongs in shared platform code or a site-specific overlay
3. whether the feature also touches search, API, subscriptions, ML, templates, or frontend component bootstrapping

That distinction is the main architectural boundary in this repo.
