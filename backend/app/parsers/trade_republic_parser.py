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
    transaction_type: str  # Trading Buy, Trading Sell, Dividend, Interest payment, etc.
    transaction_date: date
    settlement_date: Optional[date]
    currency: str
    exchange_rate: Decimal
    quantity: Decimal
    market_value: Decimal
    net_amount: Decimal
    country: Optional[str] = None
    asset_type: Optional[str] = None  # Equities, Funds, Liquidity


@dataclass
class ParsedIncome:
    """Represents parsed income event (interest, dividend, distribution)."""
    isin: Optional[str]
    name: str
    income_type: str  # Interest, Dividend, Distribution
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
    transaction_type: str  # Trading Buy, Trading Sell
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

    # Summary totals from the report
    total_income: Decimal = Decimal("0")
    total_gains: Decimal = Decimal("0")
    total_losses: Decimal = Decimal("0")


class TradeRepublicParser:
    """Parser for Trade Republic annual tax report PDFs."""

    def __init__(self):
        self.current_section = None
        self.current_asset_type = None
        self.current_country = None
        self.current_isin = None
        self.current_name = None

    def parse(self, pdf_path: str | Path) -> ParsedReport:
        """Parse a Trade Republic tax report PDF."""
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        report = None

        with pdfplumber.open(pdf_path) as pdf:
            # First pass: extract metadata from page 2
            report = self._parse_metadata(pdf.pages[1])

            # Parse each page
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""

                # Detect section changes
                self._detect_section(text)

                # Parse based on current section
                if "V. Detailed Income Section" in text or self.current_section == "income":
                    self._parse_income_page(page, report)

                if "VI. Detailed Gains and Losses Section" in text or self.current_section == "gains_losses":
                    self._parse_gains_losses_page(page, report)

                if "VII. History of Transactions" in text or self.current_section == "transactions":
                    self._parse_transactions_page(page, report)

        # Classify assets for Irish tax purposes
        self._classify_assets(report)

        return report

    def _parse_metadata(self, page) -> ParsedReport:
        """Extract report metadata from page 2."""
        text = page.extract_text() or ""

        # Extract client ID
        client_match = re.search(r"Client:\s*(\d+)", text)
        client_id = client_match.group(1) if client_match else "unknown"

        # Extract period
        period_match = re.search(r"Period:\s*(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})", text)
        if period_match:
            period_start = datetime.strptime(period_match.group(1), "%d.%m.%Y").date()
            period_end = datetime.strptime(period_match.group(2), "%d.%m.%Y").date()
        else:
            period_start = date(2024, 1, 1)
            period_end = date(2024, 12, 31)

        # Extract currency and country
        currency_match = re.search(r"Currency:\s*(\w+)", text)
        currency = currency_match.group(1) if currency_match else "EUR"

        country_match = re.search(r"Country:\s*(\w+)", text)
        country = country_match.group(1) if country_match else "Ireland"

        # Accounting method
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

    def _detect_section(self, text: str):
        """Detect which section we're currently in."""
        if "V. Detailed Income Section" in text:
            self.current_section = "income"
        elif "VI. Detailed Gains and Losses Section" in text:
            self.current_section = "gains_losses"
        elif "VII. History of Transactions" in text:
            self.current_section = "transactions"
        elif "VIII. Explanatory Notes" in text or "Explanatory Notes" in text:
            self.current_section = "notes"

    def _parse_income_page(self, page, report: ParsedReport):
        """Parse income section (Section V)."""
        text = page.extract_text() or ""
        lines = text.split("\n")

        for i, line in enumerate(lines):
            # Detect asset type
            if "Asset Type:" in line:
                if "Liquidity" in line:
                    self.current_asset_type = "Liquidity"
                elif "Funds" in line:
                    self.current_asset_type = "Funds"
                continue

            # Detect country
            if line.startswith("Country:"):
                self.current_country = line.replace("Country:", "").strip()
                continue

            # Detect ISIN line (starts with IE, US, DE, LU, etc.)
            isin_match = re.match(r"^([A-Z]{2}[A-Z0-9]{10})\s*-\s*(.+)$", line.strip())
            if isin_match:
                self.current_isin = isin_match.group(1)
                self.current_name = isin_match.group(2).strip()
                continue

            # Parse interest payment lines
            if "Interest payment" in line:
                income = self._parse_interest_line(line, lines, i)
                if income:
                    report.income_events.append(income)

            # Parse dividend lines
            if line.strip().startswith("Dividend"):
                income = self._parse_dividend_line(line, lines, i)
                if income:
                    report.income_events.append(income)

    def _parse_interest_line(self, line: str, lines: list, idx: int) -> Optional[ParsedIncome]:
        """Parse an interest payment line."""
        # Format: Interest payment 01.02.2024 0.21 EUR 1.0000 0.21 0.21
        pattern = r"Interest payment\s+(\d{2}\.\d{2}\.\d{4})\s+([\d.]+)\s+EUR"
        match = re.search(pattern, line)
        if match:
            payment_date = datetime.strptime(match.group(1), "%d.%m.%Y").date()
            amount = Decimal(match.group(2))

            return ParsedIncome(
                isin=None,  # Liquidity doesn't have ISIN
                name="Trade Republic Interest",
                income_type="Interest",
                payment_date=payment_date,
                quantity=None,
                gross_amount=amount,
                withholding_tax=Decimal("0"),
                net_amount=amount,
                country=self.current_country or "Germany"
            )
        return None

    def _parse_dividend_line(self, line: str, lines: list, idx: int) -> Optional[ParsedIncome]:
        """Parse a dividend/distribution line."""
        # Format: Dividend 27.12.2024 6.1484 EUR 1.0000 0.38 0.38
        pattern = r"Dividend\s+(\d{2}\.\d{2}\.\d{4})\s+([\d.]+)\s+EUR\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"
        match = re.search(pattern, line)
        if match:
            payment_date = datetime.strptime(match.group(1), "%d.%m.%Y").date()
            quantity = Decimal(match.group(2))
            gross_amount = Decimal(match.group(4))
            net_amount = Decimal(match.group(5))

            return ParsedIncome(
                isin=self.current_isin,
                name=self.current_name or "Unknown Fund",
                income_type="Distribution",
                payment_date=payment_date,
                quantity=quantity,
                gross_amount=gross_amount,
                withholding_tax=Decimal("0"),
                net_amount=net_amount,
                country=self.current_country
            )
        return None

    def _parse_gains_losses_page(self, page, report: ParsedReport):
        """Parse gains and losses section (Section VI)."""
        tables = page.extract_tables()

        for table in tables:
            if not table or len(table) < 2:
                continue

            for row in table[1:]:  # Skip header
                if not row or len(row) < 5:
                    continue

                parsed = self._parse_gain_loss_row(row)
                if parsed:
                    report.gains_losses.append(parsed)

    def _parse_gain_loss_row(self, row: list) -> Optional[ParsedGainLoss]:
        """Parse a single gain/loss row."""
        try:
            # Clean row data
            row = [str(cell).strip() if cell else "" for cell in row]

            # Skip if not a trading row
            if not any(t in row[0] for t in ["Trading Buy", "Trading Sell"]):
                return None

            transaction_type = "buy" if "Buy" in row[0] else "sell"

            # Extract date
            date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", row[1] if len(row) > 1 else "")
            if not date_match:
                return None
            trans_date = datetime.strptime(date_match.group(1), "%d.%m.%Y").date()

            # Extract quantity
            quantity = self._parse_decimal(row[2]) if len(row) > 2 else Decimal("0")

            # Extract price
            unit_price = self._parse_decimal(row[4]) if len(row) > 4 else Decimal("0")

            # Extract amounts
            gross_amount = self._parse_decimal(row[7]) if len(row) > 7 else Decimal("0")
            net_amount = self._parse_decimal(row[8]) if len(row) > 8 else Decimal("0")

            # Extract realized gain/loss
            realized_gl = self._parse_decimal(row[9]) if len(row) > 9 else Decimal("0")
            fx_effect = self._parse_decimal(row[10]) if len(row) > 10 else Decimal("0")
            gl_no_fx = self._parse_decimal(row[11]) if len(row) > 11 else Decimal("0")

            return ParsedGainLoss(
                isin=self.current_isin or "",
                name=self.current_name or "",
                transaction_date=trans_date,
                quantity=abs(quantity),
                unit_price=unit_price,
                gross_amount=gross_amount,
                net_amount=net_amount,
                realized_gain_loss=realized_gl,
                fx_effect=fx_effect,
                gain_loss_without_fx=gl_no_fx,
                transaction_type=transaction_type,
                country=self.current_country,
                asset_type=self.current_asset_type
            )
        except (ValueError, InvalidOperation) as e:
            return None

    def _parse_transactions_page(self, page, report: ParsedReport):
        """Parse transaction history section (Section VII)."""
        text = page.extract_text() or ""
        lines = text.split("\n")

        for i, line in enumerate(lines):
            # Detect ISIN lines
            isin_match = re.match(r"^([A-Z]{2}[A-Z0-9]{10})\s*-\s*(.+)$", line.strip())
            if isin_match:
                self.current_isin = isin_match.group(1)
                self.current_name = isin_match.group(2).strip()
                continue

            # Parse transaction lines
            if line.strip().startswith(("Trading Buy", "Trading Sell")):
                trans = self._parse_transaction_line(line)
                if trans:
                    report.transactions.append(trans)

    def _parse_transaction_line(self, line: str) -> Optional[ParsedTransaction]:
        """Parse a transaction line from Section VII."""
        try:
            # Transaction format varies, try to extract key fields
            trans_type = "buy" if "Buy" in line else "sell"

            # Extract dates
            dates = re.findall(r"(\d{2}\.\d{2}\.\d{4})", line)
            if not dates:
                return None

            trans_date = datetime.strptime(dates[0], "%d.%m.%Y").date()
            settle_date = datetime.strptime(dates[1], "%d.%m.%Y").date() if len(dates) > 1 else None

            # Extract numbers after dates
            # Pattern: date date EUR 1.0000 quantity market_value net_amount
            numbers = re.findall(r"([-]?\d+\.?\d*)", line)
            # Filter out year numbers from dates
            numbers = [n for n in numbers if len(n) <= 10 and n not in ["2023", "2024"]]

            if len(numbers) < 3:
                return None

            # Try to identify quantity and amounts
            exchange_rate = Decimal("1.0000")
            for n in numbers:
                if n == "1.0000":
                    exchange_rate = Decimal(n)
                    break

            # Find quantity (usually has many decimals for fractional shares)
            quantity = Decimal("0")
            market_value = Decimal("0")

            # Simple heuristic: quantity is usually the first significant number after exchange rate
            numeric_values = []
            for n in numbers:
                try:
                    val = Decimal(n)
                    if val != exchange_rate and abs(val) > 0:
                        numeric_values.append(val)
                except:
                    continue

            if len(numeric_values) >= 2:
                quantity = numeric_values[0]
                market_value = numeric_values[1]

            return ParsedTransaction(
                isin=self.current_isin or "",
                name=self.current_name or "",
                transaction_type=trans_type,
                transaction_date=trans_date,
                settlement_date=settle_date,
                currency="EUR",
                exchange_rate=exchange_rate,
                quantity=abs(quantity),
                market_value=abs(market_value),
                net_amount=Decimal("0"),
                country=self.current_country,
                asset_type=self.current_asset_type
            )
        except Exception:
            return None

    def _parse_decimal(self, value: str) -> Decimal:
        """Safely parse a decimal value."""
        if not value:
            return Decimal("0")
        # Clean the string
        cleaned = str(value).strip().replace(",", "")
        # Remove currency symbols
        cleaned = re.sub(r"[€$£]", "", cleaned)
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return Decimal("0")

    def _classify_assets(self, report: ParsedReport):
        """
        Classify assets for Irish tax purposes based on ISIN.

        Irish tax classification:
        - IE, LU, DE (funds) -> Exit Tax 41%
        - US (stocks) -> CGT 33%
        - US (ETFs) -> CGT 33% (not Exit Tax as not EU domiciled)
        - Other stocks -> CGT 33%
        """
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

        # EU domiciled funds (Exit Tax applies)
        eu_fund_countries = ["IE", "LU", "DE", "FR", "NL", "AT"]

        # Check if it's a fund/ETF based on name keywords
        fund_keywords = ["etf", "fund", "ucits", "acc", "dist", "index", "tracker",
                        "ishares", "vanguard", "amundi", "xtrackers", "lyxor",
                        "3x", "2x", "leveraged", "short", "nasdaq", "s&p"]

        is_fund = any(kw in name_lower for kw in fund_keywords)

        if is_fund and prefix in eu_fund_countries:
            return "etf_eu"  # Exit Tax 41%
        elif is_fund and prefix == "US":
            return "etf_non_eu"  # CGT 33%
        elif prefix in ["US", "KY", "CA"]:  # Cayman Islands ADRs etc.
            return "stock"  # CGT 33%
        elif prefix in eu_fund_countries:
            # Could be stock or fund - check name
            if is_fund:
                return "etf_eu"
            return "stock"
        else:
            return "stock"  # Default to stock (CGT)


def parse_trade_republic_pdf(pdf_path: str | Path) -> ParsedReport:
    """Convenience function to parse a Trade Republic PDF."""
    parser = TradeRepublicParser()
    return parser.parse(pdf_path)
