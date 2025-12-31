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
            # Extract metadata from page 2 (or page 1 if only one page)
            report = self._parse_metadata(pdf.pages[min(1, len(pdf.pages) - 1)])

            # Parse all pages
            full_text = ""
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"

            # Parse Section V - Income (interest, dividends, distributions)
            self._parse_income_section(full_text, report)

            # Parse Section VII - Transactions
            in_transaction_section = False
            for page in pdf.pages:
                text = page.extract_text() or ""

                # Check if this page contains transaction section
                if "VII. History of Transactions" in text or "History of Transactions" in text:
                    in_transaction_section = True

                if in_transaction_section:
                    # Try table extraction first (more reliable for structured data)
                    table_trans_count = self._parse_transactions_from_tables(page, report)

                    # If no transactions found via table extraction, fall back to text parsing
                    if table_trans_count == 0:
                        self._parse_transactions_table(page, report)

        # Log parsing summary
        print(f"Parsed {len(report.transactions)} transactions, {len(report.income_events)} income events")

        # Classify assets for Irish tax purposes
        self._classify_assets(report)

        return report

    def _parse_transactions_from_tables(self, page, report: ParsedReport) -> int:
        """Extract transactions using pdfplumber table extraction."""
        tables = page.extract_tables()
        if not tables:
            return 0

        transactions_added = 0
        current_isin = None
        current_name = None

        for table in tables:
            for row in table:
                if not row or all(cell is None or cell == "" for cell in row):
                    continue

                # Join row cells and clean
                row_text = " ".join(str(cell) if cell else "" for cell in row).strip()

                # Check for ISIN header
                isin_match = re.match(r"^([A-Z]{2}[A-Z0-9]{10})[\s\-]+(.+)$", row_text)
                if isin_match:
                    current_isin = isin_match.group(1)
                    current_name = isin_match.group(2).strip().lstrip("- ")
                    continue

                # Check for transaction row
                if any(kw in row_text for kw in ["Trading Buy", "Trading Sell", "Buy ", "Sell ", "Kauf ", "Verkauf "]):
                    trans = self._parse_transaction_row(row_text, current_isin, current_name)
                    if trans and trans.market_value > Decimal("0"):
                        report.transactions.append(trans)
                        transactions_added += 1

        return transactions_added

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
            line_stripped = line.strip()

            # Detect ISIN lines - multiple formats
            # Format 1: IE00BGV5VN51 - AI & Big Data USD (Acc)
            # Format 2: IE00BGV5VN51 AI & Big Data USD (Acc)
            isin_match = re.match(r"^([A-Z]{2}[A-Z0-9]{10})[\s\-]+(.+)$", line_stripped)
            if isin_match:
                current_isin = isin_match.group(1)
                current_name = isin_match.group(2).strip()
                # Clean name - remove leading dash if present
                current_name = current_name.lstrip("- ").strip()
                # Clean name - remove trailing info like (Acc), (Dist) but keep main name
                if " - " in current_name:
                    current_name = current_name.split(" - ")[0].strip()
                continue

            # Parse interest payment lines
            # Format: Interest payment 01.02.2024 0.21 EUR 1.0000 0.21 0.21
            # Format: Interest 01.02.2024 0.21 EUR
            if "Interest" in line_stripped and ("payment" in line_stripped.lower() or re.search(r"\d{2}\.\d{2}\.\d{4}", line_stripped)):
                match = re.search(r"Interest(?:\s+payment)?\s+(\d{2}\.\d{2}\.\d{4})\s+([\d.,]+)", line_stripped)
                if match:
                    try:
                        payment_date = datetime.strptime(match.group(1), "%d.%m.%Y").date()
                        # Handle comma as decimal separator
                        amount_str = match.group(2).replace(",", ".")
                        amount = Decimal(amount_str)
                        if amount > Decimal("0"):
                            report.income_events.append(ParsedIncome(
                                isin=None,
                                name="Trade Republic Interest",
                                income_type="interest",
                                payment_date=payment_date,
                                quantity=None,
                                gross_amount=amount,
                                withholding_tax=Decimal("0"),
                                net_amount=amount,
                                country="Germany"
                            ))
                    except Exception as e:
                        print(f"Error parsing interest line: {line} - {e}")

            # Parse dividend/distribution lines - multiple formats supported
            # Format 1: Dividend 27.12.2024 6.1484 EUR 1.0000 0.38 0.38
            # Format 2: Dividend 27.12.2024 0.38 EUR
            # Format 3: Distribution 27.12.2024 ...
            # Format 4: Ausschüttung (German for distribution)
            is_dividend_line = (
                line_stripped.startswith("Dividend") or
                line_stripped.startswith("Distribution") or
                line_stripped.startswith("Ausschüttung") or
                ("Dividend" in line and "payment" not in line.lower() and re.search(r"\d{2}\.\d{2}\.\d{4}", line)) or
                ("Distribution" in line and "payment" not in line.lower() and re.search(r"\d{2}\.\d{2}\.\d{4}", line))
            )

            if is_dividend_line:
                # Try to extract date and amounts
                date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", line)
                if date_match:
                    try:
                        payment_date = datetime.strptime(date_match.group(1), "%d.%m.%Y").date()

                        # Try the original precise pattern first
                        # Format: Dividend DD.MM.YYYY quantity currency rate gross_amount net_amount
                        match = re.search(r"(Dividend|Distribution|Ausschüttung)\s+\d{2}\.\d{2}\.\d{4}\s+([\d.,]+)\s+\w{3}\s+[\d.,]+\s+([\d.,]+)", line)
                        if match:
                            quantity = Decimal(match.group(2).replace(",", "."))
                            gross_amount = Decimal(match.group(3).replace(",", "."))
                        else:
                            # Fallback: extract all numbers after the date
                            after_date = line[date_match.end():]
                            # Handle comma as decimal separator and find numbers
                            numbers = re.findall(r"([\d]+[.,][\d]+|[\d]+)", after_date)

                            amounts = []
                            for n in numbers:
                                try:
                                    val = Decimal(n.replace(",", "."))
                                    if val > Decimal("0") and val < Decimal("100000"):
                                        amounts.append(val)
                                except:
                                    pass

                            if not amounts:
                                continue

                            # Typically format is: quantity currency rate gross_amount net_amount
                            # Get gross amount (usually second-to-last or last significant amount)
                            if len(amounts) >= 2:
                                # If last two are the same, that's gross and net
                                if amounts[-1] == amounts[-2]:
                                    gross_amount = amounts[-1]
                                else:
                                    # Otherwise take the larger of the last two (gross is before net)
                                    gross_amount = max(amounts[-2], amounts[-1])
                                quantity = amounts[0] if len(amounts) > 2 else None
                            else:
                                gross_amount = amounts[0]
                                quantity = None

                        if gross_amount > Decimal("0"):
                            income_type = "dividend" if "Dividend" in line else "distribution"
                            # Use the current ISIN/name or try to find it from context
                            isin_to_use = current_isin
                            name_to_use = current_name or "Unknown Fund"

                            # Determine country based on ISIN prefix
                            country = "Unknown"
                            if isin_to_use:
                                prefix = isin_to_use[:2]
                                if prefix == "IE":
                                    country = "Ireland"
                                elif prefix == "LU":
                                    country = "Luxembourg"
                                elif prefix == "DE":
                                    country = "Germany"
                                elif prefix == "US":
                                    country = "USA"

                            report.income_events.append(ParsedIncome(
                                isin=isin_to_use,
                                name=name_to_use,
                                income_type=income_type,
                                payment_date=payment_date,
                                quantity=Decimal(str(quantity)) if quantity else None,
                                gross_amount=gross_amount,
                                withholding_tax=Decimal("0"),
                                net_amount=gross_amount,
                                country=country
                            ))
                    except Exception as e:
                        print(f"Error parsing dividend line: {line} - {e}")

    def _parse_transactions_table(self, page, report: ParsedReport):
        """Parse transaction history using table extraction."""
        text = page.extract_text() or ""
        lines = text.split("\n")

        current_isin = None
        current_name = None

        for line in lines:
            line = line.strip()

            # Detect ISIN header lines - multiple formats
            # Format 1: IE00BGV5VN51 - AI & Big Data USD (Acc)
            # Format 2: IE00BGV5VN51 AI & Big Data USD (Acc)
            # Format 3: US76954A1034 - Rivian Automotive, Inc.
            isin_match = re.match(r"^([A-Z]{2}[A-Z0-9]{10})[\s\-]+(.+)$", line)
            if isin_match:
                current_isin = isin_match.group(1)
                current_name = isin_match.group(2).strip()
                # Clean name - remove leading dash/spaces
                current_name = current_name.lstrip("- ").strip()
                continue

            # Parse transaction lines - multiple formats
            # Format 1: Trading Buy 02.05.2024 06.05.2024 EUR 1.0000 0.0408 4.47 0.00
            # Format 2: Buy 02.05.2024 06.05.2024 EUR 1.0000 0.0408 4.47 0.00
            # Format 3: Kauf/Verkauf (German)
            is_trade_line = (
                line.startswith("Trading Buy") or
                line.startswith("Trading Sell") or
                line.startswith("Buy ") or
                line.startswith("Sell ") or
                line.startswith("Kauf ") or
                line.startswith("Verkauf ")
            )

            if is_trade_line:
                trans = self._parse_transaction_row(line, current_isin, current_name)
                if trans and trans.market_value > Decimal("0"):
                    report.transactions.append(trans)
                elif trans:
                    print(f"Skipping transaction with zero market value: {line}")

    def _parse_transaction_row(self, line: str, isin: str, name: str) -> Optional[ParsedTransaction]:
        """Parse a single transaction row."""
        try:
            # Determine transaction type - handle German variants too
            trans_type = "buy" if any(kw in line for kw in ["Buy", "Kauf"]) else "sell"

            # Extract all dates (DD.MM.YYYY format)
            dates = re.findall(r"(\d{2}\.\d{2}\.\d{4})", line)
            if len(dates) < 1:
                return None

            trans_date = datetime.strptime(dates[0], "%d.%m.%Y").date()
            settle_date = datetime.strptime(dates[1], "%d.%m.%Y").date() if len(dates) >= 2 else trans_date

            # Normalize the line for number extraction
            # Step 1: Remove thousand separators
            # Handle: 2,146.00 -> 2146.00, 2 146.00 -> 2146.00
            normalized_line = line
            normalized_line = re.sub(r'(\d),(\d{3})(?![0-9])', r'\1\2', normalized_line)  # 2,146.00 -> 2146.00
            normalized_line = re.sub(r'(\d)\s+(\d{3})(?!\d)', r'\1\2', normalized_line)

            # Try multiple patterns to extract the values

            # Pattern 1: Trading Buy/Sell DATE DATE EUR rate quantity value net
            # Example: Trading Buy 02.05.2024 06.05.2024 EUR 1.0000 0.0408 4.47 0.00
            pattern1 = r"(?:Trading\s+)?(?:Buy|Sell|Kauf|Verkauf)\s+\d{2}\.\d{2}\.\d{4}\s+\d{2}\.\d{2}\.\d{4}\s+(\w{3})\s+([\d.]+)\s+([-]?[\d.]+)\s+([\d.]+)\s+([\d.]+)"
            match = re.search(pattern1, normalized_line, re.IGNORECASE)

            if match:
                currency = match.group(1)
                exchange_rate = Decimal(match.group(2))
                quantity = Decimal(match.group(3))
                market_value = Decimal(match.group(4))
                net_amount = Decimal(match.group(5))
            else:
                # Pattern 2: Just find EUR followed by numbers
                # EUR exchange_rate quantity market_value net_amount
                pattern2 = r"(\w{3})\s+([\d.]+)\s+([-]?[\d.]+)\s+([\d.]+)\s*([\d.]+)?"
                match2 = re.search(pattern2, normalized_line)

                if match2 and match2.group(1) in ["EUR", "USD", "GBP"]:
                    currency = match2.group(1)
                    exchange_rate = Decimal(match2.group(2))
                    quantity = Decimal(match2.group(3))
                    market_value = Decimal(match2.group(4))
                    net_amount = Decimal(match2.group(5)) if match2.group(5) else market_value
                else:
                    # Fallback: extract all numbers from the line
                    remainder = normalized_line
                    remainder = re.sub(r"(?:Trading\s+)?(?:Buy|Sell|Kauf|Verkauf)", "", remainder, flags=re.IGNORECASE)
                    for d in dates:
                        remainder = remainder.replace(d, "")
                    remainder = re.sub(r"(EUR|USD|GBP)", "", remainder)

                    # Find all numbers (including negative, decimals)
                    numbers = re.findall(r"([-]?\d+\.?\d*)", remainder)
                    numbers = [n for n in numbers if n and n != "-" and n != "."]

                    if len(numbers) < 2:
                        print(f"Could not parse transaction - not enough numbers: {line}")
                        return None

                    try:
                        currency = "EUR"
                        idx = 0

                        # Check if first number looks like exchange rate (around 1.0)
                        first_val = Decimal(numbers[0])
                        if Decimal("0.5") <= first_val <= Decimal("2.0") and "." in numbers[0]:
                            exchange_rate = first_val
                            idx = 1
                        else:
                            exchange_rate = Decimal("1.0000")

                        quantity = abs(Decimal(numbers[idx]))
                        market_value = abs(Decimal(numbers[idx + 1])) if len(numbers) > idx + 1 else Decimal("0")
                        net_amount = abs(Decimal(numbers[idx + 2])) if len(numbers) > idx + 2 else market_value

                    except (IndexError, InvalidOperation) as e:
                        print(f"Error extracting numbers from transaction: {line} - {e}")
                        return None

            # Validation: if market_value is 0 but we have quantity, something went wrong
            if market_value == Decimal("0") and quantity > Decimal("0"):
                print(f"Warning: Transaction has zero market value with non-zero quantity: {line}")
                # Try to salvage by using net_amount as market_value
                if net_amount > Decimal("0"):
                    market_value = net_amount

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
