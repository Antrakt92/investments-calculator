"""
Irish Exit Tax Calculator

Exit Tax applies to:
- Irish/EU domiciled funds (ISIN starting with IE, LU, DE, FR, etc.)
- UCITS funds
- Rate: 41%
- NO annual exemption
- NO loss offset with CGT assets

Special features:
- Deemed disposal every 8 years from purchase
- Must track and calculate upcoming deemed disposals
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


@dataclass
class FundHolding:
    """A holding in an EU-domiciled fund subject to Exit Tax."""
    isin: str
    name: str
    acquisition_date: date
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    remaining_quantity: Decimal

    # Deemed disposal tracking
    deemed_disposal_date: Optional[date] = None  # 8 years from acquisition
    deemed_disposal_processed: bool = False

    def __post_init__(self):
        self.remaining_quantity = self.quantity
        # Calculate deemed disposal date (8 years from acquisition)
        self.deemed_disposal_date = date(
            self.acquisition_date.year + 8,
            self.acquisition_date.month,
            self.acquisition_date.day
        )


@dataclass
class ExitTaxDisposal:
    """A disposal of EU fund units."""
    disposal_date: date
    isin: str
    quantity: Decimal
    unit_price: Decimal
    proceeds: Decimal
    cost_basis: Decimal
    gain_loss: Decimal
    is_deemed_disposal: bool = False


@dataclass
class DeemedDisposalEvent:
    """Upcoming or processed deemed disposal event."""
    isin: str
    name: str
    original_acquisition_date: date
    deemed_disposal_date: date
    quantity: Decimal
    cost_basis: Decimal
    current_value: Optional[Decimal] = None
    estimated_gain: Optional[Decimal] = None
    estimated_tax: Optional[Decimal] = None
    processed: bool = False


@dataclass
class ExitTaxResult:
    """Result of Exit Tax calculation for a tax year."""
    tax_year: int

    # Actual disposals
    disposal_gains: Decimal = Decimal("0")
    disposal_losses: Decimal = Decimal("0")
    net_disposal_gain_loss: Decimal = Decimal("0")

    # Deemed disposals (8-year rule)
    deemed_disposal_gains: Decimal = Decimal("0")

    # Total taxable (losses cannot offset gains for Exit Tax)
    total_gains_taxable: Decimal = Decimal("0")

    # Tax calculation (41%)
    tax_rate: Decimal = Decimal("0.41")
    tax_due: Decimal = Decimal("0")

    # Detailed records
    disposals: list[ExitTaxDisposal] = field(default_factory=list)
    deemed_disposals: list[DeemedDisposalEvent] = field(default_factory=list)

    # Upcoming deemed disposals (for planning)
    upcoming_deemed_disposals: list[DeemedDisposalEvent] = field(default_factory=list)


class ExitTaxCalculator:
    """
    Calculator for Irish Exit Tax on EU-domiciled funds.

    Key rules:
    - 41% tax rate
    - No annual exemption
    - Losses cannot be offset against CGT gains (separate regime)
    - 8-year deemed disposal rule
    """

    EXIT_TAX_RATE = Decimal("0.41")
    DEEMED_DISPOSAL_YEARS = 8

    # EU countries where funds are subject to Exit Tax
    EU_FUND_COUNTRIES = {"IE", "LU", "DE", "FR", "NL", "AT", "BE", "IT", "ES", "PT"}

    def __init__(self):
        # Holdings per ISIN
        self.holdings: dict[str, list[FundHolding]] = {}

    @classmethod
    def is_exit_tax_asset(cls, isin: str, name: str = "") -> bool:
        """Determine if an asset is subject to Exit Tax."""
        if not isin or len(isin) < 2:
            return False

        country_code = isin[:2]
        name_lower = name.lower() if name else ""

        # EU domiciled
        if country_code not in cls.EU_FUND_COUNTRIES:
            return False

        # Check if it's a fund/ETF (not a stock)
        fund_keywords = [
            "etf", "fund", "ucits", "acc", "dist", "index", "tracker",
            "ishares", "vanguard", "amundi", "xtrackers", "lyxor",
            "spdr", "invesco", "wisdomtree", "3x", "2x", "leveraged",
            "short", "nasdaq", "s&p", "msci", "ftse", "bond", "equity",
            "money market", "floating rate"
        ]

        # If it's from IE/LU and doesn't look like a regular company stock
        if country_code in ["IE", "LU"]:
            # Most IE/LU ISINs that aren't funds are stocks like Jazz Pharmaceuticals
            # Check for fund indicators
            return any(kw in name_lower for kw in fund_keywords)

        return any(kw in name_lower for kw in fund_keywords)

    def add_acquisition(
        self,
        isin: str,
        name: str,
        acquisition_date: date,
        quantity: Decimal,
        unit_cost: Decimal,
    ):
        """Add a fund acquisition."""
        holding = FundHolding(
            isin=isin,
            name=name,
            acquisition_date=acquisition_date,
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=quantity * unit_cost,
            remaining_quantity=quantity
        )

        if isin not in self.holdings:
            self.holdings[isin] = []
        self.holdings[isin].append(holding)
        # Sort by date for FIFO matching
        self.holdings[isin].sort(key=lambda x: x.acquisition_date)

    def process_disposal(
        self,
        isin: str,
        disposal_date: date,
        quantity: Decimal,
        unit_price: Decimal,
        is_deemed_disposal: bool = False
    ) -> list[ExitTaxDisposal]:
        """Process a fund disposal using FIFO."""
        if isin not in self.holdings:
            return []

        remaining = quantity
        disposals = []

        for holding in self.holdings[isin]:
            if remaining <= 0:
                break

            if holding.remaining_quantity <= 0:
                continue

            match_qty = min(remaining, holding.remaining_quantity)
            cost_basis = match_qty * holding.unit_cost
            proceeds = match_qty * unit_price
            gain_loss = proceeds - cost_basis

            disposals.append(ExitTaxDisposal(
                disposal_date=disposal_date,
                isin=isin,
                quantity=match_qty,
                unit_price=unit_price,
                proceeds=proceeds,
                cost_basis=cost_basis,
                gain_loss=gain_loss,
                is_deemed_disposal=is_deemed_disposal
            ))

            holding.remaining_quantity -= match_qty
            remaining -= match_qty

            # If deemed disposal, update the acquisition date for next 8-year cycle
            if is_deemed_disposal:
                holding.deemed_disposal_processed = True
                # Reset cost basis to current value for next deemed disposal
                holding.unit_cost = unit_price
                holding.deemed_disposal_date = date(
                    disposal_date.year + self.DEEMED_DISPOSAL_YEARS,
                    disposal_date.month,
                    disposal_date.day
                )

        return disposals

    def get_deemed_disposals_in_year(
        self,
        tax_year: int,
        current_prices: Optional[dict[str, Decimal]] = None
    ) -> list[DeemedDisposalEvent]:
        """Get deemed disposal events occurring in a tax year."""
        events = []
        year_start = date(tax_year, 1, 1)
        year_end = date(tax_year, 12, 31)

        for isin, holdings in self.holdings.items():
            for holding in holdings:
                if holding.remaining_quantity <= 0:
                    continue

                if holding.deemed_disposal_date and year_start <= holding.deemed_disposal_date <= year_end:
                    current_price = current_prices.get(isin) if current_prices else None
                    current_value = None
                    estimated_gain = None
                    estimated_tax = None

                    if current_price:
                        current_value = holding.remaining_quantity * current_price
                        cost_basis = holding.remaining_quantity * holding.unit_cost
                        estimated_gain = current_value - cost_basis
                        if estimated_gain > 0:
                            estimated_tax = (estimated_gain * self.EXIT_TAX_RATE).quantize(
                                Decimal("0.01"), rounding=ROUND_HALF_UP
                            )

                    events.append(DeemedDisposalEvent(
                        isin=isin,
                        name=holding.name,
                        original_acquisition_date=holding.acquisition_date,
                        deemed_disposal_date=holding.deemed_disposal_date,
                        quantity=holding.remaining_quantity,
                        cost_basis=holding.remaining_quantity * holding.unit_cost,
                        current_value=current_value,
                        estimated_gain=estimated_gain,
                        estimated_tax=estimated_tax
                    ))

        return events

    def get_upcoming_deemed_disposals(
        self,
        as_of_date: date,
        years_ahead: int = 3,
        current_prices: Optional[dict[str, Decimal]] = None
    ) -> list[DeemedDisposalEvent]:
        """Get upcoming deemed disposals for planning."""
        events = []
        cutoff = date(
            as_of_date.year + years_ahead,
            as_of_date.month,
            as_of_date.day
        )

        for isin, holdings in self.holdings.items():
            for holding in holdings:
                if holding.remaining_quantity <= 0:
                    continue

                if holding.deemed_disposal_date and as_of_date < holding.deemed_disposal_date <= cutoff:
                    current_price = current_prices.get(isin) if current_prices else None
                    current_value = None
                    estimated_gain = None
                    estimated_tax = None

                    if current_price:
                        current_value = holding.remaining_quantity * current_price
                        cost_basis = holding.remaining_quantity * holding.unit_cost
                        estimated_gain = current_value - cost_basis
                        if estimated_gain > 0:
                            estimated_tax = (estimated_gain * self.EXIT_TAX_RATE).quantize(
                                Decimal("0.01"), rounding=ROUND_HALF_UP
                            )

                    events.append(DeemedDisposalEvent(
                        isin=isin,
                        name=holding.name,
                        original_acquisition_date=holding.acquisition_date,
                        deemed_disposal_date=holding.deemed_disposal_date,
                        quantity=holding.remaining_quantity,
                        cost_basis=holding.remaining_quantity * holding.unit_cost,
                        current_value=current_value,
                        estimated_gain=estimated_gain,
                        estimated_tax=estimated_tax
                    ))

        # Sort by date
        events.sort(key=lambda x: x.deemed_disposal_date)
        return events

    def calculate_tax(
        self,
        tax_year: int,
        disposals: list[ExitTaxDisposal]
    ) -> ExitTaxResult:
        """Calculate Exit Tax for a tax year."""
        result = ExitTaxResult(tax_year=tax_year)

        for disposal in disposals:
            if disposal.disposal_date.year != tax_year:
                continue

            result.disposals.append(disposal)

            if disposal.is_deemed_disposal:
                if disposal.gain_loss > 0:
                    result.deemed_disposal_gains += disposal.gain_loss
            else:
                if disposal.gain_loss > 0:
                    result.disposal_gains += disposal.gain_loss
                else:
                    result.disposal_losses += abs(disposal.gain_loss)

        # Net disposal gain/loss (but losses don't reduce deemed disposal gains)
        result.net_disposal_gain_loss = result.disposal_gains - result.disposal_losses

        # Total taxable: gains only (losses cannot offset, no exemption)
        # Note: Within Exit Tax regime, losses can offset gains
        # But cannot offset against CGT regime
        result.total_gains_taxable = max(
            Decimal("0"),
            result.disposal_gains - result.disposal_losses
        ) + result.deemed_disposal_gains

        # Calculate tax
        result.tax_due = (result.total_gains_taxable * self.EXIT_TAX_RATE).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        return result
