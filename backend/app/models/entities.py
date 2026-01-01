"""Database entity models for Irish Tax Calculator."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Numeric,
    ForeignKey, Enum as SQLEnum, Boolean, Text
)
from sqlalchemy.orm import relationship
from .database import Base


class AssetType(str, Enum):
    """Asset type classification for Irish tax purposes."""
    STOCK = "stock"           # CGT 33%
    ETF_EU = "etf_eu"         # Exit Tax 41% (IE, LU, DE domiciled)
    ETF_NON_EU = "etf_non_eu" # CGT 33% (US domiciled ETFs)
    FUND = "fund"             # Exit Tax 41%
    BOND = "bond"             # CGT 33%
    CASH = "cash"             # DIRT 33%


class TransactionType(str, Enum):
    """Transaction types."""
    BUY = "buy"
    SELL = "sell"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    DISTRIBUTION = "distribution"
    CORPORATE_ACTION = "corporate_action"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class Person(Base):
    """Person entity for family/joint tax returns."""
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    is_primary = Column(Boolean, default=False)  # Primary taxpayer vs spouse
    pps_number = Column(String(20))  # Optional PPS number
    color = Column(String(7), default="#3B82F6")  # UI color for distinction

    # Relationships
    transactions = relationship("Transaction", back_populates="person")
    tax_lots = relationship("TaxLot", back_populates="person")
    holdings = relationship("Holding", back_populates="person")
    income_events = relationship("IncomeEvent", back_populates="person")
    tax_reports = relationship("TaxReport", back_populates="person")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Asset(Base):
    """Asset master data."""
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    isin = Column(String(12), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    asset_type = Column(SQLEnum(AssetType), nullable=False)
    country = Column(String(100))  # Country of domicile
    currency = Column(String(3), default="EUR")

    # For deemed disposal tracking (Exit Tax)
    is_eu_fund = Column(Boolean, default=False)

    # Relationships
    transactions = relationship("Transaction", back_populates="asset")
    holdings = relationship("Holding", back_populates="asset")
    tax_lots = relationship("TaxLot", back_populates="asset")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Transaction(Base):
    """Individual transaction record."""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True)  # For family tax returns

    transaction_type = Column(SQLEnum(TransactionType), nullable=False)
    transaction_date = Column(Date, nullable=False, index=True)
    settlement_date = Column(Date)

    # Quantities and prices
    quantity = Column(Numeric(18, 8), nullable=False)  # Support fractional shares
    unit_price = Column(Numeric(18, 6), nullable=False)
    gross_amount = Column(Numeric(18, 2), nullable=False)
    fees = Column(Numeric(18, 2), default=0)
    net_amount = Column(Numeric(18, 2), nullable=False)

    # Currency info
    currency = Column(String(3), default="EUR")
    exchange_rate = Column(Numeric(18, 6), default=1.0)
    amount_eur = Column(Numeric(18, 2))  # Amount in EUR

    # For CGT calculations
    realized_gain_loss = Column(Numeric(18, 2))  # Calculated by tax engine
    cost_basis_used = Column(Numeric(18, 2))     # Cost basis consumed

    # Metadata from Trade Republic
    external_id = Column(String(100))  # TR transaction reference
    notes = Column(Text)

    # Relationships
    asset = relationship("Asset", back_populates="transactions")
    person = relationship("Person", back_populates="transactions")

    created_at = Column(DateTime, default=datetime.utcnow)


class TaxLot(Base):
    """
    Tax lot for tracking cost basis.
    Implements Irish CGT matching rules:
    1. Same-day acquisitions
    2. Acquisitions within next 4 weeks (bed & breakfast)
    3. FIFO for remaining
    """
    __tablename__ = "tax_lots"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True)  # For family tax returns

    acquisition_date = Column(Date, nullable=False, index=True)
    quantity = Column(Numeric(18, 8), nullable=False)
    remaining_quantity = Column(Numeric(18, 8), nullable=False)
    unit_cost = Column(Numeric(18, 6), nullable=False)
    total_cost = Column(Numeric(18, 2), nullable=False)

    # For Exit Tax deemed disposal
    deemed_disposal_date = Column(Date)  # 8 years from acquisition
    deemed_disposal_processed = Column(Boolean, default=False)

    # Link to original buy transaction
    buy_transaction_id = Column(Integer, ForeignKey("transactions.id"))

    asset = relationship("Asset", back_populates="tax_lots")
    person = relationship("Person", back_populates="tax_lots")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Holding(Base):
    """Current holdings summary per asset per person."""
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True)  # For family tax returns

    quantity = Column(Numeric(18, 8), nullable=False, default=0)
    average_cost = Column(Numeric(18, 6))
    total_cost_basis = Column(Numeric(18, 2))

    # Current market value (updated separately)
    current_price = Column(Numeric(18, 6))
    market_value = Column(Numeric(18, 2))
    unrealized_gain_loss = Column(Numeric(18, 2))

    # For Exit Tax tracking
    earliest_acquisition_date = Column(Date)
    next_deemed_disposal_date = Column(Date)

    asset = relationship("Asset", back_populates="holdings")
    person = relationship("Person", back_populates="holdings")

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IncomeEvent(Base):
    """Income events (interest, dividends, distributions)."""
    __tablename__ = "income_events"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"))
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True)  # For family tax returns

    income_type = Column(String(50), nullable=False)  # interest, dividend, distribution
    payment_date = Column(Date, nullable=False, index=True)

    gross_amount = Column(Numeric(18, 2), nullable=False)
    withholding_tax = Column(Numeric(18, 2), default=0)
    net_amount = Column(Numeric(18, 2), nullable=False)

    # Tax classification
    tax_type = Column(String(50))  # DIRT, CGT, Income
    tax_rate = Column(Numeric(5, 2))

    # Source info
    source_country = Column(String(100))

    # Relationships
    person = relationship("Person", back_populates="income_events")

    created_at = Column(DateTime, default=datetime.utcnow)


class TaxReport(Base):
    """Generated tax report summary."""
    __tablename__ = "tax_reports"

    id = Column(Integer, primary_key=True, index=True)
    tax_year = Column(Integer, nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True)  # For family tax returns

    # CGT Summary
    cgt_gains = Column(Numeric(18, 2), default=0)
    cgt_losses = Column(Numeric(18, 2), default=0)
    cgt_net = Column(Numeric(18, 2), default=0)
    cgt_exemption_used = Column(Numeric(18, 2), default=0)
    cgt_taxable = Column(Numeric(18, 2), default=0)
    cgt_tax_due = Column(Numeric(18, 2), default=0)

    # Exit Tax Summary
    exit_tax_gains = Column(Numeric(18, 2), default=0)
    exit_tax_losses = Column(Numeric(18, 2), default=0)
    exit_tax_taxable = Column(Numeric(18, 2), default=0)
    exit_tax_due = Column(Numeric(18, 2), default=0)

    # Deemed Disposal Summary
    deemed_disposal_gains = Column(Numeric(18, 2), default=0)
    deemed_disposal_tax_due = Column(Numeric(18, 2), default=0)

    # DIRT Summary
    interest_income = Column(Numeric(18, 2), default=0)
    dirt_tax_due = Column(Numeric(18, 2), default=0)

    # Dividend Summary
    dividend_income = Column(Numeric(18, 2), default=0)
    dividend_withholding_credit = Column(Numeric(18, 2), default=0)

    # Total
    total_tax_due = Column(Numeric(18, 2), default=0)

    # Payment periods (Irish CGT split)
    jan_nov_gains = Column(Numeric(18, 2), default=0)  # Due Dec 15
    dec_gains = Column(Numeric(18, 2), default=0)       # Due Jan 31

    # Relationships
    person = relationship("Person", back_populates="tax_reports")

    generated_at = Column(DateTime, default=datetime.utcnow)
    report_data = Column(Text)  # JSON with detailed breakdown
