"""
BillingCycle — finds due subscriptions, generates invoices, posts ledger DEBITs,
advances the subscription period. Must be IDEMPOTENT (safe to run twice).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

from billing_engine.db import (
    Database,
    CustomerRepository,
    PlanRepository,
    SubscriptionRepository,
    UsageRecordRepository,
    InvoiceRepository,
    InvoiceLineItemRepository,
    LedgerRepository,
)
from billing_engine.models import (
    Subscription,
    SubscriptionStatus,
    InvoiceStatus,
    LedgerDirection,
    LedgerEntry,
    Invoice,
    InvoiceLineItem,
    LineItemKind,
)
from billing_engine.billing.pipeline import build_invoice
from billing_engine.billing.proration import compute_proration
from billing_engine.billing.dunning import DunningProcess
from billing_engine.taxes.base import TaxContext


@dataclass
class BillingResult:
    invoices_created: int
    invoices_skipped_duplicate: int
    trials_activated: int


class BillingCycle:

    def __init__(
        self,
        db: Database,
        customer_repo: CustomerRepository,
        plan_repo: PlanRepository,
        subscription_repo: SubscriptionRepository,
        usage_repo: UsageRecordRepository,
        invoice_repo: InvoiceRepository,
        line_item_repo: InvoiceLineItemRepository,
        ledger_repo: LedgerRepository,
        strategy_factory: Callable,  
        discount_factory: Callable,    
        tax_factory: Callable,    
        gateway=None,                 
    ) -> None:
        self.db = db
        self.customer_repo = customer_repo
        self.plan_repo = plan_repo
        self.subscription_repo = subscription_repo
        self.usage_repo = usage_repo
        self.invoice_repo = invoice_repo
        self.line_item_repo = line_item_repo
        self.ledger_repo = ledger_repo
        self.strategy_factory = strategy_factory
        self.discount_factory = discount_factory
        self.tax_factory = tax_factory
        self.gateway = gateway

    def run(self, as_of: date) -> BillingResult:
        result = BillingResult(0, 0, 0)
        
        subscriptions = self.subscription_repo.list_all()

        for sub in subscriptions:
        
            if sub.status == SubscriptionStatus.TRIAL and sub.trial_end and sub.trial_end <= as_of:
                self.subscription_repo.update_status(sub.id, SubscriptionStatus.ACTIVE)
                result.trials_activated += 1

            # Skip invoicing if not due
            if sub.current_period_end > as_of:
                continue

          
            already_billed = self.invoice_repo.count_for_subscription(sub.id) > 0
            if already_billed:
                result.invoices_skipped_duplicate += 1
                continue

           
            customer = self.customer_repo.get(sub.customer_id)
            plan = self.plan_repo.get(sub.plan_id)
            
            pricing_strategy = self.strategy_factory(plan)
            base_amount = pricing_strategy.calculate([])  # No usage for simplicity in demo

            discount = self.discount_factory(getattr(sub, 'discount_id', None))
            discounted_amount = discount.apply(base_amount) if discount else base_amount
            discount_total = base_amount - discounted_amount if discount else type(base_amount)("0", base_amount.currency)

            tax_calc, tax_ctx = self.tax_factory(customer)
            tax_amount = tax_calc.apply(discounted_amount, tax_ctx).total

            total_amount = discounted_amount + tax_amount 

            
            invoice = Invoice(
                id=None,
                subscription_id=sub.id,
                period_start=sub.current_period_start,
                period_end=sub.current_period_end,
                subtotal=base_amount,
                discount_total=discount_total,
                tax_total=tax_amount,
                total=total_amount,
                status=InvoiceStatus.ISSUED,
                issued_at=as_of,
                pdf_path=None,
            )
            saved_invoice = self.invoice_repo.add(invoice)

            
            self.ledger_repo.add(
                LedgerEntry(
                    id=None,
                    customer_id=customer.id,
                    invoice_id=saved_invoice.id,
                    direction=LedgerDirection.DEBIT,
                    amount=total_amount,
                    reason=f"Invoice #{saved_invoice.id} for period ending {sub.current_period_end}",
                )
            )


            old_end = sub.current_period_end
            new_start = old_end
            month = old_end.month
            year = old_end.year
            if month == 12:
                new_month, new_year = 1, year + 1
            else:
                new_month, new_year = month + 1, year
            last_day = calendar.monthrange(new_year, new_month)[1]
            new_day = min(old_end.day, last_day)
            new_end = old_end.replace(year=new_year, month=new_month, day=new_day)

            self.subscription_repo.update_period(sub.id, new_start, new_end)

            result.invoices_created += 1

        return result

    def upgrade_subscription(
        self,
        subscription_id: int,
        new_plan_id: int,
        switch_date: Optional[date] = None,
    ) -> Invoice:
        
        if switch_date is None:
            switch_date = date.today()

        with self.db.transaction() as conn:
           
            sub = self.subscription_repo.get(subscription_id)
            if sub is None:
                raise ValueError(f"Subscription {subscription_id} not found")

            old_plan = self.plan_repo.get(sub.plan_id)
            new_plan = self.plan_repo.get(new_plan_id)
            if old_plan is None or new_plan is None:
                raise ValueError("One or both plans not found")

            customer = self.customer_repo.get(sub.customer_id)
            if customer is None:
                raise ValueError("Customer not found")

          
            old_strategy = self.strategy_factory(old_plan)
            new_strategy = self.strategy_factory(new_plan)
            
          
            old_price = old_strategy.monthly_price() if hasattr(old_strategy, 'monthly_price') else old_strategy.calculate([])
            new_price = new_strategy.monthly_price() if hasattr(new_strategy, 'monthly_price') else new_strategy.calculate([])

      
            pr = compute_proration(
                old_plan_price=old_price,
                new_plan_price=new_price,
                period_start=sub.current_period_start,
                period_end=sub.current_period_end,
                switch_date=switch_date,
                tax_calc=self.tax_factory(customer)[0],
                tax_context=self.tax_factory(customer)[1],
            )

            net_subtotal = pr.charge_amount - pr.credit_amount
            net_tax = pr.charge_tax - pr.credit_tax
            net_total = net_subtotal + net_tax

            currency = pr.charge_amount.currency

            invoice = self.invoice_repo.add(
                Invoice(
                    id=None,
                    subscription_id=subscription_id,
                    period_start=sub.current_period_start,
                    period_end=sub.current_period_end,
                    subtotal=net_subtotal,
                    discount_total=Money("0", currency),
                    tax_total=net_tax,
                    total=net_total,
                    status=InvoiceStatus.PAID,
                    issued_at=switch_date,
                    pdf_path=None,
                )
            )

            
            self.line_item_repo.add(
                InvoiceLineItem(
                    id=None,
                    invoice_id=invoice.id,
                    description=f"Proration credit — switching from {old_plan.name}",
                    amount=-pr.credit_amount,          # negative = credit
                    kind=LineItemKind.PRORATION_CREDIT,
                )
            )

            self.line_item_repo.add(
                InvoiceLineItem(
                    id=None,
                    invoice_id=invoice.id,
                    description=f"Proration charge — switching to {new_plan.name}",
                    amount=pr.charge_amount,
                    kind=LineItemKind.PRORATION_CHARGE,
                )
            )

           
            self.ledger_repo.add(
                LedgerEntry(
                    id=None,
                    customer_id=customer.id,
                    invoice_id=invoice.id,
                    direction=LedgerDirection.DEBIT,
                    amount=net_total,
                    reason=f"Mid-cycle upgrade from plan {sub.plan_id} to {new_plan_id}",
                )
            )

            self.subscription_repo.update_plan(subscription_id, new_plan_id)

            return invoice