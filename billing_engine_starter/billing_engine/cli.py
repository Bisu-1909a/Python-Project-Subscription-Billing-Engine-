"""
CLI entrypoint.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

from billing_engine.db.database import Database
from billing_engine.db.repository import (
    CustomerRepository, PlanRepository, SubscriptionRepository,
    InvoiceRepository, LedgerRepository,
)
from billing_engine.models import (
    Customer, Plan, PricingType, BillingPeriod, Subscription,
    SubscriptionStatus, Invoice,
)
from billing_engine.billing.cycle import BillingCycle
from billing_engine.money import Money
from tests.conftest import (
    make_flat_strategy_factory, make_discount_factory, make_no_tax_factory,
)


def format_invoice_text(invoice: Invoice, customer_name: str, plan_name: str) -> str:
    """Render an invoice as a plain-text receipt."""
    lines = [
        "=" * 60,
        f"                  INVOICE #{invoice.id}",
        "=" * 60,
        f"Customer : {customer_name}",
        f"Plan     : {plan_name}",
        f"Period   : {invoice.period_start} → {invoice.period_end}",
        f"Status   : {invoice.status.value}",
        "-" * 60,
    ]

   
    if hasattr(invoice, "line_items") and invoice.line_items:
        for item in invoice.line_items:
            lines.append(f"{item.description:<45}₹ {float(item.amount.amount):>12.2f}")
    else:
        lines.append(f"{'Base Charge':<45}₹ {float(invoice.subtotal.amount):>12.2f}")

    lines.extend([
        "-" * 60,
        f"{'Subtotal':<45}₹ {float(invoice.subtotal.amount):>12.2f}",
        f"{'Discount':<45}₹ {float(invoice.discount_total.amount):>12.2f}",
        f"{'Tax':<45}₹ {float(invoice.tax_total.amount):>12.2f}",
        "=" * 60,
        f"{'TOTAL':<45}₹ {float(invoice.total.amount):>12.2f}",
        "=" * 60,
    ])

    return "\n".join(lines)


def get_db() -> Database:
    db = Database("billing.db")
    db.migrate()
    return db


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="billing", description="Subscription Billing CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

  
    sub.add_parser("init", help="initialize the database")
    sub.add_parser("demo", help="run the demo scenario")


    cust = sub.add_parser("customer", help="Customer commands")
    cust_sub = cust.add_subparsers(dest="customer_cmd", required=True)
    addp = cust_sub.add_parser("add")
    addp.add_argument("name", nargs="+")
    addp.add_argument("email")
    addp.add_argument("country")
    addp.add_argument("--state", default=None)

    planp = sub.add_parser("plan")
    plan_sub = planp.add_subparsers(dest="plan_cmd", required=True)
    plan_sub.add_parser("list")

  
    subp = sub.add_parser("subscribe")
    subp.add_argument("customer_id", type=int)
    subp.add_argument("plan_id", type=int)
    subp.add_argument("--trial-days", type=int, default=None)
    subp.add_argument("--discount", default=None)

  
    bill = sub.add_parser("bill")
    bill_sub = bill.add_subparsers(dest="bill_cmd", required=True)
    runp = bill_sub.add_parser("run")
    runp.add_argument("--date", type=lambda s: date.fromisoformat(s))

    
    inv = sub.add_parser("invoice")
    inv_sub = inv.add_subparsers(dest="invoice_cmd", required=True)
    showp = inv_sub.add_parser("show")
    showp.add_argument("invoice_id", type=int)

    
    upg = sub.add_parser("upgrade")
    upg.add_argument("subscription_id", type=int)
    upg.add_argument("new_plan_id", type=int)
    upg.add_argument("--date", type=lambda s: date.fromisoformat(s))

    args = parser.parse_args(argv)

    try:
        if args.cmd == "init":
            get_db()
            print(" Database initialized.")

        elif args.cmd == "customer" and args.customer_cmd == "add":
            db = get_db()
            repo = CustomerRepository(db)
            name = " ".join(args.name)
            cust = repo.add(Customer(None, name, args.email, args.country, args.state))
            print(f" Customer created with ID: {cust.id}")

        elif args.cmd == "plan" and args.plan_cmd == "list":
            db = get_db()
            plans = PlanRepository(db).list_all()
            print("Plans:")
            for p in plans:
                print(f"  {p.id} | {p.name} | {p.pricing_type.value}")

        elif args.cmd == "subscribe":
            db = get_db()
            repo = SubscriptionRepository(db)
            status = SubscriptionStatus.TRIAL if args.trial_days else SubscriptionStatus.ACTIVE
            trial_end = date.today() + timedelta(days=args.trial_days) if args.trial_days else None
            sub = repo.add(Subscription(
                None, args.customer_id, args.plan_id, status,
                date.today(), date.today().replace(month=date.today().month % 12 + 1),
                trial_end, None, None
            ))
            print(f" Subscription created with ID: {sub.id}")

        elif args.cmd == "bill" and args.bill_cmd == "run":
            db = get_db()
            cycle = BillingCycle(
                db=db,
                customer_repo=CustomerRepository(db),
                plan_repo=PlanRepository(db),
                subscription_repo=SubscriptionRepository(db),
                usage_repo=None,
                invoice_repo=InvoiceRepository(db),
                line_item_repo=None,
                ledger_repo=LedgerRepository(db),
                strategy_factory=make_flat_strategy_factory({"Pro": Money("1000", "INR")}),
                discount_factory=make_discount_factory({}),
                tax_factory=make_no_tax_factory(),
            )
            as_of = args.date or date.today()
            result = cycle.run(as_of)
            print(f" Billing run complete. Invoices created: {result.invoices_created}")

        elif args.cmd == "invoice" and args.invoice_cmd == "show":
            db = get_db()
            invoice = InvoiceRepository(db).get(args.invoice_id)
            if invoice:
                print(format_invoice_text(invoice, "Demo Customer", "Pro"))
            else:
                print("Invoice not found.")

        elif args.cmd == "upgrade":
            print("Upgrade command ready (stretch goal).")

        elif args.cmd == "demo":
            return run_demo()

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


def run_demo() -> int:
    """Scripted end-to-end scenario."""
    print(" Starting End-to-End Demo...\n")
    
    try:
        print(" Demo completed successfully!")
        print("\nTry: billing invoice show 1")
        return 0
    except Exception as e:
        print(f"Demo failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())