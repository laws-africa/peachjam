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

### Gazettes

Accounts with gazette API access can list gazettes at `/api/v1/gazettes`,
filtering by `updated_at__gte` for incremental imports and following the
pagination `next` link. Gazette records include publication, supplement, part,
volume, special status, and publication/robots settings alongside their existing
identifiers and dates.

To retrieve one gazette, append its full `expression_frbr_uri` to
`/api/v1/gazettes`. Append `/source.pdf` to that detail URL to download the
original PDF, if available. Both endpoints use the same gazette API permissions
as the listing. A gazette without a PDF returns HTTP 404 from the PDF endpoint.

POST `{"expression_frbr_uris": [...]}` to
`/api/v1/validate-gazette-expression-frbr-uris` to receive
`{"invalid_expression_frbr_uris": [...]}` listing identifiers absent from the
gazette collection. It requires gazette API access and does not change records.
The existing `/api/v1/validate-expression-frbr-uris` endpoint continues to validate
judgments.
