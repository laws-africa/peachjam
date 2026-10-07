# peachjam_subs

Subscription/catalog domain for Peachjam projects.

## Core Model Concepts

1. `Feature`
- A bundle of Django permissions that can be granted by a product.

2. `Product`
- A tiered subscription product (for example Free, Essentials, Pro).
- Includes feature membership and tier/limit configuration.
- `selectable_offerings` explicitly lists which offerings users can choose in UI flows.

3. `PricingPlan`
- A period/price definition (monthly or annually).

4. `ProductOffering`
- A concrete pairing of `Product` + `PricingPlan`.
- `can_subscribe` object permission controls whether a user may choose it.

5. `Subscription`
- A user’s access to one product offering over time.
- State machine: `pending -> active -> closed`.
- Supports scheduled starts/ends and optional trial transitions.

6. `SubscriptionSettings` (singleton)
- `default_product_offering`: assigned when users need a baseline subscription.
- `key_products`: products shown on pricing/listing pages.
- Trial settings (`trial_product_offering`, `trial_duration_days`).

## Selection and Visibility Rules

- Pricing/listing pages are driven by `SubscriptionSettings.key_products`.
- User-selectable offerings are explicit via `Product.selectable_offerings`.
- Actual access/availability is still permission-driven by `ProductOffering.can_subscribe`.
- `ProductOffering.product_offerings_available_to_user(user)` returns offerings:
  - the user can subscribe to,
  - that belong to products with selectable offerings configured,
  - excluding the user’s currently active non-trial offering.

## Catalog Validation Rules

`validate_selectable_offering_catalog(...)` enforces:

- At most one selectable offering per billing period per product.
- For each billing period, selectable prices increase with product tier.
- If a product has both monthly and annual selectable offerings:
  - for paid plans, annual price must be higher than monthly.
  - free `0/0` monthly+annual is allowed.
- Mixed catalogs are allowed (monthly-only products and annual-only products can coexist).
