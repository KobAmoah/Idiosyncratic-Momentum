# File: ResidualMomentum.py
# Description: This file contains an implementation of residual momentum as described Denis Chaves(2012)
# Paper: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1982100
#
# The code modifies initial work by Jin Wu on Beta Factors for stocks.
# Jin Wu's algorithm :  https://www.quantconnect.com/learning/articles/investment-strategy-library/beta-factors-in-stocks
#
# Author: Kobby Amoah<amoahkobena@gmail.com>
# Copyright (c) 2023 
#
# Licensed under the MIT License.
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#   https://opensource.org/license/mit/
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.  See the License for the specific language governing
# permissions and limitations under the License.
#
######################################################################
######################################################################


#region imports
from AlgorithmImports import *
#endregion
from QuantConnect.Data.UniverseSelection import *
from QuantConnect.Python import PythonData
from collections import deque
from datetime import datetime
import math
import numpy as np
import pandas as pd
import scipy as sp
from decimal import Decimal


class ResidualMomemtumInStocks(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2016, 1, 1)   
        self.SetEndDate(2020, 1, 1)         
        self.SetCash(1000000)            

        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.CoarseSelectionFunction)
        self.AddEquity("SPY", Resolution.Daily)

        # Add Wilshire 5000 Total Market Index data from Dropbox 
        self.price5000 = self.AddData(Fred, Fred.Wilshire.Price5000, Resolution.Daily).Symbol
        # Setup a RollingWindow to hold market return
        self.market_return = RollingWindow[float](252)
        # Use a ROC indicator to convert market price index into return, and save it to the RollingWindow
        self.roc = self.ROC(self.price5000, 1)
        self.roc.Updated += lambda sender, updated: self.market_return.Add(updated.Value)
        # Warm up
        hist = self.History(self.price5000, 253, Resolution.Daily)
        for point in hist.itertuples():
            self.roc.Update(point.Index[1], point.value)

        self.data = {}
        self.monthly_rebalance = False
        self.long = None
        self.short = None
            
        self.Schedule.On(self.DateRules.MonthStart("SPY"), self.TimeRules.AfterMarketOpen("SPY"), self.rebalance)

    def CoarseSelectionFunction(self, coarse):
        CoarseWithFundamental = [x for x in coarse if x.HasFundamentalData and x.DollarVolume>10000000]
        for c in CoarseWithFundamental:
            if c.Symbol not in self.data:
                self.data[c.Symbol] = SymbolData(c.Symbol)
            self.data[c.Symbol].Update(c.EndTime, c.AdjustedPrice)

        if self.monthly_rebalance:
            filtered_data = {symbol: data for symbol, data in self.data.items() 
                             if data.last_price > 5 and data.IsReady()}
            if len(filtered_data) > 100:
                    # sort the dictionary and select top and bottom 10 stocks
                sorted_beta = sorted(filtered_data, 
                                     key = lambda x: filtered_data[x].beta(self.market_return),
                                     reverse=True)
                self.short = sorted_beta[-10:]
                self.long = sorted_beta[:10]
                return self.long + self.short

            else: 
                self.monthly_rebalance = False
                return []

        else:
            return []

    def rebalance(self):
        self.monthly_rebalance = True

    def OnData(self, data):
        if not self.monthly_rebalance: return 
        
        # Liquidate symbols not in the universe anymore
        for symbol in self.Portfolio.Keys:
            if self.Portfolio[symbol].Invested and symbol not in self.long + self.short:
                self.Liquidate(symbol)


        if self.long is None or self.short is None: return
                
        for symbol in self.long:    
            self.SetHoldings(symbol, 1/len(self.long))

        for symbol in self.short:    
            self.SetHoldings(symbol, -1/len(self.short))
           
        self.monthly_rebalance = False
        self.long = None
        self.short = None


class SymbolData:
    def __init__(self, symbol):
        self.Symbol = symbol
        self.last_price = 0
        self.returns = RollingWindow[float](252)
        self.roc = RateOfChange(1)
        self.roc.Updated += lambda sender, updated: self.returns.Add(updated.Value)
        
    def Update(self, time, price):
        if price != 0:
            self.last_price = price
            self.roc.Update(time, price)
    
    def IsReady(self):
        return self.roc.IsReady and self.returns.IsReady
    
    # This is a misnaming, should be residual
    # Changing the name however affects the running of the algo.
    def beta(self, market_ret):
        asset_return = np.array(list(self.returns), dtype=np.float32)
        asset_return = np.delete(asset_return,np.s_[:-21])
        market_return = np.array(list(market_ret), dtype=np.float32)
        market_return = np.delete(market_return,np.s_[:-21])
        bla = np.vstack([market_return, np.ones(len(asset_return))]).T
        result, residual, *_ = np.linalg.lstsq(bla , asset_return,rcond = None)
        momentum = np.cumprod(1+residual)-1
        return momentum
