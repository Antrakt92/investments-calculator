Attribute VB_Name = "Module2"
Option Explicit

Public Sub ComputeFIFO_Fast()
    ' Turn off some Excel features for speed
    Application.ScreenUpdating = False
    Application.EnableEvents = False
    Application.Calculation = xlCalculationManual
    
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets("Transactions")
    
    Dim lastRow As Long
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).row
    
    Dim data As Variant
    data = ws.Range("A2:K" & lastRow).Value
    
    Dim results As Variant
    ReDim results(1 To UBound(data, 1), 1 To 1)
    
    Dim dict As Object
    Set dict = CreateObject("Scripting.Dictionary")
    
    Dim i As Long
    For i = 1 To UBound(data, 1)
        Dim trType As String: trType = UCase(Trim(CStr(data(i, 3))))
        Dim ticker As String: ticker = UCase(Trim(CStr(data(i, 4))))
        Dim qty As Double: qty = CDbl(data(i, 10))
        Dim price As Double: price = CDbl(data(i, 6))
        Dim comm As Double: comm = CDbl(data(i, 7))
        Dim totalVal As Double: totalVal = CDbl(data(i, 8))
        
        results(i, 1) = ""
        
        If Not dict.Exists(ticker) Then
            dict.Add ticker, New Collection
        End If
        
        Select Case trType
            Case "BUY"
                Dim costPerShare As Double
                If qty <> 0 Then
                    costPerShare = price + (comm / qty)
                Else
                    costPerShare = price
                End If
                dict(ticker).Add Array(qty, costPerShare)
            
            Case "SELL"
                Dim lotList As Collection
                Set lotList = dict(ticker)
                
                Dim totalShares As Double, j As Long
                For j = 1 To lotList.Count
                    totalShares = totalShares + lotList(j)(0)
                Next j
                
                If totalShares + 0.000001 < Abs(qty) Then
                    results(i, 1) = "#ERROR: Not enough shares"
                Else
                    Dim remainingQty As Double: remainingQty = Abs(qty)
                    Dim realizedPL As Double: realizedPL = 0
                    
                    Do While remainingQty > 0 And lotList.Count > 0
                        Dim currentLot As Variant
                        currentLot = lotList(1)
                        
                        If currentLot(0) > remainingQty Then
                            realizedPL = realizedPL + (price - currentLot(1)) * remainingQty
                            Dim updatedQty As Double: updatedQty = currentLot(0) - remainingQty
                            
                            Dim tempLots As New Collection
                            tempLots.Add Array(updatedQty, currentLot(1))
                            Dim k As Long
                            For k = 2 To lotList.Count
                                tempLots.Add lotList(k)
                            Next k
                            Set lotList = tempLots
                            remainingQty = 0
                        Else
                            realizedPL = realizedPL + (price - currentLot(1)) * currentLot(0)
                            remainingQty = remainingQty - currentLot(0)
                            lotList.Remove 1
                        End If
                    Loop
                    
                    realizedPL = Round(realizedPL - comm, 2)
                    results(i, 1) = realizedPL
                End If
            
            Case "DIVIDEND", "INTEREST"
                results(i, 1) = totalVal
            
            Case "DEPOSIT"
                results(i, 1) = 0
            
            Case Else
                results(i, 1) = ""
        End Select
    Next i
    
    ws.Range("K2:K" & lastRow).Value = results
    
    Application.Calculation = xlCalculationAutomatic
    Application.EnableEvents = True
    Application.ScreenUpdating = True
End Sub

