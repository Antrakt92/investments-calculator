"""Upload router for Trade Republic PDF reports."""

import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models import get_db, init_db, Asset, Transaction, IncomeEvent, AssetType, TransactionType
from ..parsers import TradeRepublicParser
from ..schemas import UploadResponse

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/trade-republic-pdf", response_model=UploadResponse)
async def upload_trade_republic_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload and parse a Trade Republic annual tax report PDF.
    Extracts transactions, income events, and stores in database.
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

            # Create transaction
            trans_type = TransactionType.BUY if trans.transaction_type == "buy" else TransactionType.SELL
            quantity = trans.quantity if trans.transaction_type == "buy" else -trans.quantity

            db_trans = Transaction(
                asset_id=asset.id,
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

        # Process income events
        for income in parsed.income_events:
            # Get or create asset for dividends/distributions
            asset_id = None
            if income.isin:
                asset = db.query(Asset).filter(Asset.isin == income.isin).first()
                if asset:
                    asset_id = asset.id

            income_event = IncomeEvent(
                asset_id=asset_id,
                income_type=income.income_type.lower(),
                payment_date=income.payment_date,
                gross_amount=income.gross_amount,
                withholding_tax=income.withholding_tax,
                net_amount=income.net_amount,
                source_country=income.country
            )
            db.add(income_event)
            income_count += 1

        db.commit()

        return UploadResponse(
            success=True,
            message=f"Successfully imported {transactions_count} transactions and {income_count} income events",
            transactions_imported=transactions_count,
            income_events_imported=income_count,
            tax_year=parsed.period_end.year
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error parsing PDF: {str(e)}")

    finally:
        # Clean up temp file
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
