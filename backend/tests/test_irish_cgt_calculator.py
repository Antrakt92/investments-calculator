"""
Tests for Irish CGT Calculator.

Tests cover:
- Basic gain/loss calculation
- Same-day matching rule
- Bed & Breakfast (4-week) rule
- FIFO matching
- Annual exemption
- Loss carry forward
- Payment period splitting (Jan-Nov vs December)
"""
import pytest
import sys
from pathlib import Path
from decimal import Decimal
from datetime import date, timedelta

# Add the app/services directory to path for direct imports
sys.path.insert(0, str(Path(__file__).parent.parent / "app" / "services"))

# Import directly from the module file to avoid __init__.py chain
from irish_cgt_calculator import (
    IrishCGTCalculator,
    Acquisition,
    Disposal,
    TaxLot,
    DisposalMatch,
    CGTResult
)


class TestBasicCalculations:
    """Test basic gain/loss calculations."""

    def test_simple_gain(self):
        """Buy low, sell high = gain."""
        calc = IrishCGTCalculator()

        # Buy 100 shares at €10
        acq = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00"),
            total_cost=Decimal("1000.00")
        )
        calc.add_acquisition("US0001", acq)

        # Sell 100 shares at €15
        disposal = Disposal(
            date=date(2024, 6, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_price=Decimal("15.00"),
            proceeds=Decimal("1500.00")
        )
        calc.process_disposal(disposal)

        result = calc.calculate_tax(2024)

        assert result.total_gains == Decimal("500.00")
        assert result.total_losses == Decimal("0")
        assert result.net_gain_loss == Decimal("500.00")

    def test_simple_loss(self):
        """Buy high, sell low = loss."""
        calc = IrishCGTCalculator()

        # Buy 100 shares at €20
        acq = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("20.00"),
            total_cost=Decimal("2000.00")
        )
        calc.add_acquisition("US0001", acq)

        # Sell 100 shares at €15
        disposal = Disposal(
            date=date(2024, 6, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_price=Decimal("15.00"),
            proceeds=Decimal("1500.00")
        )
        calc.process_disposal(disposal)

        result = calc.calculate_tax(2024)

        assert result.total_gains == Decimal("0")
        assert result.total_losses == Decimal("500.00")
        assert result.net_gain_loss == Decimal("-500.00")

    def test_partial_sale(self):
        """Sell only part of holdings."""
        calc = IrishCGTCalculator()

        # Buy 100 shares at €10
        acq = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00"),
            total_cost=Decimal("1000.00")
        )
        calc.add_acquisition("US0001", acq)

        # Sell only 50 shares at €15
        disposal = Disposal(
            date=date(2024, 6, 15),
            isin="US0001",
            quantity=Decimal("50"),
            unit_price=Decimal("15.00"),
            proceeds=Decimal("750.00")
        )
        calc.process_disposal(disposal)

        result = calc.calculate_tax(2024)

        # Gain = 50 * (15 - 10) = 250
        assert result.total_gains == Decimal("250.00")

        # 50 shares should remain
        remaining = calc.get_remaining_holdings("US0001")
        assert len(remaining) == 1
        assert remaining[0].remaining_quantity == Decimal("50")


class TestMatchingRules:
    """Test Irish CGT matching rules."""

    def test_same_day_rule(self):
        """Same-day acquisitions should match first."""
        calc = IrishCGTCalculator()

        # Buy 100 shares at €10 in January
        acq1 = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00"),
            total_cost=Decimal("1000.00")
        )
        calc.add_acquisition("US0001", acq1)

        # Buy 50 shares at €20 on same day as sale (June 15)
        acq2 = Acquisition(
            date=date(2024, 6, 15),
            isin="US0001",
            quantity=Decimal("50"),
            unit_cost=Decimal("20.00"),
            total_cost=Decimal("1000.00")
        )
        calc.add_acquisition("US0001", acq2)

        # Sell 50 shares at €25 on June 15
        disposal = Disposal(
            date=date(2024, 6, 15),
            isin="US0001",
            quantity=Decimal("50"),
            unit_price=Decimal("25.00"),
            proceeds=Decimal("1250.00")
        )
        matches = calc.process_disposal(disposal)

        # Should match with same-day acquisition (€20 cost), not FIFO (€10 cost)
        assert len(matches) == 1
        assert matches[0].match_rule == "same_day"
        assert matches[0].cost_basis == Decimal("1000.00")  # 50 * €20
        assert matches[0].gain_loss == Decimal("250.00")    # 1250 - 1000

    def test_bed_breakfast_rule(self):
        """Acquisitions within 4 weeks after sale should match (anti-avoidance)."""
        calc = IrishCGTCalculator()

        # Buy 100 shares at €10 in January
        acq1 = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00"),
            total_cost=Decimal("1000.00")
        )
        calc.add_acquisition("US0001", acq1)

        # Sell 100 shares at €8 on June 15 (trying to realize loss)
        disposal = Disposal(
            date=date(2024, 6, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_price=Decimal("8.00"),
            proceeds=Decimal("800.00")
        )

        # Buy back 100 shares at €8.50 on June 20 (within 4 weeks)
        acq2 = Acquisition(
            date=date(2024, 6, 20),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("8.50"),
            total_cost=Decimal("850.00")
        )
        calc.add_acquisition("US0001", acq2)

        matches = calc.process_disposal(disposal)

        # Should match with bed & breakfast acquisition (€8.50 cost), not FIFO (€10 cost)
        assert len(matches) == 1
        assert matches[0].match_rule == "bed_breakfast"
        assert matches[0].cost_basis == Decimal("850.00")   # 100 * €8.50
        assert matches[0].gain_loss == Decimal("-50.00")    # 800 - 850

    def test_fifo_after_same_day_and_bed_breakfast(self):
        """FIFO should apply only after same-day and bed & breakfast."""
        calc = IrishCGTCalculator()

        # Buy 50 shares at €10 in January (oldest - FIFO candidate)
        acq1 = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("50"),
            unit_cost=Decimal("10.00"),
            total_cost=Decimal("500.00")
        )
        calc.add_acquisition("US0001", acq1)

        # Buy 50 shares at €12 in February
        acq2 = Acquisition(
            date=date(2024, 2, 15),
            isin="US0001",
            quantity=Decimal("50"),
            unit_cost=Decimal("12.00"),
            total_cost=Decimal("600.00")
        )
        calc.add_acquisition("US0001", acq2)

        # Sell 100 shares at €15 on June 15 (no same-day or bed & breakfast)
        disposal = Disposal(
            date=date(2024, 6, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_price=Decimal("15.00"),
            proceeds=Decimal("1500.00")
        )
        matches = calc.process_disposal(disposal)

        # Should match FIFO: first 50 at €10, then 50 at €12
        assert len(matches) == 2
        assert all(m.match_rule == "fifo" for m in matches)

        # First match: 50 shares at €10 cost
        assert matches[0].cost_basis == Decimal("500.00")
        assert matches[0].gain_loss == Decimal("250.00")  # 750 - 500

        # Second match: 50 shares at €12 cost
        assert matches[1].cost_basis == Decimal("600.00")
        assert matches[1].gain_loss == Decimal("150.00")  # 750 - 600

    def test_bed_breakfast_outside_4_weeks(self):
        """Acquisitions more than 4 weeks after sale should NOT match as bed & breakfast."""
        calc = IrishCGTCalculator()

        # Buy 100 shares at €10 in January
        acq1 = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00"),
            total_cost=Decimal("1000.00")
        )
        calc.add_acquisition("US0001", acq1)

        # Sell 100 shares at €8 on June 15
        disposal = Disposal(
            date=date(2024, 6, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_price=Decimal("8.00"),
            proceeds=Decimal("800.00")
        )

        # Buy back 100 shares at €7 on August 1 (more than 4 weeks later)
        acq2 = Acquisition(
            date=date(2024, 8, 1),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("7.00"),
            total_cost=Decimal("700.00")
        )
        calc.add_acquisition("US0001", acq2)

        matches = calc.process_disposal(disposal)

        # Should match with FIFO (€10 cost), not the later purchase
        assert len(matches) == 1
        assert matches[0].match_rule == "fifo"
        assert matches[0].cost_basis == Decimal("1000.00")  # 100 * €10
        assert matches[0].gain_loss == Decimal("-200.00")   # 800 - 1000


class TestAnnualExemption:
    """Test €1,270 annual exemption."""

    def test_exemption_covers_small_gain(self):
        """Small gains within exemption = no tax."""
        calc = IrishCGTCalculator()

        # Buy at €10, sell at €11 - gain of €100
        acq = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00"),
            total_cost=Decimal("1000.00")
        )
        calc.add_acquisition("US0001", acq)

        disposal = Disposal(
            date=date(2024, 6, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_price=Decimal("11.00"),
            proceeds=Decimal("1100.00")
        )
        calc.process_disposal(disposal)

        result = calc.calculate_tax(2024)

        assert result.total_gains == Decimal("100.00")
        assert result.exemption_used == Decimal("100.00")
        assert result.taxable_gain == Decimal("0")
        assert result.tax_due == Decimal("0")

    def test_exemption_partial_use(self):
        """Gains above exemption are taxed."""
        calc = IrishCGTCalculator()

        # Gain of €2,000 (above €1,270 exemption)
        acq = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00"),
            total_cost=Decimal("1000.00")
        )
        calc.add_acquisition("US0001", acq)

        disposal = Disposal(
            date=date(2024, 6, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_price=Decimal("30.00"),
            proceeds=Decimal("3000.00")
        )
        calc.process_disposal(disposal)

        result = calc.calculate_tax(2024)

        assert result.total_gains == Decimal("2000.00")
        assert result.exemption_used == Decimal("1270.00")
        assert result.taxable_gain == Decimal("730.00")
        # Tax = 730 * 0.33 = 240.90
        assert result.tax_due == Decimal("240.90")

    def test_losses_offset_gains_before_exemption(self):
        """Losses reduce gains before applying exemption."""
        calc = IrishCGTCalculator()

        # Trade 1: Gain of €1,000
        acq1 = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00"),
            total_cost=Decimal("1000.00")
        )
        calc.add_acquisition("US0001", acq1)

        disposal1 = Disposal(
            date=date(2024, 3, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_price=Decimal("20.00"),
            proceeds=Decimal("2000.00")
        )
        calc.process_disposal(disposal1)

        # Trade 2: Loss of €500
        acq2 = Acquisition(
            date=date(2024, 2, 15),
            isin="US0002",
            quantity=Decimal("100"),
            unit_cost=Decimal("15.00"),
            total_cost=Decimal("1500.00")
        )
        calc.add_acquisition("US0002", acq2)

        disposal2 = Disposal(
            date=date(2024, 4, 15),
            isin="US0002",
            quantity=Decimal("100"),
            unit_price=Decimal("10.00"),
            proceeds=Decimal("1000.00")
        )
        calc.process_disposal(disposal2)

        result = calc.calculate_tax(2024)

        assert result.total_gains == Decimal("1000.00")
        assert result.total_losses == Decimal("500.00")
        assert result.net_gain_loss == Decimal("500.00")
        # €500 net gain < €1,270 exemption = no tax
        assert result.exemption_used == Decimal("500.00")
        assert result.tax_due == Decimal("0")


class TestLossCarryForward:
    """Test loss carry forward functionality."""

    def test_losses_carried_forward(self):
        """Net losses can be carried forward to future years."""
        calc = IrishCGTCalculator()

        # Loss-making trade
        acq = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("100.00"),
            total_cost=Decimal("10000.00")
        )
        calc.add_acquisition("US0001", acq)

        disposal = Disposal(
            date=date(2024, 6, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_price=Decimal("50.00"),
            proceeds=Decimal("5000.00")
        )
        calc.process_disposal(disposal)

        result = calc.calculate_tax(2024)

        assert result.total_losses == Decimal("5000.00")
        assert result.net_gain_loss == Decimal("-5000.00")
        assert result.losses_to_carry_forward == Decimal("5000.00")
        assert result.tax_due == Decimal("0")

    def test_using_carried_forward_losses(self):
        """Carried forward losses reduce future gains."""
        calc = IrishCGTCalculator()

        # Profitable trade in 2024
        acq = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00"),
            total_cost=Decimal("1000.00")
        )
        calc.add_acquisition("US0001", acq)

        disposal = Disposal(
            date=date(2024, 6, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_price=Decimal("30.00"),
            proceeds=Decimal("3000.00")
        )
        calc.process_disposal(disposal)

        # Calculate with €1,000 carried forward losses from previous year
        result = calc.calculate_tax(2024, losses_brought_forward=Decimal("1000.00"))

        # Gain = €2,000, minus €1,000 losses = €1,000 net
        assert result.total_gains == Decimal("2000.00")
        assert result.net_gain_loss == Decimal("1000.00")
        # €1,000 < €1,270 exemption = no tax
        assert result.tax_due == Decimal("0")


class TestPaymentPeriods:
    """Test payment period splitting (Jan-Nov vs December)."""

    def test_jan_nov_gains_due_dec_15(self):
        """Gains from Jan-Nov are due December 15."""
        calc = IrishCGTCalculator()

        # Gain in March
        acq = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00"),
            total_cost=Decimal("1000.00")
        )
        calc.add_acquisition("US0001", acq)

        disposal = Disposal(
            date=date(2024, 3, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_price=Decimal("30.00"),
            proceeds=Decimal("3000.00")
        )
        calc.process_disposal(disposal)

        result = calc.calculate_tax(2024)

        assert result.jan_nov_gains == Decimal("2000.00")
        assert result.dec_gains == Decimal("0")

    def test_december_gains_due_jan_31(self):
        """Gains from December are due January 31 of next year."""
        calc = IrishCGTCalculator()

        # Gain in December
        acq = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00"),
            total_cost=Decimal("1000.00")
        )
        calc.add_acquisition("US0001", acq)

        disposal = Disposal(
            date=date(2024, 12, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_price=Decimal("30.00"),
            proceeds=Decimal("3000.00")
        )
        calc.process_disposal(disposal)

        result = calc.calculate_tax(2024)

        assert result.jan_nov_gains == Decimal("0")
        assert result.dec_gains == Decimal("2000.00")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_quantity_disposal(self):
        """Disposing zero shares should work gracefully."""
        calc = IrishCGTCalculator()

        acq = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00"),
            total_cost=Decimal("1000.00")
        )
        calc.add_acquisition("US0001", acq)

        disposal = Disposal(
            date=date(2024, 6, 15),
            isin="US0001",
            quantity=Decimal("0"),
            unit_price=Decimal("15.00"),
            proceeds=Decimal("0")
        )
        matches = calc.process_disposal(disposal)

        assert len(matches) == 0

    def test_dispose_more_than_held(self):
        """Disposing more shares than held should only match available shares."""
        calc = IrishCGTCalculator()

        # Buy 50 shares
        acq = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("50"),
            unit_cost=Decimal("10.00"),
            total_cost=Decimal("500.00")
        )
        calc.add_acquisition("US0001", acq)

        # Try to sell 100 shares
        disposal = Disposal(
            date=date(2024, 6, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_price=Decimal("15.00"),
            proceeds=Decimal("1500.00")
        )
        matches = calc.process_disposal(disposal)

        # Should only match 50 shares
        assert len(matches) == 1
        assert matches[0].quantity_matched == Decimal("50")

    def test_dispose_unknown_isin(self):
        """Disposing shares of unknown ISIN should return empty matches."""
        calc = IrishCGTCalculator()

        disposal = Disposal(
            date=date(2024, 6, 15),
            isin="UNKNOWN",
            quantity=Decimal("100"),
            unit_price=Decimal("15.00"),
            proceeds=Decimal("1500.00")
        )
        matches = calc.process_disposal(disposal)

        assert len(matches) == 0

    def test_multiple_assets(self):
        """Test handling multiple different assets."""
        calc = IrishCGTCalculator()

        # Asset 1: Gain
        acq1 = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00"),
            total_cost=Decimal("1000.00")
        )
        calc.add_acquisition("US0001", acq1)

        # Asset 2: Loss
        acq2 = Acquisition(
            date=date(2024, 1, 15),
            isin="US0002",
            quantity=Decimal("100"),
            unit_cost=Decimal("20.00"),
            total_cost=Decimal("2000.00")
        )
        calc.add_acquisition("US0002", acq2)

        # Sell Asset 1 for gain
        disposal1 = Disposal(
            date=date(2024, 6, 15),
            isin="US0001",
            quantity=Decimal("100"),
            unit_price=Decimal("15.00"),
            proceeds=Decimal("1500.00")
        )
        calc.process_disposal(disposal1)

        # Sell Asset 2 for loss
        disposal2 = Disposal(
            date=date(2024, 6, 15),
            isin="US0002",
            quantity=Decimal("100"),
            unit_price=Decimal("10.00"),
            proceeds=Decimal("1000.00")
        )
        calc.process_disposal(disposal2)

        result = calc.calculate_tax(2024)

        assert result.total_gains == Decimal("500.00")
        assert result.total_losses == Decimal("1000.00")
        assert result.net_gain_loss == Decimal("-500.00")

    def test_fractional_shares(self):
        """Test handling fractional share quantities."""
        calc = IrishCGTCalculator()

        # Buy 10.5 shares
        acq = Acquisition(
            date=date(2024, 1, 15),
            isin="US0001",
            quantity=Decimal("10.5"),
            unit_cost=Decimal("100.00"),
            total_cost=Decimal("1050.00")
        )
        calc.add_acquisition("US0001", acq)

        # Sell 5.25 shares
        disposal = Disposal(
            date=date(2024, 6, 15),
            isin="US0001",
            quantity=Decimal("5.25"),
            unit_price=Decimal("120.00"),
            proceeds=Decimal("630.00")
        )
        calc.process_disposal(disposal)

        result = calc.calculate_tax(2024)

        # Gain = 630 - (5.25 * 100) = 630 - 525 = 105
        assert result.total_gains == Decimal("105.00")

        # 5.25 shares should remain
        remaining = calc.get_remaining_holdings("US0001")
        assert remaining[0].remaining_quantity == Decimal("5.25")
