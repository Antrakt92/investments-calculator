"""Tax calculation router."""

from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from ..models import get_db, Asset, Transaction, IncomeEvent, TransactionType, Person
from ..services import (
    IrishCGTCalculator,
    ExitTaxCalculator,
    DIRTCalculator,
    TaxReportGenerator
)
from ..services.irish_cgt_calculator import Acquisition, Disposal
from ..schemas import TaxSummaryResponse, PaymentDeadlineResponse

router = APIRouter(prefix="/tax", tags=["tax"])


def _calculate_tax_for_person(
    db: Session,
    tax_year: int,
    person_id: Optional[int],
    losses_carried_forward: Decimal = Decimal("0")
) -> tuple:
    """
    Calculate tax for a single person (or all if person_id is None).
    Returns (cgt_result, exit_result, dirt_result, exit_disposals, income_events, all_disposal_matches)
    """
    cgt_calc = IrishCGTCalculator()
    exit_calc = ExitTaxCalculator()
    dirt_calc = DIRTCalculator()
    all_exit_disposals = []

    # Get transactions
    trans_query = db.query(Transaction).join(Asset).filter(
        Transaction.transaction_date <= date(tax_year, 12, 31)
    )
    if person_id is not None:
        trans_query = trans_query.filter(Transaction.person_id == person_id)
    transactions = trans_query.order_by(Transaction.transaction_date).all()

    # Process transactions
    for trans in transactions:
        asset = trans.asset
        is_exit_tax = ExitTaxCalculator.is_exit_tax_asset(asset.isin, asset.name)

        if trans.transaction_type == TransactionType.BUY:
            qty = abs(trans.quantity)
            total_cost_with_fees = trans.gross_amount + trans.fees
            unit_cost = total_cost_with_fees / qty if qty > 0 else Decimal("0")

            if is_exit_tax:
                exit_calc.add_acquisition(
                    isin=asset.isin,
                    name=asset.name,
                    acquisition_date=trans.transaction_date,
                    quantity=qty,
                    unit_cost=unit_cost
                )
            else:
                acq = Acquisition(
                    date=trans.transaction_date,
                    isin=asset.isin,
                    quantity=qty,
                    unit_cost=unit_cost,
                    total_cost=total_cost_with_fees
                )
                cgt_calc.add_acquisition(asset.isin, acq)

        elif trans.transaction_type == TransactionType.SELL:
            qty = abs(trans.quantity)
            proceeds_after_fees = trans.gross_amount - trans.fees
            unit_price = proceeds_after_fees / qty if qty > 0 else Decimal("0")

            if is_exit_tax:
                disposals = exit_calc.process_disposal(
                    isin=asset.isin,
                    disposal_date=trans.transaction_date,
                    quantity=qty,
                    unit_price=unit_price
                )
                all_exit_disposals.extend(disposals)
            else:
                disposal = Disposal(
                    date=trans.transaction_date,
                    isin=asset.isin,
                    quantity=qty,
                    unit_price=unit_price,
                    proceeds=proceeds_after_fees,
                    fees=trans.fees
                )
                cgt_calc.process_disposal(disposal)

    # Get income events
    income_query = db.query(IncomeEvent).filter(
        IncomeEvent.payment_date >= date(tax_year, 1, 1),
        IncomeEvent.payment_date <= date(tax_year, 12, 31)
    )
    if person_id is not None:
        income_query = income_query.filter(IncomeEvent.person_id == person_id)
    income_events = income_query.all()

    # Process interest for DIRT
    for event in income_events:
        if event.income_type == "interest":
            dirt_calc.add_interest_payment(
                payment_date=event.payment_date,
                gross_amount=event.gross_amount,
                source="Trade Republic",
                withholding_tax=event.withholding_tax
            )

    # Calculate taxes
    cgt_result = cgt_calc.calculate_tax(tax_year, losses_brought_forward=losses_carried_forward)
    exit_result = exit_calc.calculate_tax(tax_year, all_exit_disposals)
    dirt_result = dirt_calc.calculate_tax(tax_year)

    return cgt_result, exit_result, dirt_result, dirt_calc, all_exit_disposals, income_events


@router.get("/calculate/{tax_year}")
async def calculate_tax(
    tax_year: int,
    losses_carried_forward: Decimal = Query(Decimal("0"), description="CGT losses from previous years"),
    person_id: Optional[int] = Query(None, description="Person ID for family mode (None = combined view)"),
    db: Session = Depends(get_db)
) -> dict:
    """
    Calculate Irish taxes for a tax year.

    Returns breakdown of:
    - CGT (33%) on stocks
    - Exit Tax (41%) on EU funds
    - DIRT (33%) on interest
    - Dividend income summary

    If person_id is provided, calculates for that person only.
    If person_id is None, calculates combined totals for all persons.
    IMPORTANT: Each person gets their own €1,270 CGT exemption.
    """
    if person_id is not None:
        # Single person calculation - straightforward
        cgt_result, exit_result, dirt_result, dirt_calc, all_exit_disposals, income_events = \
            _calculate_tax_for_person(db, tax_year, person_id, losses_carried_forward)
        all_disposal_matches = cgt_result.disposal_matches
        total_annual_exemption = cgt_result.annual_exemption
    else:
        # Combined view: Calculate per-person to apply individual exemptions
        # Get all unique person_ids that have transactions
        person_ids_with_trans = db.query(Transaction.person_id).filter(
            Transaction.transaction_date <= date(tax_year, 12, 31)
        ).distinct().all()
        person_ids = [pid[0] for pid in person_ids_with_trans if pid[0] is not None]

        if not person_ids:
            # No persons - might be legacy data without person_id
            cgt_result, exit_result, dirt_result, dirt_calc, all_exit_disposals, income_events = \
                _calculate_tax_for_person(db, tax_year, None, losses_carried_forward)
            all_disposal_matches = cgt_result.disposal_matches
            total_annual_exemption = cgt_result.annual_exemption
        else:
            # Calculate tax for each person and aggregate
            # Each person gets their own €1,270 exemption
            from ..services.irish_cgt_calculator import CGTResult
            from ..services.exit_tax_calculator import ExitTaxResult

            # Aggregate CGT results
            total_cgt_gains = Decimal("0")
            total_cgt_losses = Decimal("0")
            total_cgt_net = Decimal("0")
            total_exemption_used = Decimal("0")
            total_cgt_taxable = Decimal("0")
            total_cgt_tax_due = Decimal("0")
            total_jan_nov_gains = Decimal("0")
            total_jan_nov_tax = Decimal("0")
            total_dec_gains = Decimal("0")
            total_dec_tax = Decimal("0")
            total_losses_to_carry = Decimal("0")
            all_disposal_matches = []

            # Aggregate Exit Tax results
            total_exit_disposal_gains = Decimal("0")
            total_exit_disposal_losses = Decimal("0")
            total_exit_deemed_gains = Decimal("0")
            total_exit_taxable = Decimal("0")
            total_exit_tax_due = Decimal("0")
            all_upcoming_deemed = []

            # Aggregate DIRT results
            total_interest = Decimal("0")
            total_dirt_withheld = Decimal("0")
            total_dirt_due = Decimal("0")
            total_dirt_to_pay = Decimal("0")

            # Aggregate income events
            all_income_events = []
            first_dirt_calc = None

            # Per-person losses carried forward (simplified: split evenly)
            per_person_losses = losses_carried_forward / len(person_ids) if len(person_ids) > 0 else Decimal("0")

            for pid in person_ids:
                p_cgt, p_exit, p_dirt, p_dirt_calc, p_exit_disp, p_income = \
                    _calculate_tax_for_person(db, tax_year, pid, per_person_losses)

                if first_dirt_calc is None:
                    first_dirt_calc = p_dirt_calc

                # CGT aggregation
                total_cgt_gains += p_cgt.total_gains
                total_cgt_losses += p_cgt.total_losses
                total_cgt_net += p_cgt.net_gain_loss
                total_exemption_used += p_cgt.exemption_used
                total_cgt_taxable += p_cgt.taxable_gain
                total_cgt_tax_due += p_cgt.tax_due
                total_jan_nov_gains += p_cgt.jan_nov_gains
                total_jan_nov_tax += p_cgt.jan_nov_tax
                total_dec_gains += p_cgt.dec_gains
                total_dec_tax += p_cgt.dec_tax
                total_losses_to_carry += p_cgt.losses_to_carry_forward
                all_disposal_matches.extend(p_cgt.disposal_matches)

                # Exit Tax aggregation
                total_exit_disposal_gains += p_exit.disposal_gains
                total_exit_disposal_losses += p_exit.disposal_losses
                total_exit_deemed_gains += p_exit.deemed_disposal_gains
                total_exit_taxable += p_exit.total_gains_taxable
                total_exit_tax_due += p_exit.tax_due
                all_upcoming_deemed.extend(p_exit.upcoming_deemed_disposals)

                # DIRT aggregation
                total_interest += p_dirt.total_interest
                total_dirt_withheld += p_dirt.tax_withheld
                total_dirt_due += p_dirt.dirt_due
                total_dirt_to_pay += p_dirt.dirt_to_pay

                all_income_events.extend(p_income)

            # Build aggregated CGT result
            cgt_result = CGTResult(
                tax_year=tax_year,
                total_gains=total_cgt_gains,
                total_losses=total_cgt_losses,
                net_gain_loss=total_cgt_net,
                annual_exemption=Decimal("1270") * len(person_ids),  # Per-person exemptions
                exemption_used=total_exemption_used,
                taxable_gain=total_cgt_taxable,
                tax_due=total_cgt_tax_due,
                jan_nov_gains=total_jan_nov_gains,
                jan_nov_tax=total_jan_nov_tax,
                dec_gains=total_dec_gains,
                dec_tax=total_dec_tax,
                disposal_matches=all_disposal_matches,
                losses_to_carry_forward=total_losses_to_carry
            )

            # Build aggregated Exit Tax result
            exit_result = ExitTaxResult(
                tax_year=tax_year,
                disposal_gains=total_exit_disposal_gains,
                disposal_losses=total_exit_disposal_losses,
                deemed_disposal_gains=total_exit_deemed_gains,
                total_gains_taxable=total_exit_taxable,
                tax_due=total_exit_tax_due,
                upcoming_deemed_disposals=all_upcoming_deemed
            )

            # Build aggregated DIRT result (simple container)
            class DIRTAggregated:
                pass
            dirt_result = DIRTAggregated()
            dirt_result.total_interest = total_interest
            dirt_result.tax_withheld = total_dirt_withheld
            dirt_result.dirt_due = total_dirt_due
            dirt_result.dirt_to_pay = total_dirt_to_pay

            dirt_calc = first_dirt_calc
            income_events = all_income_events
            total_annual_exemption = Decimal("1270") * len(person_ids)

    # Sum dividends
    total_dividends = Decimal("0")
    dividend_withholding = Decimal("0")
    for event in income_events:
        if event.income_type in ["dividend", "distribution"]:
            total_dividends += event.gross_amount
            dividend_withholding += event.withholding_tax

    # Build response
    total_tax = cgt_result.tax_due + exit_result.tax_due + dirt_result.dirt_to_pay

    return {
        "tax_year": tax_year,
        "cgt": {
            "description": "Capital Gains Tax on stocks (33%)",
            "gains": float(cgt_result.total_gains),
            "losses": float(cgt_result.total_losses),
            "net_gain_loss": float(cgt_result.net_gain_loss),
            "annual_exemption": float(total_annual_exemption),
            "exemption_used": float(cgt_result.exemption_used),
            "taxable_gain": float(cgt_result.taxable_gain),
            "tax_rate": "33%",
            "tax_due": float(cgt_result.tax_due),
            "losses_to_carry_forward": float(cgt_result.losses_to_carry_forward),
            "payment_periods": {
                "jan_nov": {
                    "gains": float(cgt_result.jan_nov_gains),
                    "tax": float(cgt_result.jan_nov_tax),
                    "due_date": f"{tax_year}-12-15"
                },
                "december": {
                    "gains": float(cgt_result.dec_gains),
                    "tax": float(cgt_result.dec_tax),
                    "due_date": f"{tax_year + 1}-01-31"
                }
            },
            "disposal_details": [
                {
                    "disposal_date": m.disposal_date.isoformat(),
                    "acquisition_date": m.acquisition_date.isoformat(),
                    "quantity": float(m.quantity_matched),
                    "cost_basis": float(m.cost_basis),
                    "proceeds": float(m.proceeds),
                    "gain_loss": float(m.gain_loss),
                    "matching_rule": m.match_rule
                }
                for m in cgt_result.disposal_matches
            ]
        },
        "exit_tax": {
            "description": "Exit Tax on EU-domiciled funds (41%)",
            "gains": float(exit_result.disposal_gains),
            "losses": float(exit_result.disposal_losses),
            "deemed_disposal_gains": float(exit_result.deemed_disposal_gains),
            "total_taxable": float(exit_result.total_gains_taxable),
            "tax_rate": "41%",
            "tax_due": float(exit_result.tax_due),
            "note": "No annual exemption. Losses cannot offset CGT gains.",
            "upcoming_deemed_disposals": [
                {
                    "isin": d.isin,
                    "name": d.name,
                    "acquisition_date": d.original_acquisition_date.isoformat(),
                    "deemed_disposal_date": d.deemed_disposal_date.isoformat(),
                    "quantity": float(d.quantity),
                    "cost_basis": float(d.cost_basis)
                }
                for d in exit_result.upcoming_deemed_disposals
            ]
        },
        "dirt": {
            "description": "Deposit Interest Retention Tax (33%)",
            "interest_income": float(dirt_result.total_interest),
            "tax_withheld": float(dirt_result.tax_withheld),
            "tax_rate": "33%",
            "tax_due": float(dirt_result.dirt_due),
            "tax_to_pay": float(dirt_result.dirt_to_pay),
            "note": "Trade Republic does not withhold DIRT - must self-declare",
            "form_guidance": dirt_calc.get_annual_summary(tax_year) if dirt_calc else {}
        },
        "dividends": {
            "description": "Dividend income (taxed at marginal rate)",
            "total_dividends": float(total_dividends),
            "withholding_tax_credit": float(dividend_withholding),
            "note": "Add to Schedule D income on Form 11"
        },
        "summary": {
            "total_tax_due": float(total_tax),
            "payment_deadlines": [
                {
                    "description": f"CGT on Jan-Nov {tax_year} gains",
                    "due_date": f"{tax_year}-12-15",
                    "amount": float(cgt_result.jan_nov_tax),
                    "tax_type": "CGT"
                },
                {
                    "description": f"CGT on Dec {tax_year} gains",
                    "due_date": f"{tax_year + 1}-01-31",
                    "amount": float(cgt_result.dec_tax),
                    "tax_type": "CGT"
                },
                {
                    "description": f"Exit Tax on {tax_year} fund disposals",
                    "due_date": f"{tax_year}-12-15",
                    "amount": float(exit_result.tax_due),
                    "tax_type": "Exit Tax"
                },
                {
                    "description": f"DIRT on {tax_year} interest",
                    "due_date": f"{tax_year + 1}-10-31",
                    "amount": float(dirt_result.dirt_to_pay),
                    "tax_type": "DIRT"
                }
            ]
        },
        "form_11_guidance": {
            "panel_d": {
                "deposit_interest_gross": float(dirt_result.total_interest),
                "dirt_deducted": float(dirt_result.tax_withheld)
            },
            "panel_e": {
                "cgt_consideration": float(sum(m.proceeds for m in cgt_result.disposal_matches)),
                "cgt_allowable_costs": float(sum(m.cost_basis for m in cgt_result.disposal_matches)),
                "cgt_net_gain": float(cgt_result.net_gain_loss),
                "cgt_exemption": float(cgt_result.exemption_used),
                "cgt_taxable": float(cgt_result.taxable_gain),
                "exit_tax_gains": float(exit_result.total_gains_taxable)
            },
            "panel_f": {
                "foreign_dividends": float(total_dividends),
                "foreign_tax_credit": float(dividend_withholding)
            }
        }
    }


@router.get("/deemed-disposals")
async def get_deemed_disposals(
    years_ahead: int = Query(3, le=10, description="Years to look ahead"),
    person_id: Optional[int] = Query(None, description="Person ID for family mode"),
    db: Session = Depends(get_db)
) -> list[dict]:
    """Get upcoming deemed disposal events for Exit Tax planning."""
    exit_calc = ExitTaxCalculator()

    # Load all EU fund acquisitions
    assets = db.query(Asset).filter(Asset.is_eu_fund == True).all()

    for asset in assets:
        trans_query = db.query(Transaction).filter(
            Transaction.asset_id == asset.id,
            Transaction.transaction_type == TransactionType.BUY
        )
        if person_id is not None:
            trans_query = trans_query.filter(Transaction.person_id == person_id)
        transactions = trans_query.all()

        for trans in transactions:
            qty = abs(trans.quantity)
            # Include fees in cost basis (allowable cost for tax purposes)
            total_cost_with_fees = trans.gross_amount + trans.fees
            unit_cost = total_cost_with_fees / qty if qty > 0 else Decimal("0")
            exit_calc.add_acquisition(
                isin=asset.isin,
                name=asset.name,
                acquisition_date=trans.transaction_date,
                quantity=qty,
                unit_cost=unit_cost
            )

    upcoming = exit_calc.get_upcoming_deemed_disposals(
        as_of_date=date.today(),
        years_ahead=years_ahead
    )

    return [
        {
            "isin": d.isin,
            "name": d.name,
            "acquisition_date": d.original_acquisition_date.isoformat(),
            "deemed_disposal_date": d.deemed_disposal_date.isoformat(),
            "quantity": float(d.quantity),
            "cost_basis": float(d.cost_basis),
            "estimated_gain": float(d.estimated_gain) if d.estimated_gain else None,
            "estimated_tax": float(d.estimated_tax) if d.estimated_tax else None
        }
        for d in upcoming
    ]


@router.get("/losses-to-carry-forward/{from_year}")
async def get_losses_to_carry_forward(
    from_year: int,
    person_id: Optional[int] = Query(None, description="Person ID for family mode"),
    db: Session = Depends(get_db)
) -> dict:
    """
    Get CGT losses that should be carried forward from a specific year.

    This calculates the losses from the specified year that can be used
    to offset gains in future years.
    """
    # Initialize CGT calculator
    cgt_calc = IrishCGTCalculator()

    # Get all non-Exit Tax transactions up to and including the specified year
    trans_query = db.query(Transaction).join(Asset).filter(
        Transaction.transaction_date <= date(from_year, 12, 31)
    )
    if person_id is not None:
        trans_query = trans_query.filter(Transaction.person_id == person_id)
    transactions = trans_query.order_by(Transaction.transaction_date).all()

    # Process transactions
    for trans in transactions:
        asset = trans.asset
        is_exit_tax = ExitTaxCalculator.is_exit_tax_asset(asset.isin, asset.name)

        # Only process non-Exit Tax assets for CGT
        if is_exit_tax:
            continue

        if trans.transaction_type == TransactionType.BUY:
            qty = abs(trans.quantity)
            # Include fees in cost basis
            total_cost_with_fees = trans.gross_amount + trans.fees
            unit_cost = total_cost_with_fees / qty if qty > 0 else Decimal("0")
            acq = Acquisition(
                date=trans.transaction_date,
                isin=asset.isin,
                quantity=qty,
                unit_cost=unit_cost,
                total_cost=total_cost_with_fees
            )
            cgt_calc.add_acquisition(asset.isin, acq)

        elif trans.transaction_type == TransactionType.SELL:
            qty = abs(trans.quantity)
            # Deduct fees from proceeds
            proceeds_after_fees = trans.gross_amount - trans.fees
            unit_price = proceeds_after_fees / qty if qty > 0 else Decimal("0")
            disposal = Disposal(
                date=trans.transaction_date,
                isin=asset.isin,
                quantity=qty,
                unit_price=unit_price,
                proceeds=proceeds_after_fees,
                fees=trans.fees
            )
            cgt_calc.process_disposal(disposal)

    # Calculate tax for the year (with no carried forward losses to get raw losses)
    cgt_result = cgt_calc.calculate_tax(from_year, losses_brought_forward=Decimal("0"))

    return {
        "from_year": from_year,
        "losses_to_carry_forward": float(cgt_result.losses_to_carry_forward),
        "total_gains": float(cgt_result.total_gains),
        "total_losses": float(cgt_result.total_losses),
        "net_gain_loss": float(cgt_result.net_gain_loss)
    }
