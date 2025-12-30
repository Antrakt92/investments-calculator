"""
Trade Republic Tax Report PDF Parser

Extracts data from Trade Republic annual tax reports for Irish tax calculations.
Sections parsed:
- Section V: Detailed Income (interest, dividends, distributions)
- Section VI: Detailed Gains and Losses
- Section VII: History of Transactions and Corporate Actions
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional
import pdfplumber


@dataclass
class ParsedTransaction:
    """Represents a parsed transaction from the PDF."""
    isin: str
    name: str
    transaction_type: str  # buy, sell
    transaction_date: date
    settlement_date: Optional[date]
    currency: str
    exchange_rate: Decimal
    quantity: Decimal
    market_value: Decimal
    net_amount: Decimal
    country: Optional[str] = None
    asset_type: Optional[str] = None


@dataclass
class ParsedIncome:
    """Represents parsed income event (interest, dividend, distribution)."""
    isin: Optional[str]
    name: str
    income_type: str
    payment_date: date
    quantity: Optional[Decimal]
    gross_amount: Decimal
    withholding_tax: Decimal
    net_amount: Decimal
    country: Optional[str] = None


@dataclass
class ParsedGainLoss:
    """Represents parsed realized gain/loss."""
    isin: str
    name: str
    transaction_date: date
    quantity: Decimal
    unit_price: Decimal
    gross_amount: Decimal
    net_amount: Decimal
    realized_gain_loss: Decimal
    fx_effect: Decimal
    gain_loss_without_fx: Decimal
    transaction_type: str
    country: Optional[str] = None
    asset_type: Optional[str] = None


@dataclass
class ParsedReport:
    """Complete parsed Trade Republic tax report."""
    client_id: str
    period_start: date
    period_end: date
    currency: str
    country: str
    accounting_method: str

    transactions: list[ParsedTransaction] = field(default_factory=list)
    income_events: list[ParsedIncome] = field(default_factory=list)
    gains_losses: list[ParsedGainLoss] = field(default_factory=list)

    total_income: Decimal = Decimal("0")
    total_gains: Decimal = Decimal("0")
    total_losses: Decimal = Decimal("0")


class TradeRepublicParser:
    """Parser for Trade Republic annual tax report PDFs."""

    def __init__(self):
        self.current_isin = None
        self.current_name = None

    def parse(self, pdf_path: str | Path) -> ParsedReport:
        """Parse a Trade Republic tax report PDF."""
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        report = None

        with pdfplumber.open(pdf_path) as pdf:
            # Extract metadata from page 2
            report = self._parse_metadata(pdf.pages[1])

            # Parse all pages
            full_text = ""
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"

            # Parse Section V - Income
            self._parse_income_section(full_text, report)

            # Parse Section VII - Transactions (using table extraction)
            for page in pdf.pages:
                text = page.extract_text() or ""
                if "VII. History of Transactions" in text or "History of Transactions" in text:
                    self._parse_transactions_table(page, report)

        # Classify assets for Irish tax purposes
        self._classify_assets(report)

        return report

    def _parse_metadata(self, page) -> ParsedReport:
        """Extract report metadata from page 2."""
        text = page.extract_text() or ""

        client_match = re.search(r"Client:\s*(\d+)", text)
        client_id = client_match.group(1) if client_match else "unknown"

        period_match = re.search(r"Period:\s*(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})", text)
        if period_match:
            period_start = datetime.strptime(period_match.group(1), "%d.%m.%Y").date()
            period_end = datetime.strptime(period_match.group(2), "%d.%m.%Y").date()
        else:
            period_start = date(2024, 1, 1)
            period_end = date(2024, 12, 31)

        currency_match = re.search(r"Currency:\s*(\w+)", text)
        currency = currency_match.group(1) if currency_match else "EUR"

        country_match = re.search(r"Country:\s*(\w+)", text)
        country = country_match.group(1) if country_match else "Ireland"

        method_match = re.search(r"Accounting\s*Method:\s*(\w+)", text)
        accounting_method = method_match.group(1) if method_match else "Fifo"

        return ParsedReport(
            client_id=client_id,
            period_start=period_start,
            period_end=period_end,
            currency=currency,
            country=country,
            accounting_method=accounting_method
        )

    def _parse_income_section(self, full_text: str, report: ParsedReport):
        """Parse income section from full text."""
        lines = full_text.split("\n")
        current_isin = None
        current_name = None

        for i, line in enumerate(lines):
            # Detect ISIN lines
            isin_match = re.match(r"^([A-Z]{2}[A-Z0-9]{10})\s*-\s*(.+)$", line.strip())
            if isin_match:
                current_isin = isin_match.group(1)
                current_name = isin_match.group(2).strip()
                # Clean name - remove trailing (Acc), (Dist), etc. info we don't need
                if " - " in current_name:
                    current_name = current_name.split(" - ")[0].strip()
                continue

            # Parse interest payment lines
            # Format: Interest payment 01.02.2024 0.21 EUR 1.0000 0.21 0.21
            if "Interest payment" in line:
                match = re.search(r"Interest payment\s+(\d{2}\.\d{2}\.\d{4})\s+([\d.]+)", line)
                if match:
                    payment_date = datetime.strptime(match.group(1), "%d.%m.%Y").date()
                    amount = Decimal(match.group(2))
                    report.income_events.append(ParsedIncome(
                        isin=None,
                        name="Trade Republic Interest",
                        income_type="Interest",
                        payment_date=payment_date,
                        quantity=None,
                        gross_amount=amount,
                        withholding_tax=Decimal("0"),
                        net_amount=amount,
                        country="Germany"
                    ))

            # Parse dividend lines
            # Format: Dividend 27.12.2024 6.1484 EUR 1.0000 0.38 0.38
            if line.strip().startswith("Dividend") and current_isin:
                match = re.search(r"Dividend\s+(\d{2}\.\d{2}\.\d{4})\s+([\d.]+)\s+\w+\s+[\d.]+\s+([\d.]+)", line)
                if match:
                    payment_date = datetime.strptime(match.group(1), "%d.%m.%Y").date()
                    quantity = Decimal(match.group(2))
                    gross_amount = Decimal(match.group(3))
                    report.income_events.append(ParsedIncome(
                        isin=current_isin,
                        name=current_name or "Unknown Fund",
                        income_type="Distribution",
                        payment_date=payment_date,
                        quantity=quantity,
                        gross_amount=gross_amount,
                        withholding_tax=Decimal("0"),
                        net_amount=gross_amount,
                        country="Ireland"
                    ))

    def _parse_transactions_table(self, page, report: ParsedReport):
        """Parse transaction history using table extraction."""
        text = page.extract_text() or ""
        lines = text.split("\n")

        current_isin = None
        current_name = None

        for line in lines:
            line = line.strip()

            # Detect ISIN header lines
            # Format: IE00BGV5VN51 - AI & Big Data USD (Acc)
            isin_match = re.match(r"^([A-Z]{2}[A-Z0-9]{10})\s*-\s*(.+)$", line)
            if isin_match:
                current_isin = isin_match.group(1)
                current_name = isin_match.group(2).strip()
                continue

            # Parse transaction lines
            # Format: Trading Buy 02.05.2024 06.05.2024 EUR 1.0000 0.0408 4.47 0.00
            if line.startswith("Trading Buy") or line.startswith("Trading Sell"):
                trans = self._parse_transaction_row(line, current_isin, current_name)
                if trans:
                    report.transactions.append(trans)

    def _parse_transaction_row(self, line: str, isin: str, name: str) -> Optional[ParsedTransaction]:
        """Parse a single transaction row."""
        try:
            trans_type = "buy" if "Buy" in line else "sell"

            # Extract all dates (DD.MM.YYYY format)
            dates = re.findall(r"(\d{2}\.\d{2}\.\d{4})", line)
            if len(dates) < 2:
                return None

            trans_date = datetime.strptime(dates[0], "%d.%m.%Y").date()
            settle_date = datetime.strptime(dates[1], "%d.%m.%Y").date()

            # Remove the "Trading Buy/Sell" prefix and dates to get the numbers
            # Line format after dates: EUR 1.0000 quantity market_value net_amount
            # Example: Trading Buy 02.05.2024 06.05.2024 EUR 1.0000 0.0408 4.47 0.00

            # Find the position after the second date
            pattern = r"Trading (?:Buy|Sell)\s+\d{2}\.\d{2}\.\d{4}\s+\d{2}\.\d{2}\.\d{4}\s+(\w+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"
            match = re.search(pattern, line)

            if match:
                currency = match.group(1)
                exchange_rate = Decimal(match.group(2))
                quantity = Decimal(match.group(3))
                market_value = Decimal(match.group(4))
                net_amount = Decimal(match.group(5))
            else:
                # Fallback: extract all decimal numbers after the dates
                # Remove dates from consideration
                remainder = line
                for d in dates:
                    remainder = remainder.replace(d, "")

                # Find all decimal numbers
                numbers = re.findall(r"(\d+\.\d+|\d+)", remainder)
                numbers = [Decimal(n) for n in numbers if n not in ["Buy", "Sell", "Trading"]]

                if len(numbers) < 3:
                    return None

                # Assume: exchange_rate (usually 1.0000), quantity, market_value, net_amount
                # Filter out 1.0000 if it appears (exchange rate)
                if numbers[0] == Decimal("1") or (len(str(numbers[0])) >= 6 and "1.0000" in str(numbers[0])):
                    numbers = numbers[1:]

                if len(numbers) < 2:
                    return None

                quantity = numbers[0]
                market_value = numbers[1]
                net_amount = numbers[2] if len(numbers) > 2 else Decimal("0")
                exchange_rate = Decimal("1.0000")
                currency = "EUR"

            return ParsedTransaction(
                isin=isin or "",
                name=name or "",
                transaction_type=trans_type,
                transaction_date=trans_date,
                settlement_date=settle_date,
                currency=currency,
                exchange_rate=exchange_rate,
                quantity=abs(quantity),
                market_value=abs(market_value),
                net_amount=abs(net_amount),
                country=None,
                asset_type=None
            )

        except Exception as e:
            print(f"Error parsing transaction: {line} - {e}")
            return None

    def _classify_assets(self, report: ParsedReport):
        """Classify assets for Irish tax purposes."""
        for trans in report.transactions:
            trans.asset_type = self._get_asset_type(trans.isin, trans.name)

        for gl in report.gains_losses:
            gl.asset_type = self._get_asset_type(gl.isin, gl.name)

    def _get_asset_type(self, isin: str, name: str) -> str:
        """Determine asset type from ISIN and name."""
        if not isin:
            return "cash"

        prefix = isin[:2]
        name_lower = name.lower() if name else ""

        # EU fund countries where Exit Tax applies
        eu_fund_countries = ["IE", "LU", "DE", "FR", "NL", "AT"]

        # Keywords indicating a fund/ETF
        fund_keywords = [
            "etf", "fund", "ucits", "acc", "dist", "index", "tracker",
            "ishares", "vanguard", "amundi", "xtrackers", "lyxor",
            "3x", "2x", "leveraged", "short", "nasdaq", "s&p",
            "msci", "ftse", "floating rate", "bond usd", "big data",
            "money market", "dividend eur"
        ]

        is_fund = any(kw in name_lower for kw in fund_keywords)

        # Special case: Jazz Pharmaceuticals is a STOCK (IE00B4Q5ZN47), not a fund
        if "jazz" in name_lower or "pharmaceuticals" in name_lower:
            return "stock"

        if is_fund and prefix in eu_fund_countries:
            return "etf_eu"  # Exit Tax 41%
        elif is_fund and prefix == "US":
            return "etf_non_eu"  # CGT 33%
        elif prefix in ["US", "KY"]:  # US stocks, Cayman Islands ADRs
            return "stock"  # CGT 33%
        elif prefix in eu_fund_countries:
            if is_fund:
                return "etf_eu"
            return "stock"
        else:
            return "stock"


def parse_trade_republic_pdf(pdf_path: str | Path) -> ParsedReport:
    """Convenience function to parse a Trade Republic PDF."""
    parser = TradeRepublicParser()
    return parser.parse(pdf_path)
