# Peach Jam API

This Django application is the Peach Jam API. It has two components:

1. an internal API for use by frontend components
2. a public-facing API for external consumption.

## Public API

The public API is read-only. Users must authenticate and require a specific permission to access a particular
document type through the API.

Full documentation of the API is available in OpenAPI format from these endpoints:

* `/api/v1/schema`: in [OpenAPI](https://swagger.io/specification/) format
* `/api/v1/schema/redoc`: in [Redoc](https://github.com/Redocly/redoc) format
* `/api/v1/schema/swagger-ui`: in [Swagger UI](https://swagger.io/tools/swagger-ui/) format

### Authentication

Authenticate with an `Authorization: Token <token>` header that includes your authentication token.
