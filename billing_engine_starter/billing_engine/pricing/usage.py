"""
UsageBased — pay per unit consumed.

Example: ₹0.50 per API call. Customer makes 1200 calls => charge = ₹600.
"""

from billing_engine.money import Money
from billing_engine.pricing.base import PricingStrategy


class UsageBased(PricingStrategy):

    def __init__(self, unit_price: Money) -> None:
        if not isinstance(unit_price, Money):
            raise TypeError(" unit_price need to be a Money instance ")
        
        if unit_price.is_negative():
            raise ValueError(" value of unit_price not allowed ")
        
        self.unit_price = unit_price

    def calculate(self, quantity: int) -> Money:
        if quantity < 0:
            raise ValueError(" Negative value of quantity not allowed ")
        
        return self.unit_price * quantity
