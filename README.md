# Irish Tax Calculator for Trade Republic

A web application that parses Trade Republic tax reports (PDF) and calculates Irish tax obligations.

## Features

### PDF Parser
- Extracts transactions from Section VII (History of Transactions and Corporate Actions)
- Extracts income data from Section V (interest payments, dividends)
- Extracts gains/losses from Section VI
- Stores everything in SQLite database

### Tax Calculators

#### CGT (Capital Gains Tax) - 33%
- Annual exemption: €1,270
- **Irish matching rules** (NOT FIFO like Trade Republic uses):
  1. Same-day acquisitions
  2. Acquisitions within next 4 weeks (bed & breakfast rule)
  3. FIFO for remaining shares
- Two payment deadlines:
  - Gains Jan-Nov: Due December 15
  - Gains December: Due January 31

#### Exit Tax - 41%
- Applies to Irish/EU domiciled funds (ISIN starting with IE, LU, DE, etc.)
- **Deemed disposal every 8 years** from purchase
- No annual exemption
- Losses cannot offset CGT gains (separate regime)

#### DIRT - 33%
- Applies to interest income
- Trade Republic doesn't withhold - must self-declare
- No exemption

### Portfolio Dashboard
- Current holdings with cost basis
- Transaction history with filters
- Asset type classification (CGT vs Exit Tax assets)

### Tax Report Output
- Summary of each tax type owed
- Form 11/Form 12 field mappings
- Payment deadline reminders

## Tech Stack

### Backend
- **Python 3.11+**
- **FastAPI** - Modern async web framework
- **SQLite** - Database (via SQLAlchemy)
- **pdfplumber** - PDF parsing

### Frontend
- **React 18** with TypeScript
- **Vite** - Build tool
- **React Router** - Navigation

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── models/      # Database models
│   │   ├── parsers/     # PDF parsing
│   │   ├── routers/     # API endpoints
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── services/    # Tax calculators
│   │   └── main.py      # FastAPI app
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/       # React pages
│   │   ├── services/    # API client
│   │   └── App.tsx
│   └── package.json
└── data/                # SQLite database
```

## Getting Started

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

The frontend will be available at http://localhost:3000 and will proxy API requests to the backend.

## API Endpoints

### Upload
- `POST /upload/trade-republic-pdf` - Upload and parse a Trade Republic PDF

### Portfolio
- `GET /portfolio/holdings` - Get current holdings
- `GET /portfolio/transactions` - Get transaction history
- `GET /portfolio/summary` - Get portfolio summary

### Tax
- `GET /tax/calculate/{tax_year}` - Calculate taxes for a year
- `GET /tax/deemed-disposals` - Get upcoming deemed disposal events

## Important Notes

### Trade Republic vs Irish Tax Rules

Trade Republic uses **FIFO** (First In, First Out) for calculating gains. However, Irish CGT uses different matching rules:

1. **Same-day rule**: Match disposal with same-day acquisitions first
2. **Bed & Breakfast rule**: Match with acquisitions in the next 4 weeks
3. **FIFO**: Only then use FIFO for remaining shares

This calculator recalculates all gains using the correct Irish rules.

### Exit Tax vs CGT

EU-domiciled funds (ISIN starting with IE, LU, DE, etc.) are subject to **Exit Tax at 41%**, not CGT:
- No annual exemption
- 8-year deemed disposal rule
- Losses cannot offset CGT gains

US-domiciled ETFs (ISIN starting with US) are subject to **CGT at 33%**.

### DIRT

Trade Republic pays interest on cash balances but does **not** withhold Irish DIRT. You must self-declare this interest income.

## Form 11 Guidance

The calculator provides mappings to Form 11 fields:

- **Panel D**: Deposit Interest (DIRT)
- **Panel E**: Capital Gains and Exit Tax
- **Panel F**: Foreign Dividends

## Disclaimer

This tool is for informational purposes only. Always consult a tax professional for your specific situation. The calculations may not account for all tax rules and exemptions.
