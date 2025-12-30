"""
Irish DIRT (Deposit Interest Retention Tax) Calculator

DIRT applies to:
- Interest on deposits
- Interest from Trade Republic's cash balance
- Rate: 33%
- Trade Republic does NOT withhold DIRT - must self-declare

Key points:
- No exemption (unlike CGT)
- Must be declared on Form 11/Form 12
- Due with annual tax return
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


@dataclass
class InterestPayment:
    """An interest payment received."""
    payment_date: date
    source: str  # e.g., "Trade Republic", bank name
    gross_amount: Decimal
    withholding_tax: Decimal = Decimal("0")  # Usually 0 for TR
    net_amount: Decimal = Decimal("0")

    def __post_init__(self):
        if self.net_amount == 0:
            self.net_amount = self.gross_amount - self.withholding_tax


@dataclass
class DIRTResult:
    """Result of DIRT calculation for a tax year."""
    tax_year: int

    # Interest income
    total_interest: Decimal = Decimal("0")
    tax_withheld: Decimal = Decimal("0")  # Usually 0 for Trade Republic
    net_interest: Decimal = Decimal("0")

    # DIRT calculation (33%)
    tax_rate: Decimal = Decimal("0.33")
    dirt_due: Decimal = Decimal("0")
    dirt_already_paid: Decimal = Decimal("0")  # If any withholding
    dirt_to_pay: Decimal = Decimal("0")

    # Monthly breakdown for Form 11
    monthly_interest: dict[int, Decimal] = field(default_factory=dict)

    # Detailed payments
    interest_payments: list[InterestPayment] = field(default_factory=list)

    # Form guidance
    form_12_field: str = ""  # Which field on Form 12
    form_11_field: str = ""  # Which field on Form 11


class DIRTCalculator:
    """
    Calculator for Irish DIRT on interest income.

    Trade Republic pays interest on cash balances but does NOT
    withhold Irish DIRT, so the full amount must be self-declared.
    """

    DIRT_RATE = Decimal("0.33")

    def __init__(self):
        self.interest_payments: list[InterestPayment] = []

    def add_interest_payment(
        self,
        payment_date: date,
        gross_amount: Decimal,
        source: str = "Trade Republic",
        withholding_tax: Decimal = Decimal("0")
    ):
        """Add an interest payment."""
        payment = InterestPayment(
            payment_date=payment_date,
            source=source,
            gross_amount=gross_amount,
            withholding_tax=withholding_tax
        )
        self.interest_payments.append(payment)

    def calculate_tax(self, tax_year: int) -> DIRTResult:
        """Calculate DIRT for a tax year."""
        result = DIRTResult(tax_year=tax_year)

        # Initialize monthly breakdown
        for month in range(1, 13):
            result.monthly_interest[month] = Decimal("0")

        # Sum interest payments for the year
        for payment in self.interest_payments:
            if payment.payment_date.year != tax_year:
                continue

            result.interest_payments.append(payment)
            result.total_interest += payment.gross_amount
            result.tax_withheld += payment.withholding_tax
            result.net_interest += payment.net_amount

            # Add to monthly breakdown
            month = payment.payment_date.month
            result.monthly_interest[month] += payment.gross_amount

        # Calculate DIRT due
        result.dirt_due = (result.total_interest * self.DIRT_RATE).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Amount already paid (if any withholding)
        result.dirt_already_paid = result.tax_withheld

        # Amount still to pay
        result.dirt_to_pay = result.dirt_due - result.dirt_already_paid

        # Form guidance
        result.form_12_field = "Deposit Interest - Gross amount in 'Other Irish Income'"
        result.form_11_field = "Panel D - Irish Rental & Investment Income - Deposit Interest"

        return result

    def get_annual_summary(self, tax_year: int) -> dict:
        """Get annual summary for tax return."""
        result = self.calculate_tax(tax_year)

        return {
            "tax_year": tax_year,
            "gross_interest": float(result.total_interest),
            "dirt_rate": "33%",
            "dirt_due": float(result.dirt_due),
            "tax_withheld": float(result.tax_withheld),
            "tax_to_pay": float(result.dirt_to_pay),
            "note": "Trade Republic does not withhold DIRT - full amount must be self-declared",
            "form_11": {
                "section": "Panel D - Irish Rental & Investment Income",
                "field": "Deposit Interest",
                "gross_amount": float(result.total_interest),
                "tax_deducted": float(result.tax_withheld)
            },
            "form_12": {
                "section": "Other Irish Income",
                "field": "Deposit Interest (Gross)",
                "amount": float(result.total_interest)
            }
        }
