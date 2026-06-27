"""Customer dataclass. ✅ COMPLETE."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Customer:
    id: Optional[int]           
    name: str
    email: str
    country_code: str         
    state_code: str = ""       
    created_at: Optional[datetime] = None
