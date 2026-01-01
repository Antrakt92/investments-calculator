# Irish Tax Calculator - Product Roadmap

## Vision

**Personal Investment Dashboard** - A comprehensive platform for Irish investors to:
- Track their investment portfolio across multiple brokers
- Automatically calculate Irish tax obligations (CGT, Exit Tax, DIRT)
- Import transactions via PDF upload or manual entry
- Get clear guidance for Revenue Form 11/12 filing
- Support joint/family tax returns for married couples

---

## Current Status (v0.4.2)

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
- [x] Manual transaction entry (Buy/Sell) with person assignment
- [x] Edit existing transactions
- [x] Delete individual transactions
- [x] Transaction form with validation
- [x] CSV export for transactions (with person filter)
- [x] Print-friendly tax summary
- [x] CGT loss carry forward input
- [x] PDF export for tax reports
- [x] Transaction notes/comments
- [x] Dark mode toggle
- [x] Robust PDF parsing (European decimals, concatenated numbers)
- [x] Unit tests (45 tests: CGT, Exit Tax, parser)
- [x] Deemed disposal tracking with time remaining and urgency alerts
- [x] Family Mode - person management with Settings page
- [x] Per-person filtering on Portfolio, Tax Calculator
- [x] Person selector on PDF upload

### 🔧 Recent Fixes (v0.4.2)
- [x] **Combined View CGT Exemption**: Fixed critical bug - now correctly applies per-person €1,270 exemption in combined view (2 people = €2,540 total)
- [x] **Duplicate Detection**: Both transactions and income events now include person_id check (allows same data for different family members)
- [x] **Exit Tax Fee Handling**: Deemed disposals endpoint now includes fees in cost basis calculation
- [x] Manual transactions now assigned to selected person in family mode
- [x] CSV export respects person filter and includes Person column
- [x] Dashboard person filtering (UX consistency with Portfolio/Tax)
- [x] Data validation with warnings on PDF upload

---

## Phase 1: Core Improvements (Current Sprint)

### 1.1 Unit Tests ✅ DONE
- [x] Tests for Trade Republic PDF parser (regex patterns, number normalization)
- [x] Tests for CGT calculator (19 tests: FIFO matching, 4-week rule, same-day)
- [x] Tests for Exit Tax calculator (26 tests: FIFO, loss offsetting, deemed disposal)
- [ ] Tests for API endpoints
- [ ] CI/CD pipeline with test automation

### 1.2 Data Validation ✅ DONE
- [x] Track skipped transactions (missing ISIN, invalid format)
- [x] Collect parsing warnings with details
- [x] Show warnings on upload page with expandable details
- [x] Report parsing errors and skipped items count
- [ ] Validate parsed data against PDF totals (future)
- [ ] Allow manual corrections inline (future)

### 1.3 Deemed Disposal (8-Year Rule) ✅ DONE
- [x] Track purchase dates for all EU ETF holdings
- [x] Calculate deemed disposal dates (8 years from purchase)
- [x] Show upcoming deemed disposal calendar with time remaining
- [x] Calculate deemed disposal tax liability (estimated tax column)
- [x] Warning notifications for approaching dates (urgency colors)
- [x] Dashboard widget for quick overview

---

## Phase 2: Family/Joint Tax Returns 👨‍👩‍👧 ✅ DONE

### 2.1 Multi-Person Support ✅
- [x] Add "Person" entity (name, PPS number optional)
- [x] Default: Primary user + ability to add spouse
- [x] Each transaction linked to a person
- [x] Filter views by person
- [x] Settings page for person management

### 2.2 Separate Tracking ✅
- [x] Portfolio view: Filter by person or "All" combined
- [x] Transaction list: Filtered by person
- [x] Income: Split by person
- [x] Clear visual distinction (color-coded buttons)

### 2.3 Individual Tax Calculations ✅
- [x] CGT calculated separately per person
- [x] Each person gets their own €1,270 exemption
- [x] Exit Tax per person
- [x] DIRT per person
- [x] Individual tax summaries via person filter

### 2.4 Joint Filing View ✅
- [x] Combined tax summary (select "Combined" view)
- [ ] PDF export with both persons' data (enhancement)
- [ ] Joint Form 11 field reference with person breakdown (enhancement)

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

### CRITICAL - Tax Calculation Bugs
- [x] ~~**Combined View CGT Exemption**: Combined view uses single €1,270 exemption instead of per-person~~ FIXED
- [x] ~~**Exit Tax Fee Handling**: Deemed disposals endpoint now includes fees in cost basis~~ FIXED

### HIGH Priority
- [x] ~~**Income Event Duplicate Detection**: Fixed - duplicate detection now includes person_id~~ FIXED
- [x] ~~**CSV Export Person Lookup**: Already safe - uses .get() with "Unassigned" fallback~~ VERIFIED

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
- [x] ~~Dashboard person filtering (consistency with Portfolio/Tax pages)~~ FIXED
- [ ] Dashboard layout on mobile
- [ ] Better error messages for failed uploads
- [ ] Loading skeleton states
- [ ] Transaction reassignment UI before deleting person

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

| Feature | Impact | Effort | Priority | Status |
|---------|--------|--------|----------|--------|
| Unit Tests | High | Medium | **P0** | ✅ Done |
| Deemed Disposal Tracking | High | Medium | **P1** | ✅ Done |
| Family/Joint Returns | High | High | **P1** | ✅ Done |
| Data Validation | Medium | Medium | **P1** | ✅ Done |
| Multi-Year Support | Medium | Medium | **P2** | Next |
| Tax Optimization Tools | Medium | High | **P3** | Pending |
| Multiple Brokers | High | Very High | **Backlog** | Pending |
| Portfolio Analytics | Low | High | **Backlog** | Pending |

---

## Next Actions

1. ~~**Now**: Add unit tests for parser and calculators~~ ✅
2. ~~**Then**: Deemed Disposal tracking~~ ✅
3. ~~**Now**: Implement Family/Joint returns~~ ✅
4. ~~**Now**: Fix person_id bugs in manual transactions/CSV~~ ✅
5. ~~**Now**: Dashboard person filtering (UX consistency)~~ ✅
6. ~~**Now**: Data validation and error handling~~ ✅
7. ~~**CRITICAL**: Fix Combined View CGT exemption bug (per-person exemptions)~~ ✅
8. **HIGH**: Add income event duplicate detection
9. **Then**: Multi-year support (Phase 3)
10. **Next**: Tax optimization tools
