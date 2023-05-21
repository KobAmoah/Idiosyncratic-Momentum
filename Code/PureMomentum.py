# https://quantpedia.com/Screener/Details/51

#region imports
from AlgorithmImports import *
#endregion
from QuantConnect.Data.UniverseSelection import *
import numpy as np
class MomentumAlgorithm(QCAlgorithm):

    def Initialize(self):

        self.SetStartDate(2016, 1, 1)   
        self.SetEndDate(2020, 1, 1)    
        self.SetCash(100000)         

        self.UniverseSettings.Resolution = Resolution.Daily

        self.AddEquity("SPY", Resolution.Daily)
        self.AddUniverse(self.CoarseSelectionFunction)
        self.Schedule.On(self.DateRules.MonthStart("SPY"), self.TimeRules.AfterMarketOpen("SPY"), self.Rebalance)
        self.month_start = False
        self.coarse = False
        self.SymbolPrice = {}
        self.long = None
        self.short = None


    def CoarseSelectionFunction(self, coarse):
        if self.month_start:
            self.coarse = True
            coarse = [x for x in coarse if x.HasFundamentalData and x.DollarVolume>10000000 and x.AdjustedPrice > 5]
            for i in coarse:
                if i.Symbol not in self.SymbolPrice:
                    self.SymbolPrice[i.Symbol] = SymbolData(i.Symbol)
                
                self.SymbolPrice[i.Symbol].window.Add(float(i.AdjustedPrice))
                # Note this accounts for reversal effects
                if self.SymbolPrice[i.Symbol].window.IsReady:
                    price = np.array([i for i in self.SymbolPrice[i.Symbol].window])
                    returns = (price[1:-1]-price[2:])/price[2:]
                    self.SymbolPrice[i.Symbol].yearly_return = (price[1]-price[-1])/price[-1]
                    cum_rets= np.prod([(1+i)**(1/11) for i in returns])-1
                    self.SymbolPrice[i.Symbol].momentum = cum_rets

            ReadySymbolPrice = {symbol: SymbolData for symbol, SymbolData in self.SymbolPrice.items() if SymbolData.window.IsReady}
            if ReadySymbolPrice and len(ReadySymbolPrice)>50:        
                sorted_by_return = sorted(ReadySymbolPrice, key = lambda x: ReadySymbolPrice[x].yearly_return, reverse = True)
                winner = sorted_by_return[:int(len(sorted_by_return)*0.3)]
                loser = sorted_by_return[-int(len(sorted_by_return)*0.3):]
                self.long = sorted(winner, key = lambda x: ReadySymbolPrice[x].momentum)[:10] 
                self.short = sorted(loser, key = lambda x: ReadySymbolPrice[x].momentum)[-10:] 
                return self.long + self.short
            else:
                return []
        else:
            return []
                

    def OnData(self, data):
        if self.month_start and self.coarse:
            self.month_start = False
            self.coarse = False
            
            if all([self.long, self.short]):
                
                stocks_invested = [x.Key for x in self.Portfolio]
                for i in stocks_invested:
                    if i not in self.long+self.short:
                        self.Liquidate(i) 
                
                for symbol in self.long:    
                    self.SetHoldings(symbol, 1/len(self.long))

                for symbol in self.short:    
                    self.SetHoldings(symbol, -1/len(self.short))


    def Rebalance(self):
        self.month_start = True

class SymbolData:
    def __init__(self, symbol):
        self.symbol = symbol
        self.window = RollingWindow[float](13)
        self.momentum = None
        self.yearly_return = None