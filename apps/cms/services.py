"""Business logic (write side) for the cms app.

Services are the only place allowed to change domain state: they validate
business rules, run inside transactions and record audit events."""
