"""
Tests for Irish Exit Tax Calculator.

Tests cover:
- Asset classification (which assets are subject to Exit Tax)
- Basic gain/loss calculation
- FIFO matching
- Loss offsetting within Exit Tax (losses CAN offset gains)
- 8-year deemed disposal rule
- Tax calculation (41%, no exemption)
"""
import pytest
import sys
from pathlib import Path
from decimal import Decimal
from datetime import date, timedelta

# Add the app/services directory to path for direct imports
sys.path.insert(0, str(Path(__file__).parent.parent / "app" / "services"))

# Import directly from the module file to avoid __init__.py chain
from exit_tax_calculator import (
    ExitTaxCalculator,
    FundHolding,
    ExitTaxDisposal,
    DeemedDisposalEvent,
    ExitTaxResult
)


class TestAssetClassification:
    """Test determining if an asset is subject to Exit Tax."""

    def test_irish_etf_is_exit_tax(self):
        """Irish ETFs (IE ISIN) are subject to Exit Tax."""
        assert ExitTaxCalculator.is_exit_tax_asset(
            "IE00BGV5VN51", "AI & Big Data USD (Acc)"
        ) is True

    def test_irish_etf_with_dist_is_exit_tax(self):
        """Irish distributing ETFs are subject to Exit Tax."""
        assert ExitTaxCalculator.is_exit_tax_asset(
            "IE00B0M62S72", "Euro Dividend EUR (Dist)"
        ) is True

    def test_luxembourg_fund_is_exit_tax(self):
        """Luxembourg funds (LU ISIN) are subject to Exit Tax."""
        assert ExitTaxCalculator.is_exit_tax_asset(
            "LU0378449770", "MSCI World ETF"
        ) is True

    def test_german_etf_is_exit_tax(self):
        """German ETFs (DE ISIN) are subject to Exit Tax."""
        assert ExitTaxCalculator.is_exit_tax_asset(
            "DE000A0D8Q49", "iShares DAX UCITS"
        ) is True

    def test_us_etf_not_exit_tax(self):
        """US ETFs (US ISIN) are NOT subject to Exit Tax."""
        assert ExitTaxCalculator.is_exit_tax_asset(
            "US78462F1030", "SPY S&P 500 ETF"
        ) is False

    def test_us_stock_not_exit_tax(self):
        """US stocks are NOT subject to Exit Tax."""
        assert ExitTaxCalculator.is_exit_tax_asset(
            "US0378331005", "Apple Inc."
        ) is False

    def test_irish_stock_not_exit_tax(self):
        """Irish stocks (not funds) are NOT subject to Exit Tax."""
        # Jazz Pharmaceuticals is an Irish company, not a fund
        assert ExitTaxCalculator.is_exit_tax_asset(
            "IE00B4Q5ZN47", "Jazz Pharmaceuticals"
        ) is False

    def test_leveraged_etf_is_exit_tax(self):
        """Leveraged ETFs are subject to Exit Tax."""
        assert ExitTaxCalculator.is_exit_tax_asset(
            "IE00BLRPRL42", "NASDAQ 100 3x Lev USD (Acc)"
        ) is True

    def test_short_etf_is_exit_tax(self):
        """Short ETFs are subject to Exit Tax."""
        assert ExitTaxCalculator.is_exit_tax_asset(
            "IE00BLRPRJ20", "NASDAQ 100 3x Short USD (Acc)"
        ) is True

    def test_empty_isin_not_exit_tax(self):
        """Empty ISIN should not be classified as Exit Tax."""
        assert ExitTaxCalculator.is_exit_tax_asset("", "Some Fund") is False
        assert ExitTaxCalculator.is_exit_tax_asset(None, "Some Fund") is False


class TestBasicCalculations:
    """Test basic Exit Tax calculations."""

    def test_simple_gain(self):
        """Simple gain calculation at 41%."""
        calc = ExitTaxCalculator()

        # Buy 100 units at €10
        calc.add_acquisition(
            isin="IE00TEST001",
            name="Test ETF (Acc)",
            acquisition_date=date(2024, 1, 15),
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00")
        )

        # Sell 100 units at €15
        disposals = calc.process_disposal(
            isin="IE00TEST001",
            disposal_date=date(2024, 6, 15),
            quantity=Decimal("100"),
            unit_price=Decimal("15.00")
        )

        result = calc.calculate_tax(2024, disposals)

        # Gain = 100 * (15 - 10) = 500
        assert result.disposal_gains == Decimal("500.00")
        assert result.total_gains_taxable == Decimal("500.00")
        # Tax = 500 * 0.41 = 205
        assert result.tax_due == Decimal("205.00")

    def test_simple_loss(self):
        """Simple loss - no tax due, but loss is tracked."""
        calc = ExitTaxCalculator()

        # Buy 100 units at €20
        calc.add_acquisition(
            isin="IE00TEST001",
            name="Test ETF (Acc)",
            acquisition_date=date(2024, 1, 15),
            quantity=Decimal("100"),
            unit_cost=Decimal("20.00")
        )

        # Sell 100 units at €15
        disposals = calc.process_disposal(
            isin="IE00TEST001",
            disposal_date=date(2024, 6, 15),
            quantity=Decimal("100"),
            unit_price=Decimal("15.00")
        )

        result = calc.calculate_tax(2024, disposals)

        assert result.disposal_gains == Decimal("0")
        assert result.disposal_losses == Decimal("500.00")
        assert result.total_gains_taxable == Decimal("0")
        assert result.tax_due == Decimal("0")


class TestLossOffsetting:
    """Test that losses CAN offset gains within Exit Tax regime."""

    def test_losses_offset_gains(self):
        """Losses within Exit Tax regime can offset gains."""
        calc = ExitTaxCalculator()

        # ETF 1: Gain of €1000
        calc.add_acquisition(
            isin="IE00TEST001",
            name="Test ETF 1 (Acc)",
            acquisition_date=date(2024, 1, 15),
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00")
        )

        # ETF 2: Loss of €600
        calc.add_acquisition(
            isin="IE00TEST002",
            name="Test ETF 2 (Acc)",
            acquisition_date=date(2024, 1, 15),
            quantity=Decimal("100"),
            unit_cost=Decimal("20.00")
        )

        # Sell ETF 1 for gain
        disposals1 = calc.process_disposal(
            isin="IE00TEST001",
            disposal_date=date(2024, 6, 15),
            quantity=Decimal("100"),
            unit_price=Decimal("20.00")  # Gain: 100 * (20-10) = 1000
        )

        # Sell ETF 2 for loss
        disposals2 = calc.process_disposal(
            isin="IE00TEST002",
            disposal_date=date(2024, 6, 20),
            quantity=Decimal("100"),
            unit_price=Decimal("14.00")  # Loss: 100 * (14-20) = -600
        )

        all_disposals = disposals1 + disposals2
        result = calc.calculate_tax(2024, all_disposals)

        assert result.disposal_gains == Decimal("1000.00")
        assert result.disposal_losses == Decimal("600.00")
        # Net = 1000 - 600 = 400
        assert result.net_disposal_gain_loss == Decimal("400.00")
        assert result.total_gains_taxable == Decimal("400.00")
        # Tax = 400 * 0.41 = 164
        assert result.tax_due == Decimal("164.00")

    def test_losses_cannot_create_negative_tax(self):
        """Losses exceeding gains result in zero tax, not negative."""
        calc = ExitTaxCalculator()

        # Small gain
        calc.add_acquisition(
            isin="IE00TEST001",
            name="Test ETF 1 (Acc)",
            acquisition_date=date(2024, 1, 15),
            quantity=Decimal("10"),
            unit_cost=Decimal("10.00")
        )

        # Large loss
        calc.add_acquisition(
            isin="IE00TEST002",
            name="Test ETF 2 (Acc)",
            acquisition_date=date(2024, 1, 15),
            quantity=Decimal("100"),
            unit_cost=Decimal("50.00")
        )

        disposals1 = calc.process_disposal(
            isin="IE00TEST001",
            disposal_date=date(2024, 6, 15),
            quantity=Decimal("10"),
            unit_price=Decimal("15.00")  # Gain: 10 * 5 = 50
        )

        disposals2 = calc.process_disposal(
            isin="IE00TEST002",
            disposal_date=date(2024, 6, 20),
            quantity=Decimal("100"),
            unit_price=Decimal("20.00")  # Loss: 100 * 30 = 3000
        )

        result = calc.calculate_tax(2024, disposals1 + disposals2)

        assert result.disposal_gains == Decimal("50.00")
        assert result.disposal_losses == Decimal("3000.00")
        assert result.total_gains_taxable == Decimal("0")  # Not negative
        assert result.tax_due == Decimal("0")


class TestFIFOMatching:
    """Test FIFO matching for Exit Tax disposals."""

    def test_fifo_order(self):
        """Oldest acquisitions should be matched first."""
        calc = ExitTaxCalculator()

        # Buy 50 units at €10 in January
        calc.add_acquisition(
            isin="IE00TEST001",
            name="Test ETF (Acc)",
            acquisition_date=date(2024, 1, 15),
            quantity=Decimal("50"),
            unit_cost=Decimal("10.00")
        )

        # Buy 50 units at €20 in March
        calc.add_acquisition(
            isin="IE00TEST001",
            name="Test ETF (Acc)",
            acquisition_date=date(2024, 3, 15),
            quantity=Decimal("50"),
            unit_cost=Decimal("20.00")
        )

        # Sell 50 units at €25
        disposals = calc.process_disposal(
            isin="IE00TEST001",
            disposal_date=date(2024, 6, 15),
            quantity=Decimal("50"),
            unit_price=Decimal("25.00")
        )

        # Should match with oldest (€10 cost), not newer (€20)
        assert len(disposals) == 1
        assert disposals[0].cost_basis == Decimal("500.00")  # 50 * €10
        assert disposals[0].gain_loss == Decimal("750.00")   # 1250 - 500

    def test_partial_lot_matching(self):
        """Partial lot matching should work correctly."""
        calc = ExitTaxCalculator()

        # Buy 100 units at €10
        calc.add_acquisition(
            isin="IE00TEST001",
            name="Test ETF (Acc)",
            acquisition_date=date(2024, 1, 15),
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00")
        )

        # Sell only 30 units
        disposals = calc.process_disposal(
            isin="IE00TEST001",
            disposal_date=date(2024, 6, 15),
            quantity=Decimal("30"),
            unit_price=Decimal("15.00")
        )

        assert len(disposals) == 1
        assert disposals[0].quantity == Decimal("30")
        assert disposals[0].cost_basis == Decimal("300.00")  # 30 * €10

        # 70 units should remain
        remaining = [h for h in calc.holdings["IE00TEST001"] if h.remaining_quantity > 0]
        assert remaining[0].remaining_quantity == Decimal("70")


class TestDeemedDisposal:
    """Test 8-year deemed disposal rule."""

    def test_deemed_disposal_date_calculation(self):
        """Deemed disposal should be 8 years from acquisition."""
        calc = ExitTaxCalculator()

        calc.add_acquisition(
            isin="IE00TEST001",
            name="Test ETF (Acc)",
            acquisition_date=date(2016, 6, 15),
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00")
        )

        holdings = calc.holdings["IE00TEST001"]
        assert len(holdings) == 1
        # 8 years from 2016-06-15 = 2024-06-15
        assert holdings[0].deemed_disposal_date == date(2024, 6, 15)

    def test_get_deemed_disposals_in_year(self):
        """Should find deemed disposals occurring in a specific year."""
        calc = ExitTaxCalculator()

        # Acquisition from 2016 (deemed disposal in 2024)
        calc.add_acquisition(
            isin="IE00TEST001",
            name="Test ETF (Acc)",
            acquisition_date=date(2016, 6, 15),
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00")
        )

        # Acquisition from 2017 (deemed disposal in 2025)
        calc.add_acquisition(
            isin="IE00TEST002",
            name="Test ETF 2 (Acc)",
            acquisition_date=date(2017, 3, 1),
            quantity=Decimal("50"),
            unit_cost=Decimal("20.00")
        )

        events_2024 = calc.get_deemed_disposals_in_year(2024)
        events_2025 = calc.get_deemed_disposals_in_year(2025)

        assert len(events_2024) == 1
        assert events_2024[0].isin == "IE00TEST001"

        assert len(events_2025) == 1
        assert events_2025[0].isin == "IE00TEST002"

    def test_upcoming_deemed_disposals(self):
        """Should list upcoming deemed disposals for planning."""
        calc = ExitTaxCalculator()

        # Various acquisitions with different deemed disposal dates
        calc.add_acquisition(
            isin="IE00TEST001",
            name="Test ETF 1 (Acc)",
            acquisition_date=date(2018, 1, 15),  # Deemed: 2026-01-15
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00")
        )

        calc.add_acquisition(
            isin="IE00TEST002",
            name="Test ETF 2 (Acc)",
            acquisition_date=date(2019, 6, 15),  # Deemed: 2027-06-15
            quantity=Decimal("50"),
            unit_cost=Decimal("20.00")
        )

        # Check from 2025, looking 3 years ahead
        upcoming = calc.get_upcoming_deemed_disposals(
            as_of_date=date(2025, 1, 1),
            years_ahead=3
        )

        assert len(upcoming) == 2
        # Should be sorted by date
        assert upcoming[0].deemed_disposal_date < upcoming[1].deemed_disposal_date

    def test_leap_year_feb_29_handling(self):
        """Acquisition on Feb 29 should handle non-leap year deemed disposal."""
        calc = ExitTaxCalculator()

        # Acquisition on Feb 29, 2016 (leap year)
        calc.add_acquisition(
            isin="IE00TEST001",
            name="Test ETF (Acc)",
            acquisition_date=date(2016, 2, 29),
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00")
        )

        holdings = calc.holdings["IE00TEST001"]
        # 2024 is a leap year, so should be Feb 29
        assert holdings[0].deemed_disposal_date == date(2024, 2, 29)


class TestNoExemption:
    """Test that Exit Tax has NO annual exemption."""

    def test_small_gain_still_taxed(self):
        """Even small gains are taxed - no €1,270 exemption like CGT."""
        calc = ExitTaxCalculator()

        calc.add_acquisition(
            isin="IE00TEST001",
            name="Test ETF (Acc)",
            acquisition_date=date(2024, 1, 15),
            quantity=Decimal("10"),
            unit_cost=Decimal("10.00")
        )

        disposals = calc.process_disposal(
            isin="IE00TEST001",
            disposal_date=date(2024, 6, 15),
            quantity=Decimal("10"),
            unit_price=Decimal("11.00")  # Gain: 10 * 1 = €10
        )

        result = calc.calculate_tax(2024, disposals)

        # €10 gain should still be taxed (no exemption)
        assert result.disposal_gains == Decimal("10.00")
        assert result.total_gains_taxable == Decimal("10.00")
        # Tax = 10 * 0.41 = 4.10
        assert result.tax_due == Decimal("4.10")


class TestEdgeCases:
    """Test edge cases."""

    def test_dispose_unknown_isin(self):
        """Disposing from unknown ISIN should return empty list."""
        calc = ExitTaxCalculator()

        disposals = calc.process_disposal(
            isin="UNKNOWN",
            disposal_date=date(2024, 6, 15),
            quantity=Decimal("100"),
            unit_price=Decimal("15.00")
        )

        assert len(disposals) == 0

    def test_dispose_more_than_held(self):
        """Should only match available quantity."""
        calc = ExitTaxCalculator()

        calc.add_acquisition(
            isin="IE00TEST001",
            name="Test ETF (Acc)",
            acquisition_date=date(2024, 1, 15),
            quantity=Decimal("50"),
            unit_cost=Decimal("10.00")
        )

        # Try to sell 100 but only have 50
        disposals = calc.process_disposal(
            isin="IE00TEST001",
            disposal_date=date(2024, 6, 15),
            quantity=Decimal("100"),
            unit_price=Decimal("15.00")
        )

        assert len(disposals) == 1
        assert disposals[0].quantity == Decimal("50")

    def test_multiple_funds(self):
        """Test handling multiple different funds."""
        calc = ExitTaxCalculator()

        # Fund 1
        calc.add_acquisition(
            isin="IE00TEST001",
            name="Test ETF 1 (Acc)",
            acquisition_date=date(2024, 1, 15),
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00")
        )

        # Fund 2
        calc.add_acquisition(
            isin="IE00TEST002",
            name="Test ETF 2 (Acc)",
            acquisition_date=date(2024, 1, 15),
            quantity=Decimal("50"),
            unit_cost=Decimal("20.00")
        )

        # Sell from each
        disposals1 = calc.process_disposal(
            isin="IE00TEST001",
            disposal_date=date(2024, 6, 15),
            quantity=Decimal("100"),
            unit_price=Decimal("15.00")  # Gain: 500
        )

        disposals2 = calc.process_disposal(
            isin="IE00TEST002",
            disposal_date=date(2024, 6, 15),
            quantity=Decimal("50"),
            unit_price=Decimal("25.00")  # Gain: 250
        )

        result = calc.calculate_tax(2024, disposals1 + disposals2)

        assert result.disposal_gains == Decimal("750.00")
        # Tax = 750 * 0.41 = 307.50
        assert result.tax_due == Decimal("307.50")

    def test_fractional_units(self):
        """Test handling fractional unit quantities."""
        calc = ExitTaxCalculator()

        calc.add_acquisition(
            isin="IE00TEST001",
            name="Test ETF (Acc)",
            acquisition_date=date(2024, 1, 15),
            quantity=Decimal("10.5"),
            unit_cost=Decimal("100.00")
        )

        disposals = calc.process_disposal(
            isin="IE00TEST001",
            disposal_date=date(2024, 6, 15),
            quantity=Decimal("5.25"),
            unit_price=Decimal("120.00")
        )

        assert len(disposals) == 1
        assert disposals[0].quantity == Decimal("5.25")
        # Gain = 5.25 * (120 - 100) = 5.25 * 20 = 105
        assert disposals[0].gain_loss == Decimal("105.00")

    def test_zero_quantity_disposal(self):
        """Zero quantity disposal should work gracefully."""
        calc = ExitTaxCalculator()

        calc.add_acquisition(
            isin="IE00TEST001",
            name="Test ETF (Acc)",
            acquisition_date=date(2024, 1, 15),
            quantity=Decimal("100"),
            unit_cost=Decimal("10.00")
        )

        disposals = calc.process_disposal(
            isin="IE00TEST001",
            disposal_date=date(2024, 6, 15),
            quantity=Decimal("0"),
            unit_price=Decimal("15.00")
        )

        assert len(disposals) == 0
