"""Portfolio router for viewing holdings and transactions."""

from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import get_db, Asset, Transaction, Holding, TransactionType, IncomeEvent, AssetType
from ..schemas import HoldingResponse, TransactionResponse
from ..services.exit_tax_calculator import ExitTaxCalculator

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class TransactionCreate(BaseModel):
    """Schema for creating a new transaction."""
    isin: str
    name: str
    transaction_type: str  # "buy" or "sell"
    transaction_date: date
    quantity: float
    unit_price: float
    fees: float = 0


class TransactionUpdate(BaseModel):
    """Schema for updating a transaction."""
    transaction_date: Optional[date] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    fees: Optional[float] = None


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


@router.get("/income")
async def get_income_events(
    db: Session = Depends(get_db),
    income_type: Optional[str] = Query(None, description="Filter by type: interest, dividend, distribution"),
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0)
) -> list[dict]:
    """Get income events (dividends, interest, distributions)."""
    query = db.query(IncomeEvent)

    if income_type:
        query = query.filter(IncomeEvent.income_type == income_type.lower())

    if start_date:
        query = query.filter(IncomeEvent.payment_date >= start_date)

    if end_date:
        query = query.filter(IncomeEvent.payment_date <= end_date)

    events = query.order_by(
        IncomeEvent.payment_date.desc()
    ).offset(offset).limit(limit).all()

    result = []
    for e in events:
        # Get asset name if linked
        asset_name = None
        asset_isin = None
        if e.asset_id:
            asset = db.query(Asset).filter(Asset.id == e.asset_id).first()
            if asset:
                asset_name = asset.name
                asset_isin = asset.isin

        result.append({
            "id": e.id,
            "income_type": e.income_type,
            "payment_date": e.payment_date.isoformat(),
            "gross_amount": float(e.gross_amount),
            "withholding_tax": float(e.withholding_tax) if e.withholding_tax else 0,
            "net_amount": float(e.net_amount),
            "source_country": e.source_country,
            "asset_name": asset_name,
            "asset_isin": asset_isin,
            "tax_treatment": "DIRT 33%" if e.income_type == "interest" else "Marginal Rate"
        })

    return result


# ============ Transaction CRUD ============

@router.post("/transactions")
async def create_transaction(
    data: TransactionCreate,
    db: Session = Depends(get_db)
) -> dict:
    """Create a new transaction manually."""
    # Get or create asset
    asset = db.query(Asset).filter(Asset.isin == data.isin).first()
    if not asset:
        # Determine asset type
        is_exit_tax = ExitTaxCalculator.is_exit_tax_asset(data.isin, data.name)
        asset_type = AssetType.ETF_EU if is_exit_tax else AssetType.STOCK

        asset = Asset(
            isin=data.isin,
            name=data.name,
            asset_type=asset_type,
            is_eu_fund=is_exit_tax
        )
        db.add(asset)
        db.flush()

    # Calculate amounts
    quantity = Decimal(str(data.quantity))
    unit_price = Decimal(str(data.unit_price))
    fees = Decimal(str(data.fees))
    gross_amount = quantity * unit_price
    net_amount = gross_amount - fees if data.transaction_type == "buy" else gross_amount + fees

    # Create transaction
    trans_type = TransactionType.BUY if data.transaction_type == "buy" else TransactionType.SELL
    trans_quantity = quantity if trans_type == TransactionType.BUY else -quantity

    transaction = Transaction(
        asset_id=asset.id,
        transaction_type=trans_type,
        transaction_date=data.transaction_date,
        settlement_date=data.transaction_date,
        quantity=trans_quantity,
        unit_price=unit_price,
        gross_amount=gross_amount,
        fees=fees,
        net_amount=net_amount,
        currency="EUR",
        exchange_rate=Decimal("1.0000"),
        amount_eur=gross_amount
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return {
        "success": True,
        "message": f"Transaction created successfully",
        "transaction": {
            "id": transaction.id,
            "isin": asset.isin,
            "name": asset.name,
            "transaction_type": data.transaction_type,
            "transaction_date": data.transaction_date.isoformat(),
            "quantity": float(quantity),
            "unit_price": float(unit_price),
            "gross_amount": float(gross_amount),
            "fees": float(fees)
        }
    }


@router.delete("/transactions/{transaction_id}")
async def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db)
) -> dict:
    """Delete a transaction by ID."""
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    db.delete(transaction)
    db.commit()

    return {
        "success": True,
        "message": f"Transaction {transaction_id} deleted successfully"
    }


@router.put("/transactions/{transaction_id}")
async def update_transaction(
    transaction_id: int,
    data: TransactionUpdate,
    db: Session = Depends(get_db)
) -> dict:
    """Update a transaction."""
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Update fields if provided
    if data.transaction_date is not None:
        transaction.transaction_date = data.transaction_date
        transaction.settlement_date = data.transaction_date

    if data.quantity is not None:
        quantity = Decimal(str(data.quantity))
        if transaction.transaction_type == TransactionType.SELL:
            quantity = -abs(quantity)
        transaction.quantity = quantity

    if data.unit_price is not None:
        unit_price = Decimal(str(data.unit_price))
        transaction.unit_price = unit_price
        # Recalculate amounts
        quantity = abs(transaction.quantity)
        transaction.gross_amount = quantity * unit_price
        transaction.amount_eur = transaction.gross_amount

    if data.fees is not None:
        transaction.fees = Decimal(str(data.fees))
        # Recalculate net amount
        if transaction.transaction_type == TransactionType.BUY:
            transaction.net_amount = transaction.gross_amount - transaction.fees
        else:
            transaction.net_amount = transaction.gross_amount + transaction.fees

    db.commit()
    db.refresh(transaction)

    return {
        "success": True,
        "message": f"Transaction {transaction_id} updated successfully",
        "transaction": {
            "id": transaction.id,
            "transaction_date": transaction.transaction_date.isoformat(),
            "quantity": float(abs(transaction.quantity)),
            "unit_price": float(transaction.unit_price),
            "gross_amount": float(transaction.gross_amount),
            "fees": float(transaction.fees)
        }
    }


@router.get("/assets")
async def get_assets(db: Session = Depends(get_db)) -> list[dict]:
    """Get list of all assets for transaction form dropdown."""
    assets = db.query(Asset).all()
    return [
        {
            "isin": a.isin,
            "name": a.name,
            "asset_type": a.asset_type.value
        }
        for a in assets
    ]
