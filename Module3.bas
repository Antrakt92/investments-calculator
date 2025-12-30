Attribute VB_Name = "Module3"
'--- Enhanced Investment Calculator Module ---
Option Explicit

Public Function CalculateInvestment( _
    desiredPercent As Double, _
    currentAmount As Double, _
    totalCurrentAmount As Double, _
    newInvestAmount As Double, _
    targetRange As Range _
) As Double
    
    On Error GoTo ErrorHandler
    
    ' Force recalculation for dynamic updates
    Application.Volatile
    
    ' Input validation
    If desiredPercent < 0 Or desiredPercent > 1 Then
        CalculateInvestment = 0
        Exit Function
    End If
    
    If newInvestAmount <= 0 Or totalCurrentAmount < 0 Then
        CalculateInvestment = 0
        Exit Function
    End If
    
    ' Core calculations
    Dim finalPortfolioSize As Double
    finalPortfolioSize = totalCurrentAmount + newInvestAmount
    
    Dim targetAmount As Double
    targetAmount = finalPortfolioSize * desiredPercent
    
    Dim neededAmount As Double
    neededAmount = targetAmount - currentAmount
    
    ' Early exit for over-allocated assets
    If neededAmount <= 0 Then
        CalculateInvestment = 1
        Exit Function
    End If
    
    ' Calculate total investment needs across all assets
    Dim totalNeeded As Double
    Dim assetsNotNeedingInvestment As Long
    Dim i As Long
    
    totalNeeded = 0
    assetsNotNeedingInvestment = 0
    
    ' Loop through range
    For i = 1 To targetRange.Rows.Count
        Dim assetPercent As Double
        Dim assetCurrentAmount As Double
        Dim assetTargetAmount As Double
        Dim assetNeedAmount As Double
        
        assetPercent = targetRange.Cells(i, 1).Value
        assetCurrentAmount = targetRange.Cells(i, 1).Offset(0, 1).Value
        
        assetTargetAmount = finalPortfolioSize * assetPercent
        assetNeedAmount = assetTargetAmount - assetCurrentAmount
        
        If assetNeedAmount > 0 Then
            totalNeeded = totalNeeded + assetNeedAmount
        Else
            assetsNotNeedingInvestment = assetsNotNeedingInvestment + 1
        End If
    Next i
    
    ' Calculate proportional allocation
    Dim availableForDistribution As Double
    availableForDistribution = newInvestAmount - assetsNotNeedingInvestment
    
    If totalNeeded > 0 And availableForDistribution > 0 Then
        Dim proportionalAmount As Double
        proportionalAmount = (neededAmount / totalNeeded) * availableForDistribution
        CalculateInvestment = Application.WorksheetFunction.Max(1, Application.WorksheetFunction.Round(proportionalAmount, 0))
    Else
        CalculateInvestment = 1
    End If
    
    ' === CORRECTION FOR ROUNDING - Last asset gets remainder ===
    ' Find which row in range this calculation is for
    Dim currentRowIndex As Long
    currentRowIndex = 0
    
    For i = 1 To targetRange.Rows.Count
        If targetRange.Cells(i, 1).Value = desiredPercent And _
           targetRange.Cells(i, 1).Offset(0, 1).Value = currentAmount Then
            currentRowIndex = i
            Exit For
        End If
    Next i
    
    ' If this is the LAST row, adjust for rounding errors
    If currentRowIndex = targetRange.Rows.Count Then
        Dim totalAllocated As Double
        totalAllocated = 0
        
        ' Sum all allocations EXCEPT current (last) one
        For i = 1 To targetRange.Rows.Count - 1
            Dim rowPercent As Double
            Dim rowCurrent As Double
            Dim rowTarget As Double
            Dim rowNeed As Double
            
            rowPercent = targetRange.Cells(i, 1).Value
            rowCurrent = targetRange.Cells(i, 1).Offset(0, 1).Value
            rowTarget = finalPortfolioSize * rowPercent
            rowNeed = rowTarget - rowCurrent
            
            If rowNeed <= 0 Then
                totalAllocated = totalAllocated + 1
            Else
                Dim rowProportion As Double
                If totalNeeded > 0 Then
                    rowProportion = (rowNeed / totalNeeded) * availableForDistribution
                    totalAllocated = totalAllocated + Application.WorksheetFunction.Max(1, Application.WorksheetFunction.Round(rowProportion, 0))
                Else
                    totalAllocated = totalAllocated + 1
                End If
            End If
        Next i
        
        ' Last asset gets exact remainder
        CalculateInvestment = newInvestAmount - totalAllocated
        
        ' Ensure minimum 1
        If CalculateInvestment < 1 Then CalculateInvestment = 1
    End If
    
    Exit Function
    
ErrorHandler:
    CalculateInvestment = 0
    
End Function

Public Function CalculateNewPercentage( _
    currentAmount As Double, _
    addedAmount As Double, _
    totalAmount As Double, _
    newInvestAmount As Double _
) As Double
    
    On Error GoTo ErrorHandler
    
    ' Input validation
    If totalAmount + newInvestAmount <= 0 Then
        CalculateNewPercentage = 0
        Exit Function
    End If
    
    Dim newTotalPortfolio As Double
    newTotalPortfolio = totalAmount + newInvestAmount
    
    Dim newAssetAmount As Double
    newAssetAmount = currentAmount + addedAmount
    
    CalculateNewPercentage = newAssetAmount / newTotalPortfolio
    
    Exit Function
    
ErrorHandler:
    CalculateNewPercentage = 0
    
End Function

