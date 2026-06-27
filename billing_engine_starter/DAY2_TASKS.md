# Day 2 — Storage: SQLite, Repositories, and the Invoice Pipeline

> **Goal by end of Day 2:** All tests in `test_repositories.py` and `test_pipeline.py` are green, and you are ready to implement `BillingCycle.run` on Day 3.

Today you connect yesterday's pure math to a real SQLite database. You will learn:
- Designing repository classes that hide SQL from business logic
- Writing parameterized SQL queries
- Storing `Money` as TEXT, not REAL
- Storing dates as ISO strings
- Using database constraints to protect billing logic
- Building a pure-function invoice pipeline

---

## Step 1 — Reconnect
Run `pytest -v`. You should still see all of Day 1 passing. Today's focus is:

- `tests/test_repositories.py`
- `tests/test_pipeline.py`

## Step 2 — Understand the schema
Open `billing_engine/db/schema.sql` and read it slowly.

For each table, answer for yourself:

1. What does it represent in the business?
2. What are its foreign keys?
3. What CHECK constraints exist?
4. What UNIQUE constraints exist?

Pay special attention to:

- `invoices.UNIQUE(subscription_id, period_start)`
- `ledger_entries` being append-only by convention
- money values being stored as text, not floats

## Step 3 — Read the database helper
Open `billing_engine/db/database.py` and understand:

1. `self.connect()` returns a fresh connection with foreign keys enabled.
2. `with db.transaction() as conn:` groups related writes atomically.

## Step 4 — Implement repositories
File: `billing_engine/db/repository.py`

Implement the repositories in this order:

1. `CustomerRepository`
2. `PlanRepository` and `PlanTierRepository`
3. `DiscountRepository`
4. `SubscriptionRepository`
5. `UsageRecordRepository`
6. `InvoiceRepository` and `InvoiceLineItemRepository`
7. `LedgerRepository`
8. `PaymentAttemptRepository` only if you finish early, otherwise leave it for Day 3

Useful reminders:

- Persist money using `to_storage()`.
- Read dates back with `date.fromisoformat(...)`.
- Let the invoice uniqueness constraint raise naturally.
- Keep SQL inside `db/repository.py` only.

**Checkpoint:** `pytest tests/test_repositories.py -v` should be green.

---

## Step 5 — Build the invoicing pipeline
File: `billing_engine/billing/pipeline.py`

This is a pure function. No DB access. No `datetime.now()`.

The flow is:

1. Compute base charge from the strategy.
2. Apply discount if present.
3. Compute taxable amount.
4. Apply tax.
5. Build line items.
6. Return a draft `Invoice`.

Run `pytest tests/test_pipeline.py -v`.

## Step 6 — Read `BillingCycle.run` for tomorrow
Open `billing_engine/billing/cycle.py` and read `BillingCycle.run` top to bottom.

Before leaving Day 2, make sure you can explain:

1. Where trial subscriptions get promoted to `ACTIVE`.
2. Where due subscriptions are loaded.
3. Where `build_invoice(...)` is called.
4. Which writes must happen in one transaction.
5. Why duplicate `(subscription_id, period_start)` inserts should be treated as skips.

You do not need to finish `BillingCycle.run` today unless you are ahead.

---

## End-of-Day Demo
In a Python REPL, verify you can persist and read back core data:

```python
from billing_engine.db.database import Database
from billing_engine.db.repository import CustomerRepository, PlanRepository
from billing_engine.models import BillingPeriod, Customer, Plan, PricingType

db = Database("/tmp/demo.db")
db.init_schema()

customers = CustomerRepository(db)
plans = PlanRepository(db)

cust = customers.add(Customer(None, "Aarav", "a@x.com", "IN", "MH"))
plan = plans.add(Plan(None, "Pro", PricingType.FLAT, BillingPeriod.MONTHLY, "INR"))

print(customers.get(cust.id))
print(plans.get(plan.id))
```

---

## Done-for-the-day checklist
- [ ] Repository methods are implemented
- [ ] `build_invoice` works as a pure function
- [ ] `pytest tests/test_repositories.py tests/test_pipeline.py -v` is green
- [ ] You understand the `BillingCycle.run` control flow before Day 3
- [ ] Code committed and pushed

## If you finish early
- Read `billing/cycle.py` and `tests/test_billing_cycle.py` for tomorrow.
- Implement `PaymentAttemptRepository` if you want a head start on Day 3 payment groundwork.

## If you fall behind
Skip in this order:

1. Leave `PaymentAttemptRepository` for Day 3.
2. Skip `count_for_subscription` if needed and wire it back later.
3. Do not rush `BillingCycle.run` tonight. Start it fresh on Day 3.
