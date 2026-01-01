from pydantic import BaseModel
from datetime import date
from decimal import Decimal
from typing import Optional, List


# ===== Person Schemas =====

class PersonCreate(BaseModel):
    name: str
    is_primary: bool = False
    pps_number: Optional[str] = None
    color: str = "#3B82F6"


class PersonUpdate(BaseModel):
    name: Optional[str] = None
    pps_number: Optional[str] = None
    color: Optional[str] = None


class PersonResponse(BaseModel):
    id: int
    name: str
    is_primary: bool
    pps_number: Optional[str] = None
    color: str

    class Config:
        from_attributes = True


# ===== Transaction Schemas =====

class TransactionCreate(BaseModel):
    isin: str
    name: str
    transaction_type: str
    transaction_date: date
    quantity: Decimal
    unit_price: Decimal
    fees: Decimal = Decimal("0")
    person_id: Optional[int] = None  # For family tax returns


class TransactionResponse(BaseModel):
    id: int
    isin: str
    name: str
    transaction_type: str
    transaction_date: date
    quantity: Decimal
    unit_price: Decimal
    gross_amount: Decimal
    fees: Decimal
    net_amount: Decimal
    realized_gain_loss: Optional[Decimal] = None
    person_id: Optional[int] = None
    person_name: Optional[str] = None

    class Config:
        from_attributes = True


class HoldingResponse(BaseModel):
    isin: str
    name: str
    asset_type: str
    quantity: Decimal
    average_cost: Decimal
    total_cost_basis: Decimal
    current_price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    unrealized_gain_loss: Optional[Decimal] = None
    next_deemed_disposal: Optional[date] = None
    person_id: Optional[int] = None
    person_name: Optional[str] = None


class TaxSummaryResponse(BaseModel):
    tax_year: int

    # CGT
    cgt_gains: Decimal
    cgt_losses: Decimal
    cgt_exemption_used: Decimal
    cgt_taxable: Decimal
    cgt_tax_due: Decimal

    # Exit Tax
    exit_tax_gains: Decimal
    exit_tax_due: Decimal

    # DIRT
    interest_income: Decimal
    dirt_due: Decimal

    # Dividends
    dividend_income: Decimal
    dividend_withholding_credit: Decimal

    # Total
    total_tax_due: Decimal


class PaymentDeadlineResponse(BaseModel):
    description: str
    due_date: date
    amount: Decimal
    tax_type: str


class UploadResponse(BaseModel):
    success: bool
    message: str
    transactions_imported: int
    income_events_imported: int
    tax_year: int
