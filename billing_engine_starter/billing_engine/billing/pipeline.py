"""
Invoice building pipeline.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from billing_engine.models import (
    Invoice, InvoiceStatus, InvoiceLineItem, LineItemKind,
    Subscription,
)
from billing_engine.money import Money
from billing_engine.pricing.base import PricingStrategy
from billing_engine.discounts.base import Discount
from billing_engine.taxes.base import TaxCalculator, TaxContext


def build_invoice(
    subscription: Subscription,
    plan,
    strategy: PricingStrategy,
    discount: Optional[Discount],
    tax_calc: TaxCalculator,
    tax_context: TaxContext,
    period_start: date,
    period_end: date,
    usage_quantity: int = 0,
    invoice_count_so_far: int = 0,
) -> Invoice:
    """Build complete invoice with line items."""

    if usage_quantity > 0:
        base_amount = strategy.calculate(usage_quantity).rounded()
    else:
        base_amount = strategy.calculate(0).rounded()

  
    if discount:
        try:
            discount_total = discount.apply(base_amount, tax_context).rounded()
        except TypeError:
            discount_total = discount.apply(base_amount).rounded()

        discounted_amount = (base_amount - discount_total).rounded()
    else:
        discounted_amount = base_amount
        discount_total = Money.zero(base_amount.currency)


    tax_result = tax_calc.apply(discounted_amount, tax_context)
    tax_amount = tax_result.total.rounded()

   
    total_amount = (discounted_amount + tax_amount).rounded()

   
    invoice = Invoice(
        id=None,
        subscription_id=subscription.id,
        period_start=period_start,
        period_end=period_end,
        subtotal=base_amount,
        discount_total=discount_total,          
        tax_total=tax_amount,
        total=total_amount,
        status=InvoiceStatus.DRAFT,
        issued_at=period_end,
        pdf_path=None,
    )

    
    line_items = [
        InvoiceLineItem(None, None, "Base Charge", base_amount, LineItemKind.BASE)
    ]

    if discount and discount_total.amount > 0:
        line_items.append(
            InvoiceLineItem(None, None, "Discount", -discount_total, LineItemKind.DISCOUNT)
        )

    for comp in getattr(tax_result, 'components', []):
        if isinstance(comp, str):
            amount = tax_amount
            name = comp
        else:
            amount = getattr(comp, 'amount', comp)
            name = getattr(comp, 'name', 'Tax')
        line_items.append(
            InvoiceLineItem(None, None, name, amount, LineItemKind.TAX)
        )

    invoice.line_items = line_items
    return invoice