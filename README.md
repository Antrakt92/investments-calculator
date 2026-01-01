# Irish Tax Calculator for Trade Republic

A web application that parses Trade Republic tax reports (PDF) and calculates Irish tax obligations including CGT, Exit Tax, and DIRT.

**Version: 0.3** | [View Roadmap](ROADMAP.md)

## ✨ Features

### Implemented
- ✅ **PDF Upload** - Parse Trade Republic annual tax reports
- ✅ **Portfolio Dashboard** - Holdings, transactions, income tracking
- ✅ **Tax Calculator** - CGT 33%, Exit Tax 41%, DIRT 33%
- ✅ **Irish Matching Rules** - Same-day, 4-week bed & breakfast, FIFO
- ✅ **Deemed Disposal Tracking** - 8-year rule with time remaining, urgency alerts
- ✅ **Manual Entry** - Add/edit/delete transactions
- ✅ **CSV Export** - Export transactions
- ✅ **PDF Export** - Tax report for printing
- ✅ **Form 11 Guidance** - Field references for Revenue filing
- ✅ **Dark Mode** - Toggle light/dark theme
- ✅ **Loss Carry Forward** - Input losses from previous years
- ✅ **Unit Tests** - 45 tests for CGT, Exit Tax, and parser

### Coming Soon
- 👨‍👩‍👧 Family/Joint tax returns (husband + wife separate tracking, combined Form 11)
- 📊 Multi-year support

---

## 🚀 Quick Start (Windows)

### First Time Setup

```powershell
# Clone the repository
git clone https://github.com/Antrakt92/investments-calculator.git
cd investments-calculator

# Backend setup
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup (new terminal)
cd frontend
npm install
```

### Daily Usage

```powershell
# Update code and restart (run from project root)
cd C:\Users\dimon\Documents\GitHub\investments-calculator
git pull

# Delete old database to start fresh (optional)
Remove-Item -Force data\irish_tax.db -ErrorAction SilentlyContinue

# Start backend
cd backend
venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8000

# Start frontend (new terminal)
cd frontend
npm run dev
```

**Access the app:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## 🧪 Running Tests

```bash
cd backend
pip install pytest pytest-asyncio pytest-cov

# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=app --cov-report=html
```

**Test Coverage:**
- 19 tests for CGT Calculator (matching rules, exemption, losses)
- 26 tests for Exit Tax Calculator (classification, deemed disposal, FIFO)
- Parser tests (regex patterns, number normalization)

---

## 💰 Tax Rules Implemented

### CGT (Capital Gains Tax) - 33%
- **Annual exemption**: €1,270
- **Irish matching rules** (NOT FIFO like Trade Republic uses):
  1. Same-day acquisitions
  2. Acquisitions within next 4 weeks (bed & breakfast rule)
  3. FIFO for remaining shares
- **Payment deadlines**:
  - Gains Jan-Nov: Due December 15
  - Gains December: Due January 31

### Exit Tax - 41%
- Applies to Irish/EU domiciled funds (ISIN: IE, LU, DE, FR, etc.)
- **Deemed disposal every 8 years** from purchase (tracked with urgency alerts)
- **No annual exemption**
- Losses CAN offset gains within Exit Tax regime
- Losses CANNOT offset CGT gains (separate regime)
- Dashboard widget shows upcoming deemed disposals with time remaining

### DIRT - 33%
- Applies to interest income (Trade Republic cash interest)
- **Trade Republic doesn't withhold** - must self-declare
- No exemption

---

## 📁 Project Structure

```
├── backend/
│   ├── app/
│   │   ├── models/      # Database models (SQLAlchemy)
│   │   ├── parsers/     # PDF parsing (Trade Republic)
│   │   ├── routers/     # API endpoints
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── services/    # Tax calculators
│   │   └── main.py      # FastAPI app
│   ├── tests/           # Unit tests (pytest)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/       # React pages
│   │   ├── services/    # API client
│   │   └── App.tsx
│   └── package.json
├── data/                # SQLite database
├── ROADMAP.md          # Feature roadmap
└── README.md
```

---

## 🔌 API Endpoints

### Upload
- `POST /upload/trade-republic-pdf` - Upload and parse PDF
- `POST /upload/debug-pdf` - Debug parsing without saving
- `DELETE /upload/clear-data` - Clear all data

### Portfolio
- `GET /portfolio/holdings` - Current holdings with cost basis
- `GET /portfolio/transactions` - Transaction history
- `GET /portfolio/income` - Interest and dividends
- `POST /portfolio/transactions` - Add transaction
- `PUT /portfolio/transactions/{id}` - Edit transaction
- `DELETE /portfolio/transactions/{id}` - Delete transaction

### Tax
- `GET /tax/calculate/{tax_year}` - Calculate all taxes
- `GET /tax/deemed-disposals` - Upcoming deemed disposals
- `GET /tax/losses-to-carry-forward/{year}` - Get loss carryforward

---

## 📋 Form 11 Guidance

# Run development server
npm run dev
```
```
# В терминале с бэкендом нажмите Ctrl+C чтобы остановить сервер

# Обновите код
cd C:\Users\dimon\Documents\GitHub\investments-calculator
git pull

# Удалите старую базу данных (чтобы начать заново)
Remove-Item -Force data\irish_tax.db -ErrorAction SilentlyContinue

# Перезапустите бэкенд
cd backend
venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8000

The frontend will be available at http://localhost:3000 and will proxy API requests to the backend.
```
## API Endpoints

## ⚠️ Important Notes

### Trade Republic vs Irish Tax Rules

Trade Republic uses **FIFO** for calculating gains. However, Irish CGT uses different matching rules. This calculator **recalculates all gains** using the correct Irish rules.

### Exit Tax vs CGT

| Asset Type | ISIN Prefix | Tax Rate | Exemption |
|------------|-------------|----------|-----------|
| EU ETFs/Funds | IE, LU, DE, FR | 41% Exit Tax | None |
| US ETFs | US | 33% CGT | €1,270 |
| Individual Stocks | Any | 33% CGT | €1,270 |

### DIRT Reminder

Trade Republic pays interest but does **NOT** withhold Irish DIRT. You must self-declare this on Form 11.

---

## 🛠️ Tech Stack

**Backend:**
- Python 3.11+ / FastAPI / SQLAlchemy / pdfplumber

**Frontend:**
- React 18 / TypeScript / Vite / React Router

**Testing:**
- pytest / pytest-asyncio / pytest-cov

---

## 📄 Disclaimer

This tool is for **informational purposes only**. Always consult a qualified tax professional for your specific situation. The calculations may not account for all tax rules, exemptions, or individual circumstances.

---

## 📝 License

This tool is for informational purposes only. Always consult a tax professional for your specific situation. The calculations may not account for all tax rules and exemptions.

