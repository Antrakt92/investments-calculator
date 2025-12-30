"""
Irish Tax Calculator for Trade Republic

A FastAPI application for calculating Irish tax obligations from
Trade Republic PDF tax reports.

Supports:
- CGT (33%) on stocks with Irish matching rules
- Exit Tax (41%) on EU-domiciled funds with deemed disposal tracking
- DIRT (33%) on interest income
- Dividend income reporting
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models import init_db
from .routers import upload_router, portfolio_router, tax_router

# Create FastAPI app
app = FastAPI(
    title="Irish Tax Calculator",
    description="Calculate Irish tax obligations from Trade Republic data",
    version="0.1.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(upload_router)
app.include_router(portfolio_router)
app.include_router(tax_router)


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    init_db()


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Irish Tax Calculator",
        "version": "0.1.0",
        "description": "Calculate Irish tax obligations from Trade Republic data",
        "endpoints": {
            "upload": "/upload/trade-republic-pdf",
            "portfolio": {
                "holdings": "/portfolio/holdings",
                "transactions": "/portfolio/transactions",
                "summary": "/portfolio/summary"
            },
            "tax": {
                "calculate": "/tax/calculate/{tax_year}",
                "deemed_disposals": "/tax/deemed-disposals"
            }
        },
        "tax_rates": {
            "CGT": "33% (€1,270 annual exemption)",
            "Exit Tax": "41% (no exemption, 8-year deemed disposal)",
            "DIRT": "33% (no exemption)"
        },
        "documentation": "/docs"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
