"""Upload router for Trade Republic PDF reports."""

import tempfile
from decimal import Decimal
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models import get_db, init_db, Asset, Transaction, IncomeEvent, AssetType, TransactionType
from ..parsers import TradeRepublicParser
from ..schemas import UploadResponse

router = APIRouter(prefix="/upload", tags=["upload"])


from typing import Optional
from fastapi import Query

@router.post("/trade-republic-pdf")
async def upload_trade_republic_pdf(
    file: UploadFile = File(...),
    person_id: Optional[int] = Query(None, description="Person ID for family tax returns"),
    db: Session = Depends(get_db)
):
    """
    Upload and parse a Trade Republic annual tax report PDF.
    Extracts transactions, income events, and stores in database.
    Returns detailed summary for verification.
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    # Initialize database
    init_db()

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # Parse the PDF
        parser = TradeRepublicParser()
        parsed = parser.parse(tmp_path)

        transactions_count = 0
        income_count = 0
        skipped_duplicates = 0

        # Track totals for verification
        total_buys = Decimal("0")
        total_sells = Decimal("0")
        total_interest = Decimal("0")
        total_dividends = Decimal("0")
        buy_count = 0
        sell_count = 0

        # Process transactions
        for trans in parsed.transactions:
            if not trans.isin:
                continue

            # Get or create asset
            asset = db.query(Asset).filter(Asset.isin == trans.isin).first()
            if not asset:
                asset_type = _determine_asset_type(trans.isin, trans.name)
                asset = Asset(
                    isin=trans.isin,
                    name=trans.name,
                    asset_type=asset_type,
                    country=trans.country,
                    is_eu_fund=asset_type == AssetType.ETF_EU
                )
                db.add(asset)
                db.flush()

            # Check for duplicate transaction (same asset, date, type, quantity, amount)
            trans_type = TransactionType.BUY if trans.transaction_type == "buy" else TransactionType.SELL
            quantity = trans.quantity if trans.transaction_type == "buy" else -trans.quantity

            existing = db.query(Transaction).filter(
                Transaction.asset_id == asset.id,
                Transaction.transaction_date == trans.transaction_date,
                Transaction.transaction_type == trans_type,
                Transaction.gross_amount == trans.market_value
            ).first()

            if existing:
                skipped_duplicates += 1
                continue

            db_trans = Transaction(
                asset_id=asset.id,
                person_id=person_id,  # For family tax returns
                transaction_type=trans_type,
                transaction_date=trans.transaction_date,
                settlement_date=trans.settlement_date,
                quantity=quantity,
                unit_price=trans.market_value / trans.quantity if trans.quantity else 0,
                gross_amount=trans.market_value,
                fees=0,
                net_amount=trans.net_amount or trans.market_value,
                currency=trans.currency,
                exchange_rate=trans.exchange_rate,
                amount_eur=trans.market_value
            )
            db.add(db_trans)
            transactions_count += 1

            # Track totals
            if trans.transaction_type == "buy":
                total_buys += trans.market_value
                buy_count += 1
            else:
                total_sells += trans.market_value
                sell_count += 1

        # Process income events
        for income in parsed.income_events:
            # Get or create asset for dividends/distributions
            asset_id = None
            if income.isin:
                asset = db.query(Asset).filter(Asset.isin == income.isin).first()
                if asset:
                    asset_id = asset.id

            # Check for duplicate income event
            existing_income = db.query(IncomeEvent).filter(
                IncomeEvent.asset_id == asset_id,
                IncomeEvent.payment_date == income.payment_date,
                IncomeEvent.income_type == income.income_type.lower(),
                IncomeEvent.gross_amount == income.gross_amount
            ).first()

            if existing_income:
                skipped_duplicates += 1
                continue

            income_event = IncomeEvent(
                asset_id=asset_id,
                person_id=person_id,  # For family tax returns
                income_type=income.income_type.lower(),
                payment_date=income.payment_date,
                gross_amount=income.gross_amount,
                withholding_tax=income.withholding_tax,
                net_amount=income.net_amount,
                source_country=income.country
            )
            db.add(income_event)
            income_count += 1

            # Track totals
            if income.income_type.lower() == "interest":
                total_interest += income.gross_amount
            else:
                total_dividends += income.gross_amount

        db.commit()

        # Compile validation warnings (exclude info-level Section VI warnings which are normal)
        validation_warnings = [
            {
                "type": w.warning_type,
                "severity": w.severity,
                "message": w.message,
                "line": w.line_content,
                "details": w.details
            }
            for w in parsed.warnings
            if w.severity != "info"  # Don't clutter with info messages
        ]

        # Group warnings by type for summary
        warning_summary = {}
        for w in validation_warnings:
            wtype = w["type"]
            if wtype not in warning_summary:
                warning_summary[wtype] = 0
            warning_summary[wtype] += 1

        return {
            "success": True,
            "message": f"Successfully imported {transactions_count} transactions and {income_count} income events",
            "transactions_imported": transactions_count,
            "income_events_imported": income_count,
            "skipped_duplicates": skipped_duplicates,
            "tax_year": parsed.period_end.year,
            "period": {
                "start": parsed.period_start.isoformat(),
                "end": parsed.period_end.isoformat()
            },
            "summary": {
                "buys": {
                    "count": buy_count,
                    "total": float(total_buys)
                },
                "sells": {
                    "count": sell_count,
                    "total": float(total_sells)
                },
                "interest": {
                    "count": sum(1 for i in parsed.income_events if i.income_type.lower() == "interest"),
                    "total": float(total_interest)
                },
                "dividends": {
                    "count": sum(1 for i in parsed.income_events if i.income_type.lower() != "interest"),
                    "total": float(total_dividends)
                }
            },
            "validation": {
                "skipped_no_isin": parsed.skipped_no_isin,
                "skipped_invalid_format": parsed.skipped_invalid_format,
                "parsing_errors": parsed.parsing_errors,
                "warning_count": len(validation_warnings),
                "warning_summary": warning_summary,
                "warnings": validation_warnings[:20]  # Limit to first 20 warnings
            }
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error parsing PDF: {str(e)}")

    finally:
        # Clean up temp file
        tmp_path.unlink(missing_ok=True)


@router.delete("/clear-data")
async def clear_all_data(db: Session = Depends(get_db)):
    """Delete all imported data from database."""
    try:
        # Delete in order due to foreign keys
        deleted_income = db.query(IncomeEvent).delete()
        deleted_trans = db.query(Transaction).delete()
        deleted_assets = db.query(Asset).delete()
        db.commit()

        return {
            "success": True,
            "message": "All data cleared successfully",
            "deleted": {
                "transactions": deleted_trans,
                "income_events": deleted_income,
                "assets": deleted_assets
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error clearing data: {str(e)}")


@router.post("/debug-pdf")
async def debug_pdf(file: UploadFile = File(...)):
    """
    Debug endpoint: Parse PDF and return raw extracted data without saving.
    Useful for diagnosing parsing issues.
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        parser = TradeRepublicParser()
        parsed = parser.parse(tmp_path)

        # Return detailed debug info
        return {
            "success": True,
            "metadata": {
                "client_id": parsed.client_id,
                "period_start": parsed.period_start.isoformat(),
                "period_end": parsed.period_end.isoformat(),
                "currency": parsed.currency,
                "country": parsed.country
            },
            "transactions": [
                {
                    "isin": t.isin,
                    "name": t.name,
                    "type": t.transaction_type,
                    "date": t.transaction_date.isoformat(),
                    "quantity": float(t.quantity),
                    "market_value": float(t.market_value),
                    "net_amount": float(t.net_amount),
                    "exchange_rate": float(t.exchange_rate),
                    "asset_type": t.asset_type
                }
                for t in parsed.transactions
            ],
            "income_events": [
                {
                    "isin": i.isin,
                    "name": i.name,
                    "type": i.income_type,
                    "date": i.payment_date.isoformat(),
                    "gross_amount": float(i.gross_amount),
                    "net_amount": float(i.net_amount),
                    "withholding_tax": float(i.withholding_tax),
                    "country": i.country
                }
                for i in parsed.income_events
            ],
            "summary": {
                "total_transactions": len(parsed.transactions),
                "total_income_events": len(parsed.income_events),
                "transactions_by_type": {
                    "buy": sum(1 for t in parsed.transactions if t.transaction_type == "buy"),
                    "sell": sum(1 for t in parsed.transactions if t.transaction_type == "sell")
                },
                "income_by_type": {
                    "interest": sum(1 for i in parsed.income_events if i.income_type.lower() == "interest"),
                    "dividend": sum(1 for i in parsed.income_events if i.income_type.lower() in ["dividend", "distribution"])
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing PDF: {str(e)}")
    finally:
        tmp_path.unlink(missing_ok=True)


def _determine_asset_type(isin: str, name: str) -> AssetType:
    """Determine asset type for Irish tax purposes."""
    from ..services.exit_tax_calculator import ExitTaxCalculator

    if ExitTaxCalculator.is_exit_tax_asset(isin, name):
        return AssetType.ETF_EU

    prefix = isin[:2] if isin else ""
    name_lower = name.lower() if name else ""

    # US ETFs are CGT, not Exit Tax
    if prefix == "US" and any(kw in name_lower for kw in ["etf", "fund", "index"]):
        return AssetType.ETF_NON_EU

    return AssetType.STOCK
