# Irish Tax Calculator - Product Roadmap

## Current Status (MVP v0.1)

### ✅ Implemented
- PDF Upload (Trade Republic tax reports)
- Portfolio View (Holdings, Transactions, Income tabs)
- Tax Calculator (CGT 33%, Exit Tax 41%, DIRT 33%)
- Form 11 field reference
- Irish CGT matching rules (same-day, 4-week, FIFO)
- Exit Tax with deemed disposal tracking
- Duplicate detection on import
- Gain/Loss calculation per transaction

### ❌ Missing / Needs Improvement

## Phase 1: Personal Use MVP (Current Sprint)

### 1.1 Data Verification
- [ ] Show parsed totals vs PDF totals (comparison table)
- [ ] Highlight discrepancies
- [ ] Allow user to confirm data is correct

### 1.2 Data Management
- [ ] Clear all data button
- [ ] Delete individual transactions
- [ ] Re-upload without duplicates

### 1.3 Dashboard Improvements
- [ ] Tax breakdown pie chart
- [ ] Monthly income chart
- [ ] Quick action buttons
- [ ] Year-over-year comparison

### 1.4 Export Features
- [ ] Export tax report as PDF
- [ ] Export transactions as CSV
- [ ] Export for accountant (summary)

---

## Phase 2: Beta (Multi-Year Support)

### 2.1 Historical Data
- [ ] Support multiple tax years
- [ ] Year selector on all pages
- [ ] Carry forward losses between years

### 2.2 Manual Entry
- [ ] Add transactions manually
- [ ] Edit existing transactions
- [ ] Delete transactions
- [ ] Correct parsing errors

### 2.3 Multiple Brokers
- [ ] Interactive Brokers (IBKR)
- [ ] Degiro
- [ ] Revolut
- [ ] Generic CSV import

### 2.4 Tax Optimization
- [ ] Show potential tax savings
- [ ] Suggest loss harvesting opportunities
- [ ] Show impact of different selling strategies

---

## Phase 3: SaaS Product

### 3.1 User Management
- [ ] User registration/login
- [ ] Secure data storage
- [ ] Email verification
- [ ] Password reset

### 3.2 Subscription System
- [ ] Free tier (1 year, limited features)
- [ ] Monthly subscription (€9.99/month)
- [ ] Annual subscription (€79.99/year)
- [ ] Stripe integration

### 3.3 Enhanced Features
- [ ] Email reminders for tax deadlines
- [ ] Push notifications
- [ ] Mobile-responsive design
- [ ] Dark mode

### 3.4 Compliance & Security
- [ ] GDPR compliance
- [ ] Data encryption at rest
- [ ] Two-factor authentication
- [ ] Audit logging

---

## Phase 4: Scale

### 4.1 Multi-Country Support
- [ ] UK CGT rules
- [ ] German tax rules
- [ ] Other EU countries

### 4.2 Integrations
- [ ] Direct broker API connections
- [ ] Accounting software export
- [ ] Revenue Online Service (ROS) integration

### 4.3 Enterprise
- [ ] Accountant portal
- [ ] Bulk client management
- [ ] White-label solution

---

## Technical Debt

- [ ] Add comprehensive unit tests
- [ ] Add E2E tests (Playwright)
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Error logging and monitoring
- [ ] Database migrations (Alembic)
- [ ] CI/CD pipeline

---

## Priority Matrix

| Feature | Impact | Effort | Priority |
|---------|--------|--------|----------|
| Data verification | High | Low | **P1** |
| Clear data button | High | Low | **P1** |
| PDF export | High | Medium | **P1** |
| Dashboard charts | Medium | Medium | P2 |
| Manual transaction entry | High | High | P2 |
| Multi-broker support | High | High | P3 |
| User authentication | Critical | High | P3 |
