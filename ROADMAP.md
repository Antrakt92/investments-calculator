# Irish Tax Calculator - Product Roadmap

## Vision

**Personal Investment Dashboard** - A comprehensive platform for Irish investors to:
- Track their investment portfolio across multiple brokers
- Automatically calculate Irish tax obligations (CGT, Exit Tax, DIRT)
- Import transactions via PDF upload or manual entry
- Get clear guidance for Revenue Form 11/12 filing
- Support joint/family tax returns for married couples

---

## Current Status (v0.3)

### ✅ Implemented
- [x] PDF Upload (Trade Republic tax reports)
- [x] Portfolio View (Holdings, Transactions, Income tabs)
- [x] Tax Calculator (CGT 33%, Exit Tax 41%, DIRT 33%)
- [x] Form 11 field reference with panel guidance
- [x] Irish CGT matching rules (same-day, 4-week bed & breakfast, FIFO)
- [x] Exit Tax with loss offsetting
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
- [x] CGT loss carry forward input
- [x] PDF export for tax reports
- [x] Transaction notes/comments
- [x] Dark mode toggle
- [x] Robust PDF parsing (European decimals, concatenated numbers)

---

## Phase 1: Core Improvements (Current Sprint)

### 1.1 Unit Tests ⬅️ NEXT
- [ ] Tests for Trade Republic PDF parser
- [ ] Tests for CGT calculator (FIFO matching, 4-week rule)
- [ ] Tests for Exit Tax calculator
- [ ] Tests for API endpoints
- [ ] CI/CD pipeline with test automation

### 1.2 Data Validation
- [ ] Validate parsed data against PDF totals
- [ ] Show warnings for suspicious data (e.g., negative prices)
- [ ] Highlight potential parsing errors
- [ ] Allow manual corrections inline

### 1.3 Deemed Disposal (8-Year Rule)
- [ ] Track purchase dates for all EU ETF holdings
- [ ] Calculate deemed disposal dates (8 years from purchase)
- [ ] Show upcoming deemed disposal calendar
- [ ] Calculate deemed disposal tax liability
- [ ] Warning notifications for approaching dates

---

## Phase 2: Family/Joint Tax Returns 👨‍👩‍👧

### 2.1 Multi-Person Support
- [ ] Add "Person" entity (name, PPS number optional)
- [ ] Default: Primary user + ability to add spouse
- [ ] Each transaction linked to a person
- [ ] Filter views by person

### 2.2 Separate Tracking
- [ ] Portfolio view: "My Holdings" vs "Spouse Holdings" tabs
- [ ] Transaction list: Person column with filter
- [ ] Income: Split by person
- [ ] Clear visual distinction (colors/icons)

### 2.3 Individual Tax Calculations
- [ ] CGT calculated separately per person
- [ ] Each person gets their own €1,270 exemption
- [ ] Exit Tax per person
- [ ] DIRT per person (or combined if joint account)
- [ ] Individual tax summaries

### 2.4 Joint Filing View
- [ ] Combined tax summary for Form 11
- [ ] Show: Person 1 taxes + Person 2 taxes = Total
- [ ] Joint Form 11 field reference
- [ ] PDF export with both persons' data

---

## Phase 3: Multi-Year Support

### 3.1 Year Selection
- [ ] Tax year selector (2023, 2024, 2025...)
- [ ] View historical data by year
- [ ] Automatic year detection from transactions

### 3.2 Loss Carry Forward
- [ ] Track CGT losses per year
- [ ] Automatic carry forward to next year
- [ ] Loss history view
- [ ] Manual adjustment option

### 3.3 Year Comparison
- [ ] Year-over-year tax comparison
- [ ] Income trends across years
- [ ] Portfolio growth timeline

---

## Phase 4: Tax Optimization

### 4.1 Tax Planning Tools
- [ ] Show potential tax savings opportunities
- [ ] Loss harvesting suggestions
- [ ] "What-if" scenarios (sell X shares = Y tax)
- [ ] Tax-efficient selling order recommendations

### 4.2 Alerts & Notifications
- [ ] Payment deadline reminders (Dec 15, Oct 31)
- [ ] Deemed disposal warnings (30/60/90 days before)
- [ ] 4-week rule warnings before re-buying

---

## Phase 5: Polish & UX

### 5.1 User Experience
- [ ] Mobile-responsive design
- [ ] Keyboard shortcuts
- [ ] Tooltips and help text everywhere
- [ ] Onboarding tutorial

### 5.2 Data Management
- [ ] Export all data as JSON backup
- [ ] Import from JSON backup
- [ ] Auto-backup before destructive operations
- [ ] Data encryption at rest

---

## Backlog (Future Phases)

### Multiple Brokers Support
> *Moved to backlog - complex to implement, will tackle later*
- [ ] Interactive Brokers (IBKR) - CSV import
- [ ] Degiro - CSV import
- [ ] Revolut - PDF/CSV
- [ ] Generic CSV import template
- [ ] Broker-agnostic transaction format

### Portfolio Analytics
- [ ] Performance charts (cost basis vs current value)
- [ ] Asset allocation pie chart
- [ ] Monthly income chart
- [ ] Realized gains timeline
- [ ] Currency exposure breakdown

### SaaS Features (If commercializing)
- [ ] User accounts (registration/login)
- [ ] Cloud storage with encryption
- [ ] Multi-device sync
- [ ] Subscription tiers

---

## Known Issues & Bugs

### Parser
- [x] ~~European decimal format (7,00 → 7.00)~~ FIXED
- [x] ~~Concatenated numbers (1.0000342 → 1.0000 342)~~ FIXED
- [x] ~~ISIN persistence across pages~~ FIXED
- [ ] Test with more PDF formats/years

### Tax Calculations
- [ ] Verify CGT 4-week rule edge cases
- [ ] Test Exit Tax with complex lot matching
- [ ] Validate Form 11 field mappings with accountant

### UI/UX
- [ ] Dashboard layout on mobile
- [ ] Better error messages for failed uploads
- [ ] Loading skeleton states

---

## Technical Debt

- [ ] Add comprehensive unit tests
- [ ] Add integration tests for API
- [ ] Swagger/OpenAPI documentation
- [ ] Structured error logging
- [ ] Database migrations (Alembic)
- [ ] Type hints everywhere
- [ ] Code documentation

---

## Priority Matrix

| Feature | Impact | Effort | Priority |
|---------|--------|--------|----------|
| Unit Tests | High | Medium | **P0** |
| Family/Joint Returns | High | High | **P1** |
| Deemed Disposal Tracking | High | Medium | **P1** |
| Multi-Year Support | Medium | Medium | **P2** |
| Tax Optimization Tools | Medium | High | **P3** |
| Multiple Brokers | High | Very High | **Backlog** |
| Portfolio Analytics | Low | High | **Backlog** |

---

## Next Actions

1. **Now**: Add unit tests for parser and calculators
2. **Next**: Implement Family/Joint returns
3. **Then**: Deemed Disposal tracking
4. **Later**: Multi-year support
