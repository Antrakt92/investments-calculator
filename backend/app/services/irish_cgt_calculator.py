"""
Irish Capital Gains Tax Calculator

Implements Irish CGT rules:
- 33% tax rate
- Annual exemption: €1,270
- Matching rules (NOT FIFO):
  1. Same-day acquisitions
  2. Acquisitions within next 4 weeks (bed & breakfast rule)
  3. FIFO for remaining shares

Payment deadlines:
- Gains Jan-Nov: Due December 15 of same year
- Gains December: Due January 31 of following year
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from collections import defaultdict


@dataclass
class TaxLot:
    """A tax lot representing shares acquired at a specific cost."""
    acquisition_date: date
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    remaining_quantity: Decimal
    transaction_id: Optional[int] = None


@dataclass
class DisposalMatch:
    """Records which acquisition lot was matched to a disposal."""
    disposal_date: date
    acquisition_date: date
    quantity_matched: Decimal
    cost_basis: Decimal
    proceeds: Decimal
    gain_loss: Decimal
    match_rule: str  # "same_day", "bed_breakfast", "fifo"


@dataclass
class CGTResult:
    """Result of CGT calculation for a tax year."""
    tax_year: int

    # Gains and losses
    total_gains: Decimal = Decimal("0")
    total_losses: Decimal = Decimal("0")
    net_gain_loss: Decimal = Decimal("0")

    # After exemption
    annual_exemption: Decimal = Decimal("1270")
    exemption_used: Decimal = Decimal("0")
    taxable_gain: Decimal = Decimal("0")

    # Tax calculation
    tax_rate: Decimal = Decimal("0.33")
    tax_due: Decimal = Decimal("0")

    # Payment periods
    jan_nov_gains: Decimal = Decimal("0")  # Due Dec 15
    jan_nov_tax: Decimal = Decimal("0")
    dec_gains: Decimal = Decimal("0")       # Due Jan 31
    dec_tax: Decimal = Decimal("0")

    # Detailed matches
    disposal_matches: list[DisposalMatch] = field(default_factory=list)

    # Loss carryforward
    losses_to_carry_forward: Decimal = Decimal("0")


@dataclass
class Disposal:
    """A disposal (sale) transaction."""
    date: date
    isin: str
    quantity: Decimal
    unit_price: Decimal
    proceeds: Decimal
    fees: Decimal = Decimal("0")


@dataclass
class Acquisition:
    """An acquisition (buy) transaction."""
    date: date
    isin: str
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    remaining: Decimal = Decimal("0")

    def __post_init__(self):
        self.remaining = self.quantity


class IrishCGTCalculator:
    """
    Calculator for Irish Capital Gains Tax.

    Implements proper Irish matching rules:
    1. Same-day rule: Match with acquisitions on the same day
    2. Bed & breakfast rule: Match with acquisitions in the next 4 weeks
    3. FIFO: Match with earliest remaining acquisitions
    """

    CGT_RATE = Decimal("0.33")
    ANNUAL_EXEMPTION = Decimal("1270")
    BED_BREAKFAST_DAYS = 28  # 4 weeks

    def __init__(self):
        # Holdings per ISIN: list of TaxLot
        self.holdings: dict[str, list[TaxLot]] = defaultdict(list)
        self.disposal_matches: list[DisposalMatch] = []

    def add_acquisition(self, isin: str, acq: Acquisition):
        """Add an acquisition to the holdings."""
        lot = TaxLot(
            acquisition_date=acq.date,
            quantity=acq.quantity,
            unit_cost=acq.unit_cost,
            total_cost=acq.total_cost,
            remaining_quantity=acq.quantity
        )
        self.holdings[isin].append(lot)
        # Keep sorted by date for FIFO
        self.holdings[isin].sort(key=lambda x: x.acquisition_date)

    def process_disposal(self, disposal: Disposal) -> list[DisposalMatch]:
        """
        Process a disposal using Irish matching rules.
        Returns list of matches made.
        """
        isin = disposal.isin
        remaining_to_match = disposal.quantity
        matches = []

        if isin not in self.holdings or not self.holdings[isin]:
            # No holdings to match - this could be a short sale or error
            return matches

        lots = self.holdings[isin]

        # Step 1: Same-day rule
        remaining_to_match, new_matches = self._match_same_day(
            lots, disposal, remaining_to_match
        )
        matches.extend(new_matches)

        if remaining_to_match <= 0:
            return matches

        # Step 2: Bed & breakfast rule (next 4 weeks)
        remaining_to_match, new_matches = self._match_bed_breakfast(
            lots, disposal, remaining_to_match
        )
        matches.extend(new_matches)

        if remaining_to_match <= 0:
            return matches

        # Step 3: FIFO for remaining
        remaining_to_match, new_matches = self._match_fifo(
            lots, disposal, remaining_to_match
        )
        matches.extend(new_matches)

        self.disposal_matches.extend(matches)
        return matches

    def _match_same_day(
        self, lots: list[TaxLot], disposal: Disposal, remaining: Decimal
    ) -> tuple[Decimal, list[DisposalMatch]]:
        """Match disposal with same-day acquisitions."""
        matches = []

        for lot in lots:
            if remaining <= 0:
                break

            if lot.acquisition_date == disposal.date and lot.remaining_quantity > 0:
                match_qty = min(remaining, lot.remaining_quantity)
                cost_basis = match_qty * lot.unit_cost
                proceeds = match_qty * disposal.unit_price
                gain_loss = proceeds - cost_basis

                matches.append(DisposalMatch(
                    disposal_date=disposal.date,
                    acquisition_date=lot.acquisition_date,
                    quantity_matched=match_qty,
                    cost_basis=cost_basis,
                    proceeds=proceeds,
                    gain_loss=gain_loss,
                    match_rule="same_day"
                ))

                lot.remaining_quantity -= match_qty
                remaining -= match_qty

        return remaining, matches

    def _match_bed_breakfast(
        self, lots: list[TaxLot], disposal: Disposal, remaining: Decimal
    ) -> tuple[Decimal, list[DisposalMatch]]:
        """
        Match disposal with acquisitions in the next 4 weeks.
        This is the "bed & breakfast" anti-avoidance rule.
        """
        matches = []
        cutoff_date = disposal.date + timedelta(days=self.BED_BREAKFAST_DAYS)

        # Find acquisitions in the next 4 weeks (after the disposal date)
        future_lots = [
            lot for lot in lots
            if disposal.date < lot.acquisition_date <= cutoff_date
            and lot.remaining_quantity > 0
        ]

        # Sort by date (earliest first within the 4-week window)
        future_lots.sort(key=lambda x: x.acquisition_date)

        for lot in future_lots:
            if remaining <= 0:
                break

            match_qty = min(remaining, lot.remaining_quantity)
            cost_basis = match_qty * lot.unit_cost
            proceeds = match_qty * disposal.unit_price
            gain_loss = proceeds - cost_basis

            matches.append(DisposalMatch(
                disposal_date=disposal.date,
                acquisition_date=lot.acquisition_date,
                quantity_matched=match_qty,
                cost_basis=cost_basis,
                proceeds=proceeds,
                gain_loss=gain_loss,
                match_rule="bed_breakfast"
            ))

            lot.remaining_quantity -= match_qty
            remaining -= match_qty

        return remaining, matches

    def _match_fifo(
        self, lots: list[TaxLot], disposal: Disposal, remaining: Decimal
    ) -> tuple[Decimal, list[DisposalMatch]]:
        """Match disposal using FIFO (excluding same-day and bed & breakfast lots)."""
        matches = []

        # FIFO: match with oldest lots first (already sorted by date)
        # Exclude same-day and future (bed & breakfast) lots
        eligible_lots = [
            lot for lot in lots
            if lot.acquisition_date < disposal.date  # Before disposal date
            and lot.remaining_quantity > 0
        ]

        for lot in eligible_lots:
            if remaining <= 0:
                break

            match_qty = min(remaining, lot.remaining_quantity)
            cost_basis = match_qty * lot.unit_cost
            proceeds = match_qty * disposal.unit_price
            gain_loss = proceeds - cost_basis

            matches.append(DisposalMatch(
                disposal_date=disposal.date,
                acquisition_date=lot.acquisition_date,
                quantity_matched=match_qty,
                cost_basis=cost_basis,
                proceeds=proceeds,
                gain_loss=gain_loss,
                match_rule="fifo"
            ))

            lot.remaining_quantity -= match_qty
            remaining -= match_qty

        return remaining, matches

    def calculate_tax(
        self,
        tax_year: int,
        losses_brought_forward: Decimal = Decimal("0")
    ) -> CGTResult:
        """
        Calculate CGT for a tax year based on processed disposals.
        """
        result = CGTResult(tax_year=tax_year)

        # Sum gains and losses
        for match in self.disposal_matches:
            if match.disposal_date.year != tax_year:
                continue

            if match.gain_loss > 0:
                result.total_gains += match.gain_loss

                # Split by period for payment deadlines
                if match.disposal_date.month < 12:
                    result.jan_nov_gains += match.gain_loss
                else:
                    result.dec_gains += match.gain_loss
            else:
                result.total_losses += abs(match.gain_loss)

            result.disposal_matches.append(match)

        # Net position
        result.net_gain_loss = result.total_gains - result.total_losses - losses_brought_forward

        # Apply annual exemption (only against gains, not losses)
        if result.net_gain_loss > 0:
            result.exemption_used = min(result.net_gain_loss, self.ANNUAL_EXEMPTION)
            result.taxable_gain = result.net_gain_loss - result.exemption_used
            result.tax_due = (result.taxable_gain * self.CGT_RATE).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            # Calculate tax by period
            if result.jan_nov_gains > result.total_losses:
                jan_nov_net = result.jan_nov_gains - result.total_losses - losses_brought_forward
                jan_nov_taxable = max(Decimal("0"), jan_nov_net - self.ANNUAL_EXEMPTION)
                result.jan_nov_tax = (jan_nov_taxable * self.CGT_RATE).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )

            if result.dec_gains > 0:
                # December gains use remaining exemption after Jan-Nov
                remaining_exemption = max(
                    Decimal("0"),
                    self.ANNUAL_EXEMPTION - max(Decimal("0"), result.jan_nov_gains - result.total_losses)
                )
                dec_taxable = max(Decimal("0"), result.dec_gains - remaining_exemption)
                result.dec_tax = (dec_taxable * self.CGT_RATE).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
        else:
            # Net loss - can carry forward
            result.losses_to_carry_forward = abs(result.net_gain_loss)

        return result

    def get_remaining_holdings(self, isin: str) -> list[TaxLot]:
        """Get remaining tax lots for an ISIN."""
        return [lot for lot in self.holdings.get(isin, []) if lot.remaining_quantity > 0]

    def get_total_cost_basis(self, isin: str) -> Decimal:
        """Get total remaining cost basis for an ISIN."""
        return sum(
            lot.remaining_quantity * lot.unit_cost
            for lot in self.get_remaining_holdings(isin)
        )
