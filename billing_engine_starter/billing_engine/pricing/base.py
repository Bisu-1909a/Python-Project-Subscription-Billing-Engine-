"""
Pricing strategy abstract base class.

✅ This ABC is COMPLETE. Subclasses go in sibling files.
"""

from abc import ABC, abstractmethod
from billing_engine_starter.billing_engine.money import Money


class PricingStrategy(ABC):
    
    @abstractmethod
    def calculate(self, quantity: int) -> Money:
        """Return the charge for the given usage quantity."""
        raise NotImplementedError
