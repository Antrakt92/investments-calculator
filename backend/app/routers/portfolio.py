"""Portfolio router for viewing holdings and transactions."""

from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import get_db, Asset, Transaction, Holding, TransactionType
from ..schemas import HoldingResponse, TransactionResponse

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("/holdings")
async def get_holdings(db: Session = Depends(get_db)) -> list[dict]:
    """Get current holdings with cost basis."""
    # Aggregate transactions per asset
    holdings = []

    assets = db.query(Asset).all()

    for asset in assets:
        # Get all transactions for this asset
        transactions = db.query(Transaction).filter(
            Transaction.asset_id == asset.id
        ).order_by(Transaction.transaction_date).all()

        total_quantity = Decimal("0")
        total_cost = Decimal("0")

        for trans in transactions:
            if trans.transaction_type == TransactionType.BUY:
                total_quantity += trans.quantity
                total_cost += trans.gross_amount
            elif trans.transaction_type == TransactionType.SELL:
                # Calculate cost basis consumed (simple average)
                if total_quantity > 0:
                    avg_cost = total_cost / total_quantity
                    qty_sold = abs(trans.quantity)
                    total_quantity -= qty_sold
                    total_cost -= avg_cost * qty_sold

        if total_quantity > 0:
            holdings.append({
                "isin": asset.isin,
                "name": asset.name,
                "asset_type": asset.asset_type.value,
                "quantity": float(total_quantity),
                "average_cost": float(total_cost / total_quantity) if total_quantity > 0 else 0,
                "total_cost_basis": float(total_cost),
                "is_exit_tax_asset": asset.asset_type.value == "etf_eu",
            })

    return holdings


@router.get("/transactions")
async def get_transactions(
    db: Session = Depends(get_db),
    isin: Optional[str] = Query(None, description="Filter by ISIN"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    transaction_type: Optional[str] = Query(None, description="buy or sell"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0)
) -> list[dict]:
    """Get transaction history with optional filters."""
    query = db.query(Transaction).join(Asset)

    if isin:
        query = query.filter(Asset.isin == isin)

    if start_date:
        query = query.filter(Transaction.transaction_date >= start_date)

    if end_date:
        query = query.filter(Transaction.transaction_date <= end_date)

    if transaction_type:
        trans_type = TransactionType.BUY if transaction_type.lower() == "buy" else TransactionType.SELL
        query = query.filter(Transaction.transaction_type == trans_type)

    transactions = query.order_by(
        Transaction.transaction_date.desc()
    ).offset(offset).limit(limit).all()

    # Calculate gain/loss for each transaction
    # Need to track cost basis per asset using simple average method
    result = []
    for t in transactions:
        realized_gl = None

        if t.transaction_type == TransactionType.SELL:
            # Calculate gain/loss: get all buys before this sell for the same asset
            all_trans = db.query(Transaction).filter(
                Transaction.asset_id == t.asset_id,
                Transaction.transaction_date <= t.transaction_date
            ).order_by(Transaction.transaction_date).all()

            total_qty = Decimal("0")
            total_cost = Decimal("0")

            for tr in all_trans:
                if tr.id == t.id:
                    # This is the current sell - calculate gain/loss
                    if total_qty > 0:
                        avg_cost = total_cost / total_qty
                        qty_sold = abs(t.quantity)
                        cost_basis = avg_cost * qty_sold
                        realized_gl = float(t.gross_amount - cost_basis)
                    break
                elif tr.transaction_type == TransactionType.BUY:
                    total_qty += abs(tr.quantity)
                    total_cost += tr.gross_amount
                elif tr.transaction_type == TransactionType.SELL:
                    if total_qty > 0:
                        avg_cost = total_cost / total_qty
                        qty_sold = abs(tr.quantity)
                        total_qty -= qty_sold
                        total_cost -= avg_cost * qty_sold

        result.append({
            "id": t.id,
            "isin": t.asset.isin,
            "name": t.asset.name,
            "transaction_type": t.transaction_type.value,
            "transaction_date": t.transaction_date.isoformat(),
            "quantity": float(abs(t.quantity)),
            "unit_price": float(t.unit_price),
            "gross_amount": float(t.gross_amount),
            "fees": float(t.fees),
            "net_amount": float(t.net_amount),
            "realized_gain_loss": realized_gl
        })

    return result


@router.get("/summary")
async def get_portfolio_summary(db: Session = Depends(get_db)) -> dict:
    """Get portfolio summary statistics."""
    # Count assets by type
    asset_counts = db.query(
        Asset.asset_type,
        func.count(Asset.id)
    ).group_by(Asset.asset_type).all()

    # Get transaction counts
    trans_count = db.query(func.count(Transaction.id)).scalar()

    return {
        "total_assets": sum(c[1] for c in asset_counts),
        "assets_by_type": {c[0].value: c[1] for c in asset_counts},
        "total_transactions": trans_count
    }
