import jsPDF from 'jspdf'
import type { TaxResult } from '../services/api'

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IE', {
    style: 'currency',
    currency: 'EUR',
  }).format(amount)
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-IE', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function exportTaxReportPDF(result: TaxResult, lossesCarriedForward: number = 0) {
  const doc = new jsPDF()
  const pageWidth = doc.internal.pageSize.getWidth()
  let y = 20

  // Title
  doc.setFontSize(20)
  doc.setFont('helvetica', 'bold')
  doc.text(`Irish Tax Report - ${result.tax_year}`, pageWidth / 2, y, { align: 'center' })
  y += 10

  doc.setFontSize(10)
  doc.setFont('helvetica', 'normal')
  doc.text(`Generated: ${new Date().toLocaleDateString('en-IE')}`, pageWidth / 2, y, { align: 'center' })
  y += 15

  // Summary Section
  doc.setFontSize(14)
  doc.setFont('helvetica', 'bold')
  doc.text('Tax Summary', 14, y)
  y += 8

  doc.setFontSize(10)
  doc.setFont('helvetica', 'normal')

  const summaryData = [
    ['CGT Due (Stocks - 33%)', formatCurrency(result.cgt.tax_due)],
    ['Exit Tax Due (EU Funds - 41%)', formatCurrency(result.exit_tax.tax_due)],
    ['DIRT Due (Interest - 33%)', formatCurrency(result.dirt.tax_to_pay)],
    ['TOTAL TAX DUE', formatCurrency(result.summary.total_tax_due)],
  ]

  summaryData.forEach(([label, value], i) => {
    const isTotal = i === summaryData.length - 1
    if (isTotal) {
      doc.setFont('helvetica', 'bold')
    }
    doc.text(label, 14, y)
    doc.text(value, pageWidth - 14, y, { align: 'right' })
    y += 6
  })

  y += 10

  // CGT Section
  doc.setFontSize(12)
  doc.setFont('helvetica', 'bold')
  doc.text('1. Capital Gains Tax (CGT) - Stocks', 14, y)
  y += 8

  doc.setFontSize(10)
  doc.setFont('helvetica', 'normal')

  const cgtData = [
    ['Total Gains', '+' + formatCurrency(result.cgt.gains)],
    ['Total Losses', '-' + formatCurrency(result.cgt.losses)],
    ['Net Gain/Loss', formatCurrency(result.cgt.net_gain_loss)],
    ['Losses Carried Forward', formatCurrency(lossesCarriedForward)],
    ['Annual Exemption Used', formatCurrency(result.cgt.exemption_used) + ' (max €1,270)'],
    ['Taxable Gain', formatCurrency(result.cgt.taxable_gain)],
    ['CGT @ 33%', formatCurrency(result.cgt.tax_due)],
  ]

  cgtData.forEach(([label, value]) => {
    doc.text(label, 20, y)
    doc.text(value, pageWidth - 14, y, { align: 'right' })
    y += 5
  })

  if (result.cgt.losses_to_carry_forward > 0) {
    y += 3
    doc.setFont('helvetica', 'italic')
    doc.text(`Losses to carry forward: ${formatCurrency(result.cgt.losses_to_carry_forward)}`, 20, y)
    doc.setFont('helvetica', 'normal')
    y += 5
  }

  y += 8

  // Exit Tax Section
  doc.setFontSize(12)
  doc.setFont('helvetica', 'bold')
  doc.text('2. Exit Tax (EU Funds)', 14, y)
  y += 8

  doc.setFontSize(10)
  doc.setFont('helvetica', 'normal')

  const exitData = [
    ['Gains from Sales', '+' + formatCurrency(result.exit_tax.gains)],
    ['Losses from Sales', '-' + formatCurrency(result.exit_tax.losses)],
    ['Net Gain/Loss', formatCurrency(result.exit_tax.gains - result.exit_tax.losses)],
    ['Deemed Disposal Gains', formatCurrency(result.exit_tax.deemed_disposal_gains)],
    ['Total Taxable', formatCurrency(result.exit_tax.total_taxable)],
    ['Exit Tax @ 41%', formatCurrency(result.exit_tax.tax_due)],
  ]

  exitData.forEach(([label, value]) => {
    doc.text(label, 20, y)
    doc.text(value, pageWidth - 14, y, { align: 'right' })
    y += 5
  })

  y += 8

  // DIRT Section
  doc.setFontSize(12)
  doc.setFont('helvetica', 'bold')
  doc.text('3. DIRT (Deposit Interest)', 14, y)
  y += 8

  doc.setFontSize(10)
  doc.setFont('helvetica', 'normal')

  const dirtData = [
    ['Interest Income', formatCurrency(result.dirt.interest_income)],
    ['DIRT Already Withheld', formatCurrency(result.dirt.tax_withheld)],
    ['DIRT to Pay @ 33%', formatCurrency(result.dirt.tax_to_pay)],
  ]

  dirtData.forEach(([label, value]) => {
    doc.text(label, 20, y)
    doc.text(value, pageWidth - 14, y, { align: 'right' })
    y += 5
  })

  y += 8

  // Dividends Section
  doc.setFontSize(12)
  doc.setFont('helvetica', 'bold')
  doc.text('4. Dividends (Foreign Income)', 14, y)
  y += 8

  doc.setFontSize(10)
  doc.setFont('helvetica', 'normal')

  const divData = [
    ['Total Dividends', formatCurrency(result.dividends.total_dividends)],
    ['Withholding Tax Credit', formatCurrency(result.dividends.withholding_tax_credit)],
  ]

  divData.forEach(([label, value]) => {
    doc.text(label, 20, y)
    doc.text(value, pageWidth - 14, y, { align: 'right' })
    y += 5
  })

  // Check if we need a new page for deadlines
  if (y > 220) {
    doc.addPage()
    y = 20
  } else {
    y += 10
  }

  // Payment Deadlines
  doc.setFontSize(12)
  doc.setFont('helvetica', 'bold')
  doc.text('Payment Deadlines', 14, y)
  y += 8

  doc.setFontSize(10)
  doc.setFont('helvetica', 'normal')

  const deadlines = result.summary.payment_deadlines.filter(d => d.amount > 0)
  if (deadlines.length > 0) {
    deadlines.forEach(d => {
      doc.text(`${formatDate(d.due_date)} - ${d.description}`, 20, y)
      doc.text(formatCurrency(d.amount), pageWidth - 14, y, { align: 'right' })
      y += 5
    })
  } else {
    doc.text('No tax payments due for this year.', 20, y)
    y += 5
  }

  // Check if we need a new page for Form 11
  if (y > 200) {
    doc.addPage()
    y = 20
  } else {
    y += 10
  }

  // Form 11 Guidance
  doc.setFontSize(12)
  doc.setFont('helvetica', 'bold')
  doc.text('Form 11 Field Reference', 14, y)
  y += 8

  doc.setFontSize(10)
  doc.setFont('helvetica', 'normal')

  doc.setFont('helvetica', 'bold')
  doc.text('Panel D - Irish Investment Income', 14, y)
  doc.setFont('helvetica', 'normal')
  y += 5
  doc.text('Deposit Interest (Gross)', 20, y)
  doc.text(formatCurrency(result.form_11_guidance.panel_d.deposit_interest_gross), pageWidth - 14, y, { align: 'right' })
  y += 5
  doc.text('DIRT Deducted', 20, y)
  doc.text(formatCurrency(result.form_11_guidance.panel_d.dirt_deducted), pageWidth - 14, y, { align: 'right' })
  y += 8

  doc.setFont('helvetica', 'bold')
  doc.text('Panel E - Capital Gains', 14, y)
  doc.setFont('helvetica', 'normal')
  y += 5
  doc.text('Sale Proceeds (Consideration)', 20, y)
  doc.text(formatCurrency(result.form_11_guidance.panel_e.cgt_consideration), pageWidth - 14, y, { align: 'right' })
  y += 5
  doc.text('Allowable Costs', 20, y)
  doc.text(formatCurrency(result.form_11_guidance.panel_e.cgt_allowable_costs), pageWidth - 14, y, { align: 'right' })
  y += 5
  doc.text('Net Gain', 20, y)
  doc.text(formatCurrency(result.form_11_guidance.panel_e.cgt_net_gain), pageWidth - 14, y, { align: 'right' })
  y += 5
  doc.text('Annual Exemption', 20, y)
  doc.text(formatCurrency(result.form_11_guidance.panel_e.cgt_exemption), pageWidth - 14, y, { align: 'right' })
  y += 5
  doc.text('Exit Tax Gains', 20, y)
  doc.text(formatCurrency(result.form_11_guidance.panel_e.exit_tax_gains), pageWidth - 14, y, { align: 'right' })
  y += 8

  doc.setFont('helvetica', 'bold')
  doc.text('Panel F - Foreign Income', 14, y)
  doc.setFont('helvetica', 'normal')
  y += 5
  doc.text('Foreign Dividends', 20, y)
  doc.text(formatCurrency(result.form_11_guidance.panel_f.foreign_dividends), pageWidth - 14, y, { align: 'right' })
  y += 5
  doc.text('Foreign Tax Credit', 20, y)
  doc.text(formatCurrency(result.form_11_guidance.panel_f.foreign_tax_credit), pageWidth - 14, y, { align: 'right' })

  // Footer
  const pageCount = (doc as any).internal.getNumberOfPages()
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i)
    doc.setFontSize(8)
    doc.setFont('helvetica', 'italic')
    doc.text(
      'This report is for informational purposes only. Consult a tax professional for advice.',
      pageWidth / 2,
      doc.internal.pageSize.getHeight() - 10,
      { align: 'center' }
    )
    doc.text(
      `Page ${i} of ${pageCount}`,
      pageWidth - 14,
      doc.internal.pageSize.getHeight() - 10,
      { align: 'right' }
    )
  }

  // Save the PDF
  doc.save(`Irish_Tax_Report_${result.tax_year}.pdf`)
}
