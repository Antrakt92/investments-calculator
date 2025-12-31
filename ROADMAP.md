# Irish Tax Calculator - Product Roadmap

## Vision

**Personal Investment Dashboard** - A comprehensive platform for Irish investors to:
- Track their investment portfolio across multiple brokers
- Automatically calculate Irish tax obligations (CGT, Exit Tax, DIRT)
- Import transactions via PDF upload or manual entry
- Get clear guidance for Revenue Form 11/12 filing

---

## Current Status (v0.2)

### ✅ Implemented
- [x] PDF Upload (Trade Republic tax reports)
- [x] Portfolio View (Holdings, Transactions, Income tabs)
- [x] Tax Calculator (CGT 33%, Exit Tax 41%, DIRT 33%)
- [x] Form 11 field reference with panel guidance
- [x] Irish CGT matching rules (same-day, 4-week bed & breakfast, FIFO)
- [x] Exit Tax with deemed disposal tracking (8-year rule)
- [x] Duplicate detection on import
- [x] Gain/Loss calculation per transaction
- [x] Clear All Data functionality
- [x] Upload verification summary
- [x] Income tracking (Interest + Dividends)
- [x] Improved Dashboard with tax breakdown
- [x] Manual transaction entry (Buy/Sell)
- [x] Edit existing transactions
- [x] Delete individual transactions
- [x] Transaction form with validation
- [x] CSV export for transactions
- [x] Print-friendly tax summary
- [x] Automatic CGT loss carry forward between years
- [x] PDF export for tax reports
- [x] Transaction notes/comments
- [x] Improved loading states
- [x] Dark mode toggle

---

## Phase 1: Core Features (Current)

### 1.1 Manual Transaction Entry ✅ COMPLETE
- [x] Add Buy transaction form
- [x] Add Sell transaction form
- [x] Edit existing transactions
- [x] Delete individual transactions
- [x] Form validation and error handling

### 1.2 Data Quality
- [ ] Validate parsed data against PDF totals
- [ ] Show warnings for suspicious data
- [ ] Allow manual corrections
- [x] Transaction notes/comments

### 1.3 Export Features ✅ COMPLETE
- [x] Export tax report as PDF
- [x] Export transactions as CSV
- [x] Print-friendly tax summary

---

## Phase 2: Enhanced Portfolio Tracking

### 2.1 Multi-Year Support
- [ ] View historical data by year
- [x] Carry forward CGT losses automatically
- [ ] Year-over-year comparison
- [ ] Tax history

### 2.2 Multiple Brokers
- [ ] Interactive Brokers (IBKR) - CSV import
- [ ] Degiro - CSV import
- [ ] Revolut - PDF/CSV
- [ ] Generic CSV template

### 2.3 Portfolio Analytics
- [ ] Performance charts (cost basis vs current value)
- [ ] Asset allocation breakdown
- [ ] Monthly income chart
- [ ] Realized gains over time

### 2.4 Tax Optimization
- [ ] Show potential tax savings
- [ ] Loss harvesting suggestions
- [ ] Deemed disposal calendar
- [ ] Tax-efficient selling order

---

## Phase 3: Polish & UX

### 3.1 User Experience
- [ ] Mobile-responsive design
- [x] Dark mode
- [ ] Keyboard shortcuts
- [ ] Tooltips and help text

### 3.2 Notifications
- [ ] Payment deadline reminders
- [ ] Deemed disposal warnings
- [ ] Important dates calendar

### 3.3 Data Backup
- [ ] Export all data as JSON
- [ ] Import from backup
- [ ] Auto-backup before clearing

---

## Phase 4: SaaS (Future)

### 4.1 User Accounts
- [ ] Registration/Login
- [ ] Secure cloud storage
- [ ] Multi-device sync

### 4.2 Subscription
- [ ] Free tier (current year only)
- [ ] Paid tier (full history + features)
- [ ] Payment integration

---

## Known Issues & Bugs to Fix

### Parser Issues
- [ ] Verify thousand separator handling (2,146.00 → 2146.00)
- [ ] Test with different PDF formats
- [ ] Handle missing data gracefully

### Tax Calculations
- [ ] Verify CGT 4-week rule implementation
- [ ] Test Exit Tax with multiple lots
- [ ] Validate Form 11 field mappings

### UI/UX
- [ ] Fix dashboard layout on small screens
- [x] Add loading states to all async operations
- [ ] Better error messages

---

## Technical Improvements

- [ ] Add unit tests for tax calculators
- [ ] Add integration tests for API endpoints
- [ ] Swagger/OpenAPI documentation
- [ ] Error logging
- [ ] Database migrations (Alembic)

---

## Priority Matrix

| Feature | Impact | Effort | Priority |
|---------|--------|--------|----------|
| Manual transaction entry | High | Medium | **P1** |
| Edit/Delete transactions | High | Low | **P1** |
| PDF export | Medium | Medium | P2 |
| CSV export | Medium | Low | **P1** |
| Multi-broker CSV import | High | Medium | P2 |
| Performance charts | Medium | High | P3 |
| Mobile responsive | Medium | Medium | P3 |
