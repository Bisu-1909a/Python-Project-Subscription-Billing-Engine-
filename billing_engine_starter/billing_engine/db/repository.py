"""
Repositories — the ONLY place SQL lives.

Each repository wraps the Database connection and exposes methods that
take/return domain dataclasses (defined in billing_engine/models/).

⚠️ YOU IMPLEMENT every method body marked TODO.
   The signatures, docstrings, and the LedgerRepository's append-only
   guarantee are already in place — do not change them.

Beginner map (Day 2):
  1) CustomerRepository: add, get, find_by_email, list_all
  2) PlanRepository: add, get, list_all
  3) PlanTierRepository: add, list_for_plan
  4) DiscountRepository: add, get_by_code
  5) SubscriptionRepository: add, get, list_all, get_due_for_billing
  6) UsageRecordRepository: add, sum_for_period
  7) InvoiceRepository: add, get
  8) InvoiceLineItemRepository: add, list_for_invoice

Skip on Day 2 (read-only for now):
  - SubscriptionRepository.update_period / update_status / update_plan
  - InvoiceRepository.count_for_subscription / mark_paid / mark_failed / set_pdf_path
  - LedgerRepository and PaymentAttemptRepository

Conventions:
  - Always use parameterized queries (`?` placeholders) — NEVER f-string SQL.
  - Money values are persisted as TEXT using `money.to_storage()`.
  - Dates are persisted as ISO strings (`date.isoformat()`).

New layering (beginner-friendly):
  - Raw SQL lives in `billing_engine/db/queries.py`.
  - Repository methods call those query helpers.
  - Your Day 2 focus is:
      1) Convert domain -> storage values before helper call
      2) Convert rows -> domain dataclasses after helper call
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from billing_engine.db.database import Database
from billing_engine.db import queries as q
from billing_engine.money import Money
from billing_engine.models import (
    Customer,
    Plan, PricingType, BillingPeriod,
    Subscription, SubscriptionStatus,
    Invoice, InvoiceStatus, InvoiceLineItem, LineItemKind,
    LedgerEntry, LedgerDirection,
)


# ============================================================
# CUSTOMERS
# ============================================================
# Day 2: start here.
class CustomerRepository:
    """Persistence boundary for customers.

    A Customer is the billing account owner: invoices, subscriptions, and
    ledger entries ultimately belong to a customer. This repository hides the
    `customers` table and returns Customer dataclasses so the rest of the app
    does not need to know SQL column names.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, customer : Customer) -> Customer:
        
        with self.db.transaction() as conn:
            customer_id = q.insert_customer(
            conn,
            customer.name,
            customer.email,
            customer.country_code,
            customer.state_code,
        )

        return Customer(
        id=customer_id,
        name=customer.name,
        email=customer.email,
        country_code=customer.country_code,
        state_code=customer.state_code,
    )

    def get(self, customer_id: int) -> Optional[Customer]:
        
        with self.db.connect() as conn:
            row = q.select_customer_by_id(conn, customer_id)

        if row is None:
            return None

        return Customer(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            country_code=row["country_code"],
            state_code=row["state_code"],
        )

    def find_by_email(self, email: str) -> Optional[Customer]:
        
        with self.db.connect() as conn:
             row = q.select_customer_by_email(conn, email)

        if row is None:
            return None

        return Customer(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            country_code=row["country_code"],
            state_code=row["state_code"],
        )

    def list_all(self) -> list[Customer]:
        with self.db.connect() as conn:
            rows = q.select_all_customers(conn)

        customers = []

        for row in rows :
            customer = Customer(
                id=row["id"],
                name=row["name"],
                email=row["email"],
                country_code=row["country_code"],
                state_code=row["state_code"],
            )
            customers.append(customer)
     
        return customers


# ============================================================
# PLANS  +  PLAN TIERS
# ============================================================
# Day 2
class PlanRepository:
    """Persistence boundary for subscription plans.

    A Plan describes what the customer bought: pricing type, billing period,
    currency, and strategy configuration. Pricing code consumes Plan objects,
    while this repository handles the `plans` table representation.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, plan: Plan) -> Plan:
        with self.db.transaction() as conn:
            plan_id = q.insert_plan(
            conn,
            plan.name,
            plan.pricing_type.value,
            plan.billing_period.value,
            plan.currency,
            plan.config_json,
        )

        return Plan(
        id=plan_id,
        name=plan.name,
        pricing_type=plan.pricing_type,
        billing_period=plan.billing_period,
        currency=plan.currency,
        config_json=plan.config_json,
    )

    def get(self, plan_id: int) -> Optional[Plan]:
        with self.db.connect() as conn:
            row = q.select_plan_by_id(conn, plan_id)

        if row is None:
            return None

        return Plan(
        id=row["id"],
        name=row["name"],
        pricing_type=PricingType(row["pricing_type"]),
        billing_period=BillingPeriod(row["billing_period"]),
        currency=row["currency"],
        config_json=row["config_json"],
    )

    def list_all(self) -> list[Plan]:
        with self.db.connect() as conn:
            rows = q.select_all_plans(conn)

        plans = []

        for row in rows:
            plan = Plan(
            id=row["id"],
            name=row["name"],
            pricing_type=PricingType(row["pricing_type"]),
            billing_period=BillingPeriod(row["billing_period"]),
                currency=row["currency"],
                config_json=row["config_json"],
        )
            plans.append(plan)

        return plans


class PlanTierRepository:
    """Persistence boundary for pricing tiers attached to a plan.

    Tiered and usage-based plans need rows such as "0-100 units at 1.00" and
    "101+ units at 0.75". These rows live separately from plans because one
    plan can have many tiers.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    def add(
    self,
    plan_id: int,
    from_units: int,
    to_units: Optional[int],
    unit_price: Money,
) -> int:
        with self.db.transaction() as conn:
            tier_id = q.insert_plan_tier(
                conn,
                plan_id,
                from_units,
                to_units,
                unit_price.to_storage(),
            )

        return tier_id

    def list_for_plan(
    self,
    plan_id: int,
    currency: str,
) -> list[tuple[int, Optional[int], Money]]:
        with self.db.connect() as conn:
            rows = q.select_plan_tiers(conn, plan_id)

        tiers = []

        for row in rows:
           tiers.append(
            (
                row["from_units"],
                row["to_units"],
                Money(
                    row["unit_price"],
                    currency,
                ),
            )
        )

        return tiers


# ============================================================
# DISCOUNTS
# ============================================================
# Day 2
class DiscountRepository:
    """Persistence boundary for discount definitions.

    Discounts are stored as flexible rows because different discount types need
    different interpretation: percentage, fixed amount, or first-month-free.
    This repository intentionally returns dictionaries instead of a dataclass.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, code: str, discount_type: str, value: str, currency: Optional[str] = None) -> int:
        with self.db.transaction() as conn:
            discount_id = q.insert_discount(
                conn,
                code,
                discount_type,
                value,
                currency,
        )

        return discount_id

    def get_by_code(self, code: str) -> Optional[dict]:
        with self.db.connect() as conn:
            row = q.select_discount_by_code(conn, code)

        if row is None:
            return None

        return dict(row)


# ============================================================
# SUBSCRIPTIONS
# ============================================================
# Day 2 (only add/get/list_all/get_due_for_billing)
class SubscriptionRepository:
    """Persistence boundary for customer subscriptions.

    A Subscription connects a customer to a plan and tracks lifecycle state:
    TRIAL, ACTIVE, PAST_DUE, or CANCELLED. It also stores the current billing
    period, trial end date, optional discount, and dunning state.
    """

    def __init__(self, db: Database) -> None:
        self.db = db
        
    def _row_to_subscription(self, row) -> Subscription:
        return Subscription(
            id=row["id"],
            customer_id=row["customer_id"],
            plan_id=row["plan_id"],
            status=SubscriptionStatus(row["status"]),
        
            current_period_start=date.fromisoformat(
                row["current_period_start"]
            ),
        
            current_period_end=date.fromisoformat(
                row["current_period_end"]
            ),
        
            trial_end=date.fromisoformat(
                row["trial_end"]
            ) if row["trial_end"] 
              else None,
          
            discount_id=row["discount_id"],
        
            past_due_since=date.fromisoformat(
                row["past_due_since"]
            ) if row["past_due_since"] 
              else None,
        )

    def add(self, subscription: Subscription) -> Subscription:
        with self.db.transaction() as conn:
            subscription_id = q.insert_subscription(
                conn,
                subscription.customer_id,
                subscription.plan_id,
                subscription.status.value,
                subscription.current_period_start.isoformat(),
                subscription.current_period_end.isoformat(),
                subscription.trial_end.isoformat()
                    if subscription.trial_end
                    else None,
                subscription.discount_id,
                subscription.past_due_since.isoformat()
                    if subscription.past_due_since
                    else None,
            )

        return Subscription(
            id=subscription_id,
            customer_id=subscription.customer_id,
            plan_id=subscription.plan_id,
            status=subscription.status,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            trial_end=subscription.trial_end,
            discount_id=subscription.discount_id,
            past_due_since=subscription.past_due_since,
        )

    def get(self, subscription_id: int) -> Optional[Subscription]:
        with self.db.connect() as conn:
            row = q.select_subscription_by_id(
                conn,
                subscription_id,
            )
        
        if row is None:
            return None
        return self._row_to_subscription(row)

    def list_all(self) -> list[Subscription]:
        with self.db.connect() as conn:
            rows = q.select_all_subscriptions(conn)
         
        return [
            self._row_to_subscription(row)
            for row in rows
        ]

    def get_due_for_billing(self, as_of: date) -> list[Subscription]:
        with self.db.connect() as conn:
            rows = q.select_due_subscriptions(
                conn,
                as_of.isoformat(),
            )

        return [
               self._row_to_subscription(row)
               for row in rows
            ]

    # ------------------------------------------------------------------
    # Day 2 boundary:
    # Everything below this line in this class is intentionally deferred.
    # Keep the method stubs so Day 3/4 can build on the same API surface.
    # ------------------------------------------------------------------
    def update_period(self, subscription_id: int, new_start: date, new_end: date) -> None:
        with self.db.transaction() as conn:
            conn.execute(
            """
            UPDATE subscriptions
            SET current_period_start = ?, current_period_end = ?
            WHERE id = ?
            """,
            (
                new_start.isoformat(),
                new_end.isoformat(),
                subscription_id,
            ),
        )

    def update_status(
        self,
        subscription_id: int,
        new_status: SubscriptionStatus,
        past_due_since: Optional[date] = None,
    ) -> None:
        with self.db.transaction() as conn:
            conn.execute(
            """
            UPDATE subscriptions
            SET status = ?, past_due_since = ?
            WHERE id = ?
            """,
            (
                new_status.value,
                past_due_since.isoformat() if past_due_since else None,
                subscription_id,
            ),
        )

    def update_plan(self, subscription_id: int, new_plan_id: int) -> None:
        with self.db.transaction() as conn:
            q.update_subscription_plan(
                conn, 
                subscription_id, 
                new_plan_id
            )


# ============================================================
# USAGE
# ============================================================
# Day 2
class UsageRecordRepository:
    """Persistence boundary for metered usage.

    Usage records store quantities such as API calls, seats, messages, or GBs.
    Usage-based pricing strategies ask this repository for the total quantity
    they should charge for a subscription.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, subscription_id: int, metric: str, quantity: int) -> int:
        with self.db.transaction() as conn:
            record_id = q.insert_usage_record(
                conn,
                subscription_id,
                metric,
                quantity,
            )

        return record_id

    def sum_for_period(
        self, subscription_id: int, metric: str, period_start: date, period_end: date
    ) -> int:
        with self.db.connect() as conn:
            return q.sum_usage_for_subscription_metric(
                conn,
                subscription_id,
                metric,
            )


# ============================================================
# INVOICES + LINE ITEMS
# ============================================================
# Day 2 (InvoiceRepository only add/get)
class InvoiceRepository:
    """Persistence boundary for invoice headers.

    An Invoice stores the totals for one subscription period: subtotal,
    discounts, tax, final total, status, issue time, and optional PDF path.
    Line items are stored separately by InvoiceLineItemRepository.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, invoice: Invoice) -> Invoice:
        with self.db.transaction() as conn:
            invoice_id = q.insert_invoice(
                conn,
                invoice.subscription_id,
                invoice.period_start.isoformat(),
                invoice.period_end.isoformat(),
                invoice.total.currency,
                invoice.subtotal.to_storage(),
                invoice.discount_total.to_storage(),
                invoice.tax_total.to_storage(),
                invoice.total.to_storage(),
                invoice.status.value,
                invoice.issued_at.isoformat() if invoice.issued_at else None,
                invoice.pdf_path,
        )

        return Invoice(
            id=invoice_id,
            subscription_id=invoice.subscription_id,
            period_start=invoice.period_start,
            period_end=invoice.period_end,
            subtotal=invoice.subtotal,
            discount_total=invoice.discount_total,
            tax_total=invoice.tax_total,
            total=invoice.total,
            status=invoice.status,
            issued_at=invoice.issued_at,
            pdf_path=invoice.pdf_path,
        )
        

    def get(self, invoice_id: int) -> Optional[Invoice]:
        with self.db.connect() as conn:
            row = q.select_invoice_by_id(conn, invoice_id)
            
        if row is None:
            return None
        
        currency = row["currency"]
        
        return Invoice(
    id=row["id"],
    subscription_id=row["subscription_id"],
    period_start=date.fromisoformat(row["period_start"]),
    period_end=date.fromisoformat(row["period_end"]),
    
    subtotal=Money(
        row["subtotal"],
        currency,
    ),
    
    discount_total=Money(
        row["discount_total"],
        currency,
    ),
    
    tax_total=Money(
        row["tax_total"],
        currency,
    ),
    
    total=Money(
        row["total"],
        currency,
    ),
    
    status=InvoiceStatus(row["status"]),
    
    issued_at=(
        date.fromisoformat(row["issued_at"])
        if row["issued_at"]
        else None
    ),
    
    pdf_path=row["pdf_path"],
)

    def count_for_subscription(self, subscription_id: int) -> int:
        with self.db.connect() as conn:
           row = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM invoices
            WHERE subscription_id = ?
            """,
            (subscription_id,),
        ).fetchone()

        return int(row["count"])

    def mark_paid(self, invoice_id: int) -> None:
       with self.db.transaction() as conn:
            q.update_invoice_status(conn, invoice_id, "PAID")

    def mark_failed(self, invoice_id: int) -> None:
        """Mark invoice as FAILED (used when dunning gives up)."""
        with self.db.transaction() as conn:
            q.update_invoice_status(conn, invoice_id, "FAILED")

    def set_pdf_path(self, invoice_id: int, path: str) -> None:
        with self.db.transaction() as conn:
            q.update_invoice_pdf_path(conn, invoice_id, path)


class InvoiceLineItemRepository:

    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, line_item: InvoiceLineItem) -> InvoiceLineItem:
        with self.db.transaction() as conn:
            line_item_id = q.insert_invoice_line_item(
                conn,
                line_item.invoice_id,
                line_item.description,
                line_item.amount.to_storage(),
                line_item.kind.value,
        )

        return InvoiceLineItem(
            id=line_item_id,
            invoice_id=line_item.invoice_id,
            description=line_item.description,
            amount=line_item.amount,
            kind=line_item.kind,
        )

    def list_for_invoice(
    self,
    invoice_id: int,
) -> list[InvoiceLineItem]:
     invoice = InvoiceRepository(self.db).get(invoice_id)

     if invoice is None:
        return []

     currency = invoice.total.currency

     with self.db.connect() as conn:
        rows = q.select_line_items_for_invoice(
            conn,
            invoice_id,
        )

     line_items = []

     for row in rows:
        line_items.append(
            InvoiceLineItem(
                id=row["id"],
                invoice_id=row["invoice_id"],
                description=row["description"],
                amount=Money(
                    row["amount"],
                    currency,
                ),
                kind=LineItemKind(
                    row["kind"]
                ),
            )
        )

     return line_items


# ============================================================
# DAY 3/4 ONLY — keep stubs for later
# ============================================================
# ============================================================
# LEDGER — APPEND-ONLY (do not implement update/delete)
# ============================================================

class LedgerRepository:

    def __init__(self, db: Database) -> None:
        self.db = db

    def add(self, entry: LedgerEntry) -> LedgerEntry:
        with self.db.transaction() as conn:
            cur = conn.execute(
            """
            INSERT INTO ledger_entries
            (
                customer_id,
                invoice_id,
                direction,
                amount,
                currency,
                reason
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entry.customer_id,
                entry.invoice_id,
                entry.direction.value,
                entry.amount.to_storage(),
                entry.amount.currency,
                entry.reason,
            ),
        )

        new_id = int(cur.lastrowid)

        return LedgerEntry(
        id=new_id,
        customer_id=entry.customer_id,
        invoice_id=entry.invoice_id,
        direction=entry.direction,
        amount=entry.amount,
        reason=entry.reason,
    )

    def list_for_customer(self, customer_id: int) -> list[LedgerEntry]:
        with self.db.connect() as conn:
            rows = conn.execute(
            """
            SELECT *
            FROM ledger_entries
            WHERE customer_id = ?
            ORDER BY created_at, id
            """,
            (customer_id,),
        ).fetchall()

        result = []

        for row in rows:
            result.append(
                LedgerEntry(
                id=row["id"],
                customer_id=row["customer_id"],
                invoice_id=row["invoice_id"],
                direction=LedgerDirection(row["direction"]),
                amount=Money(row["amount"], row["currency"]),
                reason=row["reason"],
            )
        )

        return result

    def update(self, *args, **kwargs):
        raise NotImplementedError("Ledger is append-only. Post a reversing entry instead.")

    def delete(self, *args, **kwargs):
        raise NotImplementedError("Ledger is append-only. Post a reversing entry instead.")


# ============================================================
# PAYMENT ATTEMPTS
# ============================================================
class PaymentAttemptRepository:
    """Persistence boundary for payment retry history.

    Each payment attempt records whether charging an invoice succeeded or
    failed, why it failed, and when the next retry should happen. This history
    powers the Day 3/4 dunning flow.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    def add(
        self,
        invoice_id: int,
        attempt_no: int,
        status: str,
        failure_reason: Optional[str],
        next_retry_at: Optional[datetime],
    ) -> int:
        with self.db.transaction() as conn:
            return q.insert_payment_attempt(
                conn,
                invoice_id,
                attempt_no,
                status,
                failure_reason,
                next_retry_at.isoformat() if next_retry_at else None,
            )

    def list_for_invoice(self, invoice_id: int) -> list[dict]:
        with self.db.connect() as conn:
            rows = q.select_attempts_for_invoice(conn, invoice_id)
        return [dict(row) for row in rows]

    def count_for_invoice(self, invoice_id: int) -> int:
        with self.db.connect() as conn:
            # The query helper already returns the integer count directly
            count = q.count_attempts_for_invoice(conn, invoice_id)
            return int(count) if count is not None else 0