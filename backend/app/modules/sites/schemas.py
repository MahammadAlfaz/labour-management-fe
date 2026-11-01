from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class SiteStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    location: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=1000)
    start_date: date | None = None
    end_date: date | None = None
    contract_amount: Decimal | None = Field(default=None, ge=0)


class SiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    location: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=1000)
    start_date: date | None = None
    end_date: date | None = None
    contract_amount: Decimal | None = Field(default=None, ge=0)


class SiteOut(BaseModel):
    id: str
    name: str
    location: str
    description: str | None
    status: SiteStatus
    start_date: date | None
    end_date: date | None
    contract_amount: Decimal | None = None
    photo_url: str | None = None
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


class ClientReceiptCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    received_on: date
    note: str | None = Field(default=None, max_length=300)


class ClientReceiptOut(BaseModel):
    id: str
    site_id: str
    amount: Decimal
    received_on: date
    note: str | None
    created_by: str
    created_at: datetime


class SiteExpenseCategory(str, Enum):
    FOOD = "FOOD"
    OTHER = "OTHER"


class SiteExpenseCreate(BaseModel):
    category: SiteExpenseCategory
    amount: Decimal = Field(gt=0)
    expense_date: date
    note: str | None = Field(default=None, max_length=300)


class SiteExpenseOut(BaseModel):
    id: str
    site_id: str
    category: SiteExpenseCategory
    amount: Decimal
    expense_date: date
    note: str | None
    created_by: str
    created_at: datetime


class SiteFinancialSummary(BaseModel):
    site_id: str
    contract_amount: Decimal | None
    client_received: Decimal
    labour_cost: Decimal
    travel_expenses: Decimal
    site_expenses: Decimal
    total_cost: Decimal
    client_balance: Decimal | None = None
    current_profit: Decimal
    expected_profit: Decimal | None = None
    days_worked: int
