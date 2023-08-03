# Peach Jam API

This Django application is the Peach Jam API. It has two components:

1. an internal API for use by frontend components
2. a public-facing API for external consumption.

## Public API

The public API is read-only. Users must authenticate and require a specific permission to access a particular
document type through the API.

### Authentication

Authenticate with an `Authorization: Token <token>` header that includes your authentication token.

### Endpoints - Judgments

#### `GET /api/v1/judgments/`

* Gets a list of judgments

#### `GET /api/v1/judgments/<id>`

* Get details on a particular judgment

#### `GET /api/v1/judgments/<id>/source.txt`

* Gets the source text of the judgment, if available

#### `GET /api/v1/judgments/<id>/source.pdf`

* Gets the source PDF of the judgment, if available

### Endpoints - Gazettes

#### `GET /api/v1/judgments/`

* Gets a list of gazettes

#### `GET /api/v1/gazettes/<id>`

* Get details on a particular gazette

#### `GET /api/v1/gazettes/<id>/source.txt`

* Gets the source text of the gazette, if available

#### `GET /api/v1/gazettes/<id>/source.pdf`

* Gets the source PDF of the gazette, if available
