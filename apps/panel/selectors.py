"""Read-side queries for the panel app.

Selectors return querysets already scoped to what the requesting user may see
(deny by default) and use select_related/prefetch_related to avoid N+1 queries."""
