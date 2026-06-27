"""
Proration — Day 4 stretch.

Mid-cycle plan change: customer is on Plan A from period_start to period_end,
but on `switch_date` they upgrade (or downgrade) to Plan B.

Day-count proration:
    total_days     = (period_end - period_start).days
    used_days      = (switch_date - period_start).days
    remaining_days = total_days - used_days

    credit = old_price * (remaining_days / total_days)
    charge = new_price * (remaining_days / total_days)

Tax MUST be recalculated on BOTH legs (reverse-tax on the credit,
fresh tax on the new charge). Tax is NOT prorated linearly — the tax
on a proration credit/charge is just `tax_calc.apply(credit_or_charge)`.

The two legs are returned as TAX-INCLUSIVE Money values for the
PRORATION_CREDIT (negative) and PRORATION_CHARGE (positive) line items.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from billing_engine.money import Money
from billing_engine.taxes.base import TaxCalculator, TaxContext


@dataclass(frozen=True)
class ProrationResult:
    credit_amount: Money   
    charge_amount: Money   
    credit_tax: Money       
    charge_tax: Money        


def _round_money(amount: Money) -> Money:
    """Round to 2 decimal places using banker's rounding (standard for money)."""
    rounded = amount.amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Money(rounded, amount.currency)


def compute_proration(
    old_plan_price: Money,
    new_plan_price: Money,
    period_start: date,
    period_end: date,
    switch_date: date,
    tax_calc: TaxCalculator,
    tax_context: TaxContext,
) -> ProrationResult:
   
    if not (period_start <= switch_date <= period_end):
        raise ValueError(
            f"switch_date {switch_date} outside period [{period_start}, {period_end}]"
        )

    if old_plan_price.currency != new_plan_price.currency:
        raise ValueError("Cannot prorate across currencies")

    total_days = (period_end - period_start).days
    if total_days <= 0:
        raise ValueError("Period must be positive")

    remaining_days = (period_end - switch_date).days
    ratio = Decimal(remaining_days) / Decimal(total_days)


    credit_amount = old_plan_price * ratio
    charge_amount = new_plan_price * ratio

  
    credit_amount = _round_money(credit_amount)
    charge_amount = _round_money(charge_amount)

   
    credit_tax = tax_calc.apply(credit_amount, tax_context).total
    charge_tax = tax_calc.apply(charge_amount, tax_context).total

   
    credit_tax = _round_money(credit_tax)
    charge_tax = _round_money(charge_tax)

    return ProrationResult(
        credit_amount=credit_amount,
        charge_amount=charge_amount,
        credit_tax=credit_tax,
        charge_tax=charge_tax,
    )