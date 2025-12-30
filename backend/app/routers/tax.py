"""Tax calculation router."""

from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from ..models import get_db, Asset, Transaction, IncomeEvent, TransactionType
from ..services import (
    IrishCGTCalculator,
    ExitTaxCalculator,
    DIRTCalculator,
    TaxReportGenerator
)
from ..services.irish_cgt_calculator import Acquisition, Disposal
from ..schemas import TaxSummaryResponse, PaymentDeadlineResponse

router = APIRouter(prefix="/tax", tags=["tax"])


@router.get("/calculate/{tax_year}")
async def calculate_tax(
    tax_year: int,
    losses_carried_forward: Decimal = Query(Decimal("0"), description="CGT losses from previous years"),
    db: Session = Depends(get_db)
) -> dict:
    """
    Calculate Irish taxes for a tax year.

    Returns breakdown of:
    - CGT (33%) on stocks
    - Exit Tax (41%) on EU funds
    - DIRT (33%) on interest
    - Dividend income summary
    """
    # Initialize calculators
    cgt_calc = IrishCGTCalculator()
    exit_calc = ExitTaxCalculator()
    dirt_calc = DIRTCalculator()

    # Get all transactions for the year and prior (for cost basis)
    transactions = db.query(Transaction).join(Asset).filter(
        Transaction.transaction_date <= date(tax_year, 12, 31)
    ).order_by(Transaction.transaction_date).all()

    # Process transactions
    for trans in transactions:
        asset = trans.asset
        is_exit_tax = ExitTaxCalculator.is_exit_tax_asset(asset.isin, asset.name)

        if trans.transaction_type == TransactionType.BUY:
            qty = abs(trans.quantity)
            unit_cost = trans.gross_amount / qty if qty > 0 else Decimal("0")

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
                    total_cost=trans.gross_amount
                )
                cgt_calc.add_acquisition(asset.isin, acq)

        elif trans.transaction_type == TransactionType.SELL:
            qty = abs(trans.quantity)
            unit_price = trans.gross_amount / qty if qty > 0 else Decimal("0")

            if is_exit_tax:
                exit_calc.process_disposal(
                    isin=asset.isin,
                    disposal_date=trans.transaction_date,
                    quantity=qty,
                    unit_price=unit_price
                )
            else:
                disposal = Disposal(
                    date=trans.transaction_date,
                    isin=asset.isin,
                    quantity=qty,
                    unit_price=unit_price,
                    proceeds=trans.gross_amount
                )
                cgt_calc.process_disposal(disposal)

    # Get income events
    income_events = db.query(IncomeEvent).filter(
        IncomeEvent.payment_date >= date(tax_year, 1, 1),
        IncomeEvent.payment_date <= date(tax_year, 12, 31)
    ).all()

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

    # Get Exit Tax disposals that occurred in the tax year
    exit_disposals = []
    exit_result = exit_calc.calculate_tax(tax_year, exit_disposals)

    dirt_result = dirt_calc.calculate_tax(tax_year)

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
            "annual_exemption": float(cgt_result.annual_exemption),
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
            "form_guidance": dirt_calc.get_annual_summary(tax_year)
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
    db: Session = Depends(get_db)
) -> list[dict]:
    """Get upcoming deemed disposal events for Exit Tax planning."""
    exit_calc = ExitTaxCalculator()

    # Load all EU fund acquisitions
    assets = db.query(Asset).filter(Asset.is_eu_fund == True).all()

    for asset in assets:
        transactions = db.query(Transaction).filter(
            Transaction.asset_id == asset.id,
            Transaction.transaction_type == TransactionType.BUY
        ).all()

        for trans in transactions:
            qty = abs(trans.quantity)
            unit_cost = trans.gross_amount / qty if qty > 0 else Decimal("0")
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
