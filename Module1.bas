Attribute VB_Name = "Module1"
Option Explicit

Sub SummarizeTaxByYearAndCategory()
    ' Reads from "Tax" sheet:
    '   Col A: Date
    '   Col B: Asset Class ("STOCK","ETF","DIVIDEND","DEPOSIT")
    '   Col D: Realized P/L
    ' Calculates tax per category:
    '   STOCK -> 33% minus annual 1270 relief (no carry-forward here)
    '   ETF -> 41%
    '   DIVIDEND -> 40%
    '   DEPOSIT -> 33%
    ' Outputs:
    '   Year, StockIncome, StockTax, ETFIncome, ETFTax, DivIncome, DivTax, DepIncome, DepTax, TotalIncome, TotalTax

    Dim ws As Worksheet: Set ws = ThisWorkbook.Sheets("Tax")
    Dim lastRow As Long: lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).row
    
    Dim dictYear As Object: Set dictYear = CreateObject("Scripting.Dictionary")
    
    Dim i As Long
    For i = 2 To lastRow
        Dim dDate As Variant: dDate = ws.Cells(i, "A").Value
        Dim cat As String: cat = UCase(Trim(CStr(ws.Cells(i, "B").Value)))
        Dim pnlVal As Double: pnlVal = CDbl(ws.Cells(i, "D").Value)
        
        If IsDate(dDate) Then
            Dim yr As Long: yr = Year(dDate)
            If Not dictYear.Exists(yr) Then
                Dim catDict As Object: Set catDict = CreateObject("Scripting.Dictionary")
                catDict("STOCK") = 0#
                catDict("ETF") = 0#
                catDict("DIVIDEND") = 0#
                catDict("DEPOSIT") = 0#
                dictYear.Add yr, catDict
            End If
            
            If dictYear(yr).Exists(cat) Then
                dictYear(yr)(cat) = dictYear(yr)(cat) + pnlVal
            End If
        End If
    Next i
    
    ws.Range("H1").Value = "Year"
    ws.Range("I1").Value = "StockIncome"
    ws.Range("J1").Value = "StockTax"
    ws.Range("K1").Value = "ETFIncome"
    ws.Range("L1").Value = "ETFTax"
    ws.Range("M1").Value = "DivIncome"
    ws.Range("N1").Value = "DivTax"
    ws.Range("O1").Value = "DepIncome"
    ws.Range("P1").Value = "DepTax"
    ws.Range("Q1").Value = "TotalIncome"
    ws.Range("R1").Value = "TotalTax"
    
    Dim allYears() As Variant
    ReDim allYears(dictYear.Count - 1)
    
    Dim idx As Long: idx = 0
    Dim k As Variant
    For Each k In dictYear.Keys
        allYears(idx) = k
        idx = idx + 1
    Next k
    
    Dim i2 As Long, j2 As Long, temp As Variant
    For i2 = LBound(allYears) To UBound(allYears) - 1
        For j2 = i2 + 1 To UBound(allYears)
            If allYears(i2) > allYears(j2) Then
                temp = allYears(i2)
                allYears(i2) = allYears(j2)
                allYears(j2) = temp
            End If
        Next j2
    Next i2
    
    Dim rowOut As Long: rowOut = 2
    
    For i2 = LBound(allYears) To UBound(allYears)
        Dim y As Long: y = allYears(i2)
        Dim cDict As Object: Set cDict = dictYear(y)
        
        Dim netStock As Double: netStock = cDict("STOCK")
        Dim netETF As Double: netETF = cDict("ETF")
        Dim netDiv As Double: netDiv = cDict("DIVIDEND")
        Dim netDep As Double: netDep = cDict("DEPOSIT")
        
        Dim taxableStock As Double
        If netStock > 0 Then
            taxableStock = Application.Max(0, netStock - 1270)
        Else
            taxableStock = 0
        End If
        Dim taxStock As Double: taxStock = Round(taxableStock * 0.33, 2)
        
        Dim taxableETF As Double: taxableETF = Application.Max(0, netETF)
        Dim taxETF As Double: taxETF = Round(taxableETF * 0.41, 2)
        
        Dim taxableDiv As Double: taxableDiv = Application.Max(0, netDiv)
        Dim taxDiv As Double: taxDiv = Round(taxableDiv * 0.4, 2)
        
        Dim taxableDep As Double: taxableDep = Application.Max(0, netDep)
        Dim taxDep As Double: taxDep = Round(taxableDep * 0.33, 2)
        
        Dim totalInc As Double: totalInc = netStock + netETF + netDiv + netDep
        Dim totalTax As Double: totalTax = taxStock + taxETF + taxDiv + taxDep
        
        ws.Cells(rowOut, "H").Value = y
        ws.Cells(rowOut, "I").Value = netStock
        ws.Cells(rowOut, "J").Value = taxStock
        ws.Cells(rowOut, "K").Value = netETF
        ws.Cells(rowOut, "L").Value = taxETF
        ws.Cells(rowOut, "M").Value = netDiv
        ws.Cells(rowOut, "N").Value = taxDiv
        ws.Cells(rowOut, "O").Value = netDep
        ws.Cells(rowOut, "P").Value = taxDep
        ws.Cells(rowOut, "Q").Value = totalInc
        ws.Cells(rowOut, "R").Value = totalTax
        
        rowOut = rowOut + 1
    Next i2
End Sub

