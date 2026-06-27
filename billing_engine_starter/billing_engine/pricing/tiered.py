from dataclasses import dataclass
from typing import Optional

from billing_engine.money import Money
from billing_engine.pricing.base import PricingStrategy


@dataclass(frozen=True)
class Tier:
    from_units: int
    to_units: Optional[int]   
    unit_price: Money


class TieredPricing(PricingStrategy):

    def __init__(self, tiers: list[Tier]) -> None:
        if not tiers:
            raise ValueError("tiers cannot be empty")
        
        for i in range(len(tiers) - 1):
            if tiers[i + 1].from_units != tiers[i].to_units:
                raise ValueError("tiers must be contiguous")

        for i, tier in enumerate(tiers):
            if tier.to_units is None and i != len(tiers) - 1:
                raise ValueError("only last one/tier can be None")

        if tiers[-1].to_units is not None:
            raise ValueError("last one/tier must be None")

        currency = tiers[0].unit_price.currency
        for tier in tiers:
            if tier.unit_price.currency != currency:
                raise ValueError(" all tiers must use a same type of currency ")

        self.tiers = tiers


    def calculate(self, quantity: int) -> Money:
        if quantity < 0:
            raise ValueError(" Negative value of quantity not allowed ")

        currency = self.tiers[0].unit_price.currency
        total = Money.zero(currency)

        for tier in self.tiers:
            if tier.to_units is None:
                units_in_tier = max(0, quantity - tier.from_units)
                
            else:
                if quantity > tier.from_units:
                    units_in_tier = min(quantity, tier.to_units) - tier.from_units
                    
                else:
                    units_in_tier = 0

            total += tier.unit_price * units_in_tier

        return total