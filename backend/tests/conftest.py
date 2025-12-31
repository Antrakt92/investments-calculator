"""
Pytest configuration and fixtures.
"""
import pytest
from decimal import Decimal
from datetime import date
from pathlib import Path


@pytest.fixture
def sample_transaction_data():
    """Sample transaction data for testing."""
    return {
        "isin": "US0378331005",
        "name": "Apple Inc.",
        "quantity": Decimal("10"),
        "unit_cost": Decimal("150.00"),
        "total_cost": Decimal("1500.00"),
        "date": date(2024, 1, 15)
    }


@pytest.fixture
def sample_eu_etf_data():
    """Sample EU ETF data (Exit Tax applies)."""
    return {
        "isin": "IE00BGV5VN51",
        "name": "AI & Big Data USD (Acc)",
        "quantity": Decimal("5"),
        "unit_cost": Decimal("110.00"),
        "total_cost": Decimal("550.00"),
        "date": date(2024, 3, 1)
    }


@pytest.fixture
def test_pdf_path():
    """Path to test PDF files (if available)."""
    return Path(__file__).parent / "fixtures" / "test_report.pdf"


# Create fixtures directory
Path(__file__).parent.joinpath("fixtures").mkdir(exist_ok=True)
