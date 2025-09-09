from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel

class RecurringDates(BaseModel):
    last_month: Optional[str] = None
    two_months_ago: Optional[str] = None
    three_months_ago: Optional[str] = None


class RecurringItem(BaseModel):
    key: str
    pattern: str
    description: Optional[str] = None
    payer: Optional[str] = None
    amount: Optional[str] = None
    currency: Optional[str] = None
    dates: RecurringDates


class RecurringResponse(BaseModel):
    count: int
    items: List[RecurringItem]