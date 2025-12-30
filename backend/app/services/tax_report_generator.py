"""
Irish Tax Report Generator

Generates comprehensive tax reports combining:
- CGT (Capital Gains Tax) - 33%
- Exit Tax - 41%
- DIRT (Deposit Interest Retention Tax) - 33%
- Dividend income reporting

Includes Form 11/Form 12 field mappings and payment deadlines.
"""

import json
from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal
from typing import Optional

from .irish_cgt_calculator import IrishCGTCalculator, CGTResult, Acquisition, Disposal
from .exit_tax_calculator import ExitTaxCalculator, ExitTaxResult
from .dirt_calculator import DIRTCalculator, DIRTResult
from ..parsers.trade_republic_parser import ParsedReport, ParsedTransaction, ParsedIncome


@dataclass
class PaymentDeadline:
    """A tax payment deadline."""
    description: str
    due_date: date
    amount: Decimal
    tax_type: str
    paid: bool = False


@dataclass
class FormField:
    """Mapping to a tax form field."""
    form: str  # "Form 11" or "Form 12"
    section: str
    field_name: str
    value: Decimal
    notes: str = ""


@dataclass
class CompleteTaxReport:
    """Complete Irish tax report for a year."""
    tax_year: int
    generated_date: date

    # Individual tax results
    cgt_result: Optional[CGTResult] = None
    exit_tax_result: Optional[ExitTaxResult] = None
    dirt_result: Optional[DIRTResult] = None

    # Dividend summary
    total_dividends: Decimal = Decimal("0")
    dividend_withholding_tax: Decimal = Decimal("0")

    # Totals
    total_tax_due: Decimal = Decimal("0")

    # Payment schedule
    payment_deadlines: list[PaymentDeadline] = None

    # Form mappings
    form_fields: list[FormField] = None

    def __post_init__(self):
        if self.payment_deadlines is None:
            self.payment_deadlines = []
        if self.form_fields is None:
            self.form_fields = []


class TaxReportGenerator:
    """
    Generates comprehensive Irish tax reports from Trade Republic data.

    Coordinates all tax calculators and produces:
    - Tax summaries per category
    - Form 11/Form 12 field mappings
    - Payment deadline schedule
    """

    def __init__(self):
        self.cgt_calculator = IrishCGTCalculator()
        self.exit_tax_calculator = ExitTaxCalculator()
        self.dirt_calculator = DIRTCalculator()
        self.dividends: list[ParsedIncome] = []

    def process_parsed_report(self, parsed: ParsedReport):
        """Process a parsed Trade Republic report."""
        # Process transactions
        for trans in parsed.transactions:
            self._process_transaction(trans)

        # Process income events
        for income in parsed.income_events:
            self._process_income(income)

        # Process gains/losses (for verification)
        # The parsed gains_losses can be used to verify our calculations

    def _process_transaction(self, trans: ParsedTransaction):
        """Route transaction to appropriate calculator."""
        if not trans.isin:
            return

        # Determine if Exit Tax asset
        is_exit_tax = ExitTaxCalculator.is_exit_tax_asset(trans.isin, trans.name)

        if trans.transaction_type == "buy":
            if is_exit_tax:
                self.exit_tax_calculator.add_acquisition(
                    isin=trans.isin,
                    name=trans.name,
                    acquisition_date=trans.transaction_date,
                    quantity=trans.quantity,
                    unit_cost=trans.market_value / trans.quantity if trans.quantity else Decimal("0")
                )
            else:
                acq = Acquisition(
                    date=trans.transaction_date,
                    isin=trans.isin,
                    quantity=trans.quantity,
                    unit_cost=trans.market_value / trans.quantity if trans.quantity else Decimal("0"),
                    total_cost=trans.market_value
                )
                self.cgt_calculator.add_acquisition(trans.isin, acq)

        elif trans.transaction_type == "sell":
            if is_exit_tax:
                self.exit_tax_calculator.process_disposal(
                    isin=trans.isin,
                    disposal_date=trans.transaction_date,
                    quantity=trans.quantity,
                    unit_price=trans.market_value / trans.quantity if trans.quantity else Decimal("0")
                )
            else:
                disposal = Disposal(
                    date=trans.transaction_date,
                    isin=trans.isin,
                    quantity=trans.quantity,
                    unit_price=trans.market_value / trans.quantity if trans.quantity else Decimal("0"),
                    proceeds=trans.market_value
                )
                self.cgt_calculator.process_disposal(disposal)

    def _process_income(self, income: ParsedIncome):
        """Route income to appropriate handler."""
        if income.income_type == "Interest":
            self.dirt_calculator.add_interest_payment(
                payment_date=income.payment_date,
                gross_amount=income.gross_amount,
                source=income.name or "Trade Republic",
                withholding_tax=income.withholding_tax
            )
        elif income.income_type in ["Dividend", "Distribution"]:
            self.dividends.append(income)

    def generate_report(
        self,
        tax_year: int,
        cgt_losses_brought_forward: Decimal = Decimal("0")
    ) -> CompleteTaxReport:
        """Generate complete tax report for a year."""
        report = CompleteTaxReport(
            tax_year=tax_year,
            generated_date=date.today()
        )

        # Calculate CGT
        report.cgt_result = self.cgt_calculator.calculate_tax(
            tax_year,
            losses_brought_forward=cgt_losses_brought_forward
        )

        # Calculate Exit Tax
        # Get all disposals from the calculator
        exit_disposals = []
        for isin, holdings in self.exit_tax_calculator.holdings.items():
            for holding in holdings:
                # The disposals are tracked during process_disposal
                pass
        report.exit_tax_result = self.exit_tax_calculator.calculate_tax(tax_year, exit_disposals)

        # Add upcoming deemed disposals for planning
        report.exit_tax_result.upcoming_deemed_disposals = (
            self.exit_tax_calculator.get_upcoming_deemed_disposals(
                as_of_date=date(tax_year, 12, 31)
            )
        )

        # Calculate DIRT
        report.dirt_result = self.dirt_calculator.calculate_tax(tax_year)

        # Sum dividends
        for div in self.dividends:
            if div.payment_date.year == tax_year:
                report.total_dividends += div.gross_amount
                report.dividend_withholding_tax += div.withholding_tax

        # Calculate total tax due
        report.total_tax_due = (
            (report.cgt_result.tax_due if report.cgt_result else Decimal("0")) +
            (report.exit_tax_result.tax_due if report.exit_tax_result else Decimal("0")) +
            (report.dirt_result.dirt_to_pay if report.dirt_result else Decimal("0"))
        )

        # Generate payment deadlines
        report.payment_deadlines = self._generate_deadlines(report)

        # Generate form field mappings
        report.form_fields = self._generate_form_fields(report)

        return report

    def _generate_deadlines(self, report: CompleteTaxReport) -> list[PaymentDeadline]:
        """Generate payment deadline schedule."""
        deadlines = []
        year = report.tax_year

        # CGT payment deadlines
        if report.cgt_result and report.cgt_result.tax_due > 0:
            # Jan-Nov gains: Due December 15 of same year
            if report.cgt_result.jan_nov_tax > 0:
                deadlines.append(PaymentDeadline(
                    description=f"CGT on Jan-Nov {year} gains",
                    due_date=date(year, 12, 15),
                    amount=report.cgt_result.jan_nov_tax,
                    tax_type="CGT"
                ))

            # December gains: Due January 31 of following year
            if report.cgt_result.dec_tax > 0:
                deadlines.append(PaymentDeadline(
                    description=f"CGT on Dec {year} gains",
                    due_date=date(year + 1, 1, 31),
                    amount=report.cgt_result.dec_tax,
                    tax_type="CGT"
                ))

        # Exit Tax follows same deadlines as CGT
        if report.exit_tax_result and report.exit_tax_result.tax_due > 0:
            deadlines.append(PaymentDeadline(
                description=f"Exit Tax on {year} fund disposals",
                due_date=date(year, 12, 15),
                amount=report.exit_tax_result.tax_due,
                tax_type="Exit Tax"
            ))

        # DIRT: Due with annual tax return
        if report.dirt_result and report.dirt_result.dirt_to_pay > 0:
            # Form 11 deadline: October 31 (extended to mid-November for ROS)
            deadlines.append(PaymentDeadline(
                description=f"DIRT on {year} interest income",
                due_date=date(year + 1, 10, 31),
                amount=report.dirt_result.dirt_to_pay,
                tax_type="DIRT"
            ))

        # Sort by date
        deadlines.sort(key=lambda x: x.due_date)
        return deadlines

    def _generate_form_fields(self, report: CompleteTaxReport) -> list[FormField]:
        """Generate Form 11/Form 12 field mappings."""
        fields = []

        # CGT fields
        if report.cgt_result:
            cgt = report.cgt_result
            fields.extend([
                FormField(
                    form="Form 11",
                    section="Panel E - Capital Gains",
                    field_name="Total consideration received",
                    value=sum(m.proceeds for m in cgt.disposal_matches),
                    notes="Total proceeds from share sales"
                ),
                FormField(
                    form="Form 11",
                    section="Panel E - Capital Gains",
                    field_name="Total allowable costs",
                    value=sum(m.cost_basis for m in cgt.disposal_matches),
                    notes="Cost basis of shares sold"
                ),
                FormField(
                    form="Form 11",
                    section="Panel E - Capital Gains",
                    field_name="Net gain/(loss)",
                    value=cgt.net_gain_loss,
                    notes="Gains minus losses"
                ),
                FormField(
                    form="Form 11",
                    section="Panel E - Capital Gains",
                    field_name="Annual exemption claimed",
                    value=cgt.exemption_used,
                    notes=f"Max €1,270 per year"
                ),
                FormField(
                    form="Form 11",
                    section="Panel E - Capital Gains",
                    field_name="Taxable gain",
                    value=cgt.taxable_gain,
                    notes="After exemption"
                ),
                FormField(
                    form="Form 11",
                    section="Panel E - Capital Gains",
                    field_name="CGT @ 33%",
                    value=cgt.tax_due,
                    notes=""
                ),
            ])

        # Exit Tax fields
        if report.exit_tax_result and report.exit_tax_result.tax_due > 0:
            exit_tax = report.exit_tax_result
            fields.extend([
                FormField(
                    form="Form 11",
                    section="Panel E - Capital Gains",
                    field_name="Exit Tax - Investment undertakings",
                    value=exit_tax.total_gains_taxable,
                    notes="Gains from EU-domiciled funds"
                ),
                FormField(
                    form="Form 11",
                    section="Panel E - Capital Gains",
                    field_name="Exit Tax @ 41%",
                    value=exit_tax.tax_due,
                    notes="No annual exemption for Exit Tax"
                ),
            ])

        # DIRT fields
        if report.dirt_result:
            dirt = report.dirt_result
            fields.extend([
                FormField(
                    form="Form 11",
                    section="Panel D - Irish Rental & Investment Income",
                    field_name="Deposit Interest - Gross",
                    value=dirt.total_interest,
                    notes="Interest from Trade Republic (no DIRT withheld)"
                ),
                FormField(
                    form="Form 11",
                    section="Panel D - Irish Rental & Investment Income",
                    field_name="DIRT deducted",
                    value=dirt.tax_withheld,
                    notes="Usually €0 for Trade Republic"
                ),
                FormField(
                    form="Form 12",
                    section="Other Irish Income",
                    field_name="Deposit Interest (Gross)",
                    value=dirt.total_interest,
                    notes="Interest from Trade Republic"
                ),
            ])

        # Dividend fields
        if report.total_dividends > 0:
            fields.extend([
                FormField(
                    form="Form 11",
                    section="Panel F - Foreign Income",
                    field_name="Foreign dividends - Gross",
                    value=report.total_dividends,
                    notes="Fund distributions and dividends"
                ),
                FormField(
                    form="Form 11",
                    section="Panel F - Foreign Income",
                    field_name="Foreign tax credit",
                    value=report.dividend_withholding_tax,
                    notes="Withholding tax deducted at source"
                ),
            ])

        return fields

    def to_json(self, report: CompleteTaxReport) -> str:
        """Convert report to JSON for storage/export."""
        def decimal_serializer(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            if isinstance(obj, date):
                return obj.isoformat()
            if hasattr(obj, '__dict__'):
                return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        return json.dumps(asdict(report), default=decimal_serializer, indent=2)

    def get_summary(self, report: CompleteTaxReport) -> dict:
        """Get a summary suitable for display."""
        return {
            "tax_year": report.tax_year,
            "cgt": {
                "gains": float(report.cgt_result.total_gains) if report.cgt_result else 0,
                "losses": float(report.cgt_result.total_losses) if report.cgt_result else 0,
                "exemption_used": float(report.cgt_result.exemption_used) if report.cgt_result else 0,
                "taxable": float(report.cgt_result.taxable_gain) if report.cgt_result else 0,
                "tax_due": float(report.cgt_result.tax_due) if report.cgt_result else 0,
                "losses_carry_forward": float(report.cgt_result.losses_to_carry_forward) if report.cgt_result else 0,
            },
            "exit_tax": {
                "gains": float(report.exit_tax_result.total_gains_taxable) if report.exit_tax_result else 0,
                "tax_due": float(report.exit_tax_result.tax_due) if report.exit_tax_result else 0,
                "upcoming_deemed_disposals": len(report.exit_tax_result.upcoming_deemed_disposals) if report.exit_tax_result else 0,
            },
            "dirt": {
                "interest_income": float(report.dirt_result.total_interest) if report.dirt_result else 0,
                "tax_due": float(report.dirt_result.dirt_to_pay) if report.dirt_result else 0,
            },
            "dividends": {
                "total": float(report.total_dividends),
                "withholding_credit": float(report.dividend_withholding_tax),
            },
            "total_tax_due": float(report.total_tax_due),
            "payment_deadlines": [
                {
                    "description": d.description,
                    "due_date": d.due_date.isoformat(),
                    "amount": float(d.amount),
                    "tax_type": d.tax_type
                }
                for d in report.payment_deadlines
            ]
        }
