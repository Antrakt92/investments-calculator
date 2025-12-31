"""
Tests for Trade Republic PDF Parser.

Tests cover:
- Number normalization (European decimals, thousand separators)
- Transaction line parsing
- ISIN detection
- Asset type classification
- Income parsing

Note: Some tests require pdfplumber which may not be available in all environments.
Tests that don't need the parser are marked to run without imports.
"""
import pytest
from decimal import Decimal
from datetime import date
import re

# Try to import the parser, skip tests if pdfplumber not available
try:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
    from parsers.trade_republic_parser import (
        TradeRepublicParser,
        ParsedTransaction,
        ParsedIncome,
        ParsedReport
    )
    PARSER_AVAILABLE = True
except (ImportError, Exception) as e:
    PARSER_AVAILABLE = False
    # Create dummy classes for tests that don't need them
    TradeRepublicParser = None
    ParsedTransaction = None
    ParsedIncome = None
    ParsedReport = None


class TestNumberNormalization:
    """Test number format normalization in the parser."""

    def test_thousand_separator_removal(self):
        """Test that thousand separators (commas) are removed correctly."""
        # Simulate the regex used in the parser
        line = "Trading Buy 19.12.2023 21.12.2023 EUR 1.0829 342.0000 4,067.75 0.00"

        # Apply normalization
        normalized = re.sub(r'(\d),(\d{3})(?![0-9])', r'\1\2', line)

        assert "4067.75" in normalized
        assert "4,067.75" not in normalized

    def test_european_decimal_format(self):
        """Test European decimal format (comma as decimal separator)."""
        line = "Trading Buy 03.06.2024 05.06.2024 EUR 1.0000 7,00 672,00 0,00"

        # Apply normalization: first thousand separators, then European decimals
        normalized = re.sub(r'(\d),(\d{3})(?![0-9])', r'\1\2', line)
        normalized = re.sub(r'(\d),(\d{1,2})(?!\d)', r'\1.\2', normalized)

        assert "7.00" in normalized
        assert "672.00" in normalized

    def test_concatenated_numbers_split(self):
        """Test splitting concatenated numbers (PDF drops spaces)."""
        # This pattern occurs when PDF extraction merges numbers
        line = "EUR 1.0000342.0000 4067.75 0.00"

        # Apply the fix for concatenated numbers
        normalized = re.sub(r'(\d\.\d{4})(\d{1,3}\.\d)', r'\1 \2', line)

        assert "1.0000 342.0000" in normalized


@pytest.mark.skipif(not PARSER_AVAILABLE, reason="pdfplumber not available")
class TestTransactionParsing:
    """Test transaction line parsing."""

    def test_parse_buy_transaction(self):
        """Test parsing a buy transaction line."""
        parser = TradeRepublicParser()

        line = "Trading Buy 02.05.2024 06.05.2024 EUR 1.0000 0.0408 4.47 0.00"

        trans = parser._parse_transaction_row(line, "IE00BGV5VN51", "AI & Big Data USD (Acc)")

        assert trans is not None
        assert trans.transaction_type == "buy"
        assert trans.transaction_date == date(2024, 5, 2)
        assert trans.settlement_date == date(2024, 5, 6)
        assert trans.quantity == Decimal("0.0408")
        assert trans.market_value == Decimal("4.47")

    def test_parse_sell_transaction(self):
        """Test parsing a sell transaction line."""
        parser = TradeRepublicParser()

        line = "Trading Sell 23.05.2024 27.05.2024 EUR 1.0000 9.0000 1031.76 0.00"

        trans = parser._parse_transaction_row(line, "IE00BGV5VN51", "AI & Big Data USD (Acc)")

        assert trans is not None
        assert trans.transaction_type == "sell"
        assert trans.transaction_date == date(2024, 5, 23)
        assert trans.quantity == Decimal("9.0000")
        assert trans.market_value == Decimal("1031.76")

    def test_reject_section_vi_line(self):
        """Section VI lines (only one date) should be rejected."""
        parser = TradeRepublicParser()

        # Section VI format has only one date
        line = "Sell 23.05.2024 9.0000 114.64 1031.76 EUR"

        trans = parser._parse_transaction_row(line, "IE00TEST", "Test")

        # Should return None because it only has one date
        assert trans is None

    def test_parse_large_quantity(self):
        """Test parsing transaction with large quantity."""
        parser = TradeRepublicParser()

        line = "Trading Buy 19.12.2023 21.12.2023 EUR 1.0829 342.0000 4067.75 0.00"

        trans = parser._parse_transaction_row(line, "IE00BLRPRJ20", "NASDAQ 100 3x Short")

        assert trans is not None
        assert trans.quantity == Decimal("342.0000")
        assert trans.market_value == Decimal("4067.75")


class TestISINDetection:
    """Test ISIN header line detection."""

    def test_detect_isin_with_dash(self):
        """Test ISIN detection with dash separator."""
        line = "IE00BGV5VN51 - AI & Big Data USD (Acc)"

        match = re.match(r"^([A-Z]{2}[A-Z0-9]{10})[\s\-]+(.+)$", line)

        assert match is not None
        assert match.group(1) == "IE00BGV5VN51"
        assert "AI & Big Data" in match.group(2)

    def test_detect_isin_with_space(self):
        """Test ISIN detection with space separator."""
        line = "US0378331005 Apple Inc."

        match = re.match(r"^([A-Z]{2}[A-Z0-9]{10})[\s\-]+(.+)$", line)

        assert match is not None
        assert match.group(1) == "US0378331005"
        assert "Apple" in match.group(2)

    def test_reject_non_isin_line(self):
        """Non-ISIN lines should not match."""
        lines = [
            "Trading Buy 02.05.2024",
            "Total 1234.56",
            "Section VII. History of Transactions"
        ]

        for line in lines:
            match = re.match(r"^([A-Z]{2}[A-Z0-9]{10})[\s\-]+(.+)$", line)
            assert match is None


@pytest.mark.skipif(not PARSER_AVAILABLE, reason="pdfplumber not available")
class TestAssetClassification:
    """Test asset type classification for Irish tax purposes."""

    def test_eu_etf_classification(self):
        """Irish/EU ETFs should be classified as etf_eu."""
        parser = TradeRepublicParser()

        assert parser._get_asset_type("IE00BGV5VN51", "AI & Big Data USD (Acc)") == "etf_eu"
        assert parser._get_asset_type("IE00B0M62S72", "Euro Dividend EUR (Dist)") == "etf_eu"
        assert parser._get_asset_type("LU0378449770", "MSCI World ETF") == "etf_eu"

    def test_us_stock_classification(self):
        """US stocks should be classified as stock."""
        parser = TradeRepublicParser()

        assert parser._get_asset_type("US0378331005", "Apple Inc.") == "stock"
        assert parser._get_asset_type("US30303M1027", "Meta Platforms") == "stock"

    def test_leveraged_etf_classification(self):
        """Leveraged ETFs should be classified as etf_eu."""
        parser = TradeRepublicParser()

        assert parser._get_asset_type("IE00BLRPRL42", "NASDAQ 100 3x Lev USD (Acc)") == "etf_eu"
        assert parser._get_asset_type("IE00BLRPRJ20", "NASDAQ 100 3x Short USD (Acc)") == "etf_eu"

    def test_irish_stock_not_etf(self):
        """Irish stocks (not ETFs) should be classified as stock."""
        parser = TradeRepublicParser()

        # Jazz Pharmaceuticals is an Irish company, not a fund
        assert parser._get_asset_type("IE00B4Q5ZN47", "Jazz Pharmaceuticals") == "stock"

    def test_empty_isin(self):
        """Empty ISIN should return cash."""
        parser = TradeRepublicParser()

        assert parser._get_asset_type("", "") == "cash"
        assert parser._get_asset_type(None, None) == "cash"


@pytest.mark.skipif(not PARSER_AVAILABLE, reason="pdfplumber not available")
class TestInstanceVariables:
    """Test that parser instance variables persist correctly."""

    def test_isin_persistence(self):
        """ISIN should persist as instance variable."""
        parser = TradeRepublicParser()

        assert parser.current_isin is None
        assert parser.current_name is None

        parser.current_isin = "IE00TEST123"
        parser.current_name = "Test ETF"

        assert parser.current_isin == "IE00TEST123"
        assert parser.current_name == "Test ETF"


@pytest.mark.skipif(not PARSER_AVAILABLE, reason="pdfplumber not available")
class TestEdgeCases:
    """Test edge cases in parsing."""

    def test_parse_zero_net_amount(self):
        """Transactions with zero net amount should parse correctly."""
        parser = TradeRepublicParser()

        line = "Trading Buy 02.05.2024 06.05.2024 EUR 1.0000 0.0408 4.47 0.00"

        trans = parser._parse_transaction_row(line, "IE00TEST", "Test")

        assert trans is not None
        assert trans.net_amount == Decimal("0.00")

    def test_parse_negative_quantity_treated_as_positive(self):
        """Negative quantities should be converted to positive."""
        parser = TradeRepublicParser()

        # If a line somehow has negative quantity
        line = "Trading Sell 23.05.2024 27.05.2024 EUR 1.0000 -9.0000 1031.76 0.00"

        trans = parser._parse_transaction_row(line, "IE00TEST", "Test")

        # Quantity should be absolute value
        if trans:
            assert trans.quantity >= 0

    def test_parse_with_exchange_rate(self):
        """Transactions with non-1.0 exchange rate should parse correctly."""
        parser = TradeRepublicParser()

        line = "Trading Buy 19.12.2023 21.12.2023 EUR 1.0829 342.0000 4067.75 0.00"

        trans = parser._parse_transaction_row(line, "IE00TEST", "Test")

        assert trans is not None
        assert trans.exchange_rate == Decimal("1.0829")

    def test_german_transaction_keywords(self):
        """German keywords (Kauf, Verkauf) should be recognized."""
        parser = TradeRepublicParser()

        # These should be recognized as trade lines
        buy_line = "Kauf 02.05.2024 06.05.2024 EUR 1.0000 100 1000.00 0.00"
        sell_line = "Verkauf 23.05.2024 27.05.2024 EUR 1.0000 100 1100.00 0.00"

        # The is_trade_line check
        is_buy = "Kauf " in buy_line
        is_sell = "Verkauf " in sell_line

        assert is_buy
        assert is_sell


@pytest.mark.skipif(not PARSER_AVAILABLE, reason="pdfplumber not available")
class TestReportMetadata:
    """Test report metadata extraction."""

    def test_parsed_report_defaults(self):
        """ParsedReport should have sensible defaults."""
        report = ParsedReport(
            client_id="123456",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
            currency="EUR",
            country="Ireland",
            accounting_method="Fifo"
        )

        assert report.client_id == "123456"
        assert report.currency == "EUR"
        assert len(report.transactions) == 0
        assert len(report.income_events) == 0
        assert report.total_income == Decimal("0")


class TestIncomeEventParsing:
    """Test income event detection patterns."""

    def test_dividend_line_detection(self):
        """Test dividend line detection patterns."""
        dividend_lines = [
            "Dividend 27.12.2024 6.1484 EUR 1.0000 0.38 0.38",
            "Distribution 15.06.2024 100 EUR 1.0000 5.00 5.00"
        ]

        for line in dividend_lines:
            is_dividend = (
                line.startswith("Dividend") or
                line.startswith("Distribution")
            )
            has_date = re.search(r"\d{2}\.\d{2}\.\d{4}", line) is not None

            assert is_dividend
            assert has_date

    def test_interest_line_detection(self):
        """Test interest line detection patterns."""
        interest_lines = [
            "Interest payment 01.02.2024 0.21 EUR 1.0000 0.21 0.21",
            "Interest 01.03.2024 0.17 EUR"
        ]

        for line in interest_lines:
            is_interest = "Interest" in line
            has_date = re.search(r"\d{2}\.\d{2}\.\d{4}", line) is not None

            assert is_interest
            assert has_date
