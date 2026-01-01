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


@router.get("/what-if/{isin}")
async def calculate_what_if(
    isin: str,
    quantity: Decimal = Query(..., description="Quantity to hypothetically sell"),
    sale_price: Decimal = Query(..., description="Hypothetical sale price per unit"),
    person_id: Optional[int] = Query(None, description="Person ID for family mode"),
    db: Session = Depends(get_db)
) -> dict:
    """
    Calculate estimated tax if you sold a position.

    Returns breakdown of:
    - Cost basis that would be used (FIFO)
    - Estimated gain/loss
    - Estimated tax (CGT 33% or Exit Tax 41%)
    - Whether annual exemption would apply
    """
    # Get the asset
    asset = db.query(Asset).filter(Asset.isin == isin).first()
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {isin} not found")

    # Determine if Exit Tax or CGT
    is_exit_tax = ExitTaxCalculator.is_exit_tax_asset(asset.isin, asset.name)
    tax_type = "Exit Tax" if is_exit_tax else "CGT"
    tax_rate = Decimal("0.41") if is_exit_tax else Decimal("0.33")

    # Get all buy transactions for this asset to calculate cost basis
    buy_query = db.query(Transaction).filter(
        Transaction.asset_id == asset.id,
        Transaction.transaction_type == TransactionType.BUY
    )
    if person_id is not None:
        buy_query = buy_query.filter(Transaction.person_id == person_id)
    buys = buy_query.order_by(Transaction.transaction_date).all()

    # Get all sell transactions to see what's already been sold
    sell_query = db.query(Transaction).filter(
        Transaction.asset_id == asset.id,
        Transaction.transaction_type == TransactionType.SELL
    )
    if person_id is not None:
        sell_query = sell_query.filter(Transaction.person_id == person_id)
    sells = sell_query.order_by(Transaction.transaction_date).all()

    # Build remaining lots using FIFO
    lots = []
    for buy in buys:
        qty = abs(buy.quantity)
        total_cost_with_fees = buy.gross_amount + buy.fees
        unit_cost = total_cost_with_fees / qty if qty > 0 else Decimal("0")
        lots.append({
            "date": buy.transaction_date,
            "quantity": qty,
            "remaining": qty,
            "unit_cost": unit_cost
        })

    # Apply existing sells using FIFO
    for sell in sells:
        qty_to_match = abs(sell.quantity)
        for lot in lots:
            if qty_to_match <= 0:
                break
            if lot["remaining"] > 0:
                matched = min(qty_to_match, lot["remaining"])
                lot["remaining"] -= matched
                qty_to_match -= matched

    # Calculate available quantity
    available_qty = sum(lot["remaining"] for lot in lots)

    if quantity > available_qty:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot sell {quantity} units. Only {float(available_qty):.4f} available."
        )

    # Calculate cost basis for hypothetical sale using FIFO
    qty_to_sell = quantity
    total_cost_basis = Decimal("0")
    lots_used = []

    for lot in lots:
        if qty_to_sell <= 0:
            break
        if lot["remaining"] > 0:
            matched = min(qty_to_sell, lot["remaining"])
            cost_for_lot = matched * lot["unit_cost"]
            total_cost_basis += cost_for_lot
            lots_used.append({
                "acquisition_date": lot["date"].isoformat(),
                "quantity": float(matched),
                "unit_cost": float(lot["unit_cost"]),
                "cost_basis": float(cost_for_lot)
            })
            qty_to_sell -= matched

    # Calculate proceeds and gain/loss
    total_proceeds = quantity * sale_price
    gain_loss = total_proceeds - total_cost_basis

    # Calculate estimated tax
    if is_exit_tax:
        # Exit Tax: No exemption, losses can offset gains within Exit Tax regime
        taxable_amount = max(Decimal("0"), gain_loss)
        estimated_tax = (taxable_amount * tax_rate).quantize(Decimal("0.01"))
        exemption_info = "No annual exemption for Exit Tax"
    else:
        # CGT: €1,270 annual exemption available
        annual_exemption = Decimal("1270")
        if gain_loss > 0:
            taxable_after_exemption = max(Decimal("0"), gain_loss - annual_exemption)
            estimated_tax = (taxable_after_exemption * tax_rate).quantize(Decimal("0.01"))
            exemption_used = min(gain_loss, annual_exemption)
            exemption_info = f"€{float(exemption_used):.2f} of €1,270 exemption could be used"
        else:
            estimated_tax = Decimal("0")
            exemption_info = "No tax on losses. Loss can be carried forward."

    return {
        "isin": isin,
        "asset_name": asset.name,
        "tax_type": tax_type,
        "scenario": {
            "quantity_to_sell": float(quantity),
            "sale_price_per_unit": float(sale_price),
            "total_proceeds": float(total_proceeds)
        },
        "cost_basis": {
            "total": float(total_cost_basis),
            "average_per_unit": float(total_cost_basis / quantity) if quantity > 0 else 0,
            "lots_used": lots_used
        },
        "result": {
            "gain_loss": float(gain_loss),
            "is_gain": gain_loss > 0,
            "tax_rate": f"{int(tax_rate * 100)}%",
            "estimated_tax": float(estimated_tax),
            "exemption_info": exemption_info
        },
        "available_quantity": float(available_qty),
        "note": f"This is an estimate. Actual tax depends on other {tax_type} transactions in the tax year."
    }


@router.get("/loss-harvesting")
async def get_loss_harvesting_opportunities(
    person_id: Optional[int] = Query(None, description="Person ID for family mode"),
    db: Session = Depends(get_db)
) -> list[dict]:
    """
    Identify positions with unrealized losses that could be harvested.

    Loss harvesting = selling at a loss to offset gains, reducing tax bill.
    Note: Watch out for the 4-week "bed & breakfast" rule if you rebuy.
    """
    opportunities = []

    assets = db.query(Asset).all()

    for asset in assets:
        # Get all transactions for this asset
        buy_query = db.query(Transaction).filter(
            Transaction.asset_id == asset.id,
            Transaction.transaction_type == TransactionType.BUY
        )
        sell_query = db.query(Transaction).filter(
            Transaction.asset_id == asset.id,
            Transaction.transaction_type == TransactionType.SELL
        )

        if person_id is not None:
            buy_query = buy_query.filter(Transaction.person_id == person_id)
            sell_query = sell_query.filter(Transaction.person_id == person_id)

        buys = buy_query.order_by(Transaction.transaction_date).all()
        sells = sell_query.order_by(Transaction.transaction_date).all()

        if not buys:
            continue

        # Build remaining lots using FIFO
        lots = []
        for buy in buys:
            qty = abs(buy.quantity)
            total_cost_with_fees = buy.gross_amount + buy.fees
            unit_cost = total_cost_with_fees / qty if qty > 0 else Decimal("0")
            lots.append({
                "date": buy.transaction_date,
                "quantity": qty,
                "remaining": qty,
                "unit_cost": unit_cost
            })

        # Apply existing sells using FIFO
        for sell in sells:
            qty_to_match = abs(sell.quantity)
            for lot in lots:
                if qty_to_match <= 0:
                    break
                if lot["remaining"] > 0:
                    matched = min(qty_to_match, lot["remaining"])
                    lot["remaining"] -= matched
                    qty_to_match -= matched

        # Calculate remaining position
        remaining_qty = sum(lot["remaining"] for lot in lots)
        if remaining_qty <= 0:
            continue

        remaining_cost = sum(lot["remaining"] * lot["unit_cost"] for lot in lots)
        avg_cost = remaining_cost / remaining_qty if remaining_qty > 0 else Decimal("0")

        # Determine tax type
        is_exit_tax = ExitTaxCalculator.is_exit_tax_asset(asset.isin, asset.name)

        opportunities.append({
            "isin": asset.isin,
            "name": asset.name,
            "tax_type": "Exit Tax" if is_exit_tax else "CGT",
            "quantity": float(remaining_qty),
            "average_cost": float(avg_cost),
            "total_cost_basis": float(remaining_cost),
            "current_price": None,  # Would need market data
            "unrealized_gain_loss": None,  # Would need market data
            "note": "Enter current price to see potential tax savings"
        })

    return opportunities


@router.get("/bed-breakfast-check/{isin}")
async def check_bed_breakfast_rule(
    isin: str,
    person_id: Optional[int] = Query(None, description="Person ID for family mode"),
    db: Session = Depends(get_db)
) -> dict:
    """
    Check if buying this asset would trigger the 4-week bed & breakfast rule.

    The bed & breakfast rule (Irish CGT) prevents you from selling an asset at a loss
    and immediately rebuying it. If you rebuy within 4 weeks, the original sale's
    cost basis is linked to the repurchase, potentially denying loss relief.

    Returns warning info if a sale of this asset occurred within the last 4 weeks.
    """
    from datetime import timedelta

    # Get the asset
    asset = db.query(Asset).filter(Asset.isin == isin).first()
    if not asset:
        return {
            "has_warning": False,
            "isin": isin,
            "message": "Asset not found in portfolio"
        }

    # Check if it's an Exit Tax asset (rule doesn't apply to Exit Tax)
    is_exit_tax = ExitTaxCalculator.is_exit_tax_asset(asset.isin, asset.name)
    if is_exit_tax:
        return {
            "has_warning": False,
            "isin": isin,
            "asset_name": asset.name,
            "message": "Bed & breakfast rule does not apply to Exit Tax assets"
        }

    # Find sales within the last 4 weeks (28 days)
    four_weeks_ago = date.today() - timedelta(days=28)

    sell_query = db.query(Transaction).filter(
        Transaction.asset_id == asset.id,
        Transaction.transaction_type == TransactionType.SELL,
        Transaction.transaction_date >= four_weeks_ago
    )

    if person_id is not None:
        sell_query = sell_query.filter(Transaction.person_id == person_id)

    recent_sales = sell_query.order_by(Transaction.transaction_date.desc()).all()

    if not recent_sales:
        return {
            "has_warning": False,
            "isin": isin,
            "asset_name": asset.name,
            "message": "No recent sales - safe to buy"
        }

    # Calculate days remaining in bed & breakfast period
    most_recent_sale = recent_sales[0]
    sale_date = most_recent_sale.transaction_date
    end_of_period = sale_date + timedelta(days=28)
    days_remaining = (end_of_period - date.today()).days

    # Calculate the loss that might be affected
    qty_sold = sum(abs(s.quantity) for s in recent_sales)
    total_proceeds = sum(s.gross_amount - s.fees for s in recent_sales)

    return {
        "has_warning": True,
        "isin": isin,
        "asset_name": asset.name,
        "recent_sale": {
            "date": sale_date.isoformat(),
            "quantity": float(abs(most_recent_sale.quantity)),
            "proceeds": float(most_recent_sale.gross_amount - most_recent_sale.fees)
        },
        "bed_breakfast_end_date": end_of_period.isoformat(),
        "days_remaining": days_remaining,
        "total_recent_sales": {
            "count": len(recent_sales),
            "total_quantity": float(qty_sold),
            "total_proceeds": float(total_proceeds)
        },
        "message": f"Warning: You sold this asset on {sale_date.strftime('%d %b %Y')}. "
                   f"Buying within 4 weeks ({days_remaining} days remaining) triggers the "
                   f"bed & breakfast rule, which may affect your CGT loss relief.",
        "safe_to_buy_date": end_of_period.isoformat()
    }


@router.get("/recent-sales")
async def get_recent_sales(
    days: int = Query(28, description="Number of days to look back"),
    person_id: Optional[int] = Query(None, description="Person ID for family mode"),
    db: Session = Depends(get_db)
) -> list[dict]:
    """
    Get all assets sold within the last N days (default 28 = 4 weeks).
    Useful for bed & breakfast rule warnings.
    """
    from datetime import timedelta

    cutoff_date = date.today() - timedelta(days=days)

    query = db.query(Transaction).join(Asset).filter(
        Transaction.transaction_type == TransactionType.SELL,
        Transaction.transaction_date >= cutoff_date
    )

    if person_id is not None:
        query = query.filter(Transaction.person_id == person_id)

    recent_sales = query.order_by(Transaction.transaction_date.desc()).all()

    # Group by ISIN
    sales_by_isin = {}
    for sale in recent_sales:
        isin = sale.asset.isin
        if isin not in sales_by_isin:
            is_exit_tax = ExitTaxCalculator.is_exit_tax_asset(sale.asset.isin, sale.asset.name)
            sales_by_isin[isin] = {
                "isin": isin,
                "name": sale.asset.name,
                "is_exit_tax": is_exit_tax,
                "sales": [],
                "bed_breakfast_applies": not is_exit_tax
            }

        sale_date = sale.transaction_date
        end_of_period = sale_date + timedelta(days=28)
        days_remaining = max(0, (end_of_period - date.today()).days)

        sales_by_isin[isin]["sales"].append({
            "date": sale_date.isoformat(),
            "quantity": float(abs(sale.quantity)),
            "proceeds": float(sale.gross_amount - sale.fees),
            "days_remaining": days_remaining,
            "safe_to_buy_date": end_of_period.isoformat()
        })

    return list(sales_by_isin.values())


@router.get("/available-years")
async def get_available_years(
    person_id: Optional[int] = Query(None, description="Person ID for family mode"),
    db: Session = Depends(get_db)
) -> dict:
    """
    Get available tax years based on transaction data.
    Returns years with transactions and the current year.
    """
    from sqlalchemy import extract, func

    # Get distinct years from transactions
    query = db.query(
        extract('year', Transaction.transaction_date).label('year')
    ).distinct()

    if person_id is not None:
        query = query.filter(Transaction.person_id == person_id)

    years_with_data = sorted([int(row.year) for row in query.all()], reverse=True)

    # Also get years from income events
    income_query = db.query(
        extract('year', IncomeEvent.payment_date).label('year')
    ).distinct()

    if person_id is not None:
        income_query = income_query.filter(IncomeEvent.person_id == person_id)

    income_years = [int(row.year) for row in income_query.all()]

    # Combine and deduplicate
    all_years = sorted(set(years_with_data + income_years), reverse=True)

    # Always include current year and previous year
    current_year = date.today().year
    if current_year not in all_years:
        all_years.insert(0, current_year)
    if (current_year - 1) not in all_years:
        all_years.append(current_year - 1)
        all_years = sorted(all_years, reverse=True)

    return {
        "years": all_years,
        "default_year": all_years[0] if all_years else current_year,
        "has_data": len(years_with_data) > 0
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
