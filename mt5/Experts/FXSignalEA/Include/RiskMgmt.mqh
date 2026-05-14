//+------------------------------------------------------------------+
//|                                                  RiskMgmt.mqh    |
//|  資金管理 / ロット計算 / 日次損失追跡                              |
//+------------------------------------------------------------------+
#property strict

//+------------------------------------------------------------------+
//| pip サイズ。JPY クロス → 0.01、その他 → 0.0001                    |
//+------------------------------------------------------------------+
double CalcPipSize(const string symbol)
{
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   if(digits == 3 || digits == 5)
      return SymbolInfoDouble(symbol, SYMBOL_POINT) * 10.0;
   return SymbolInfoDouble(symbol, SYMBOL_POINT);
}

//+------------------------------------------------------------------+
//| 1 pip あたりの金額 (口座通貨ベース)                                |
//|  = TickValue * (PipSize / TickSize)                              |
//+------------------------------------------------------------------+
double CalcPipValuePerLot(const string symbol)
{
   double tick_size  = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   double tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tick_size <= 0) return 0.0;
   double pip_size = CalcPipSize(symbol);
   return tick_value * (pip_size / tick_size);
}

//+------------------------------------------------------------------+
//| リスク%とSL距離からロット数を計算 (ブローカーの min/max/step に丸め)|
//|  account_currency 単位の resi金額 = balance × risk_pct/100        |
//|  lot = risk_money / (SL_pips × pip_value)                        |
//+------------------------------------------------------------------+
double CalcLotByRisk(const string symbol, double risk_pct, double entry, double stop_loss)
{
   if(risk_pct <= 0 || entry == stop_loss) return 0.0;
   double pip = CalcPipSize(symbol);
   if(pip <= 0) return 0.0;

   double sl_pips = MathAbs(entry - stop_loss) / pip;
   if(sl_pips <= 0) return 0.0;

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_money = balance * risk_pct / 100.0;
   double pip_value = CalcPipValuePerLot(symbol);
   if(pip_value <= 0) return 0.0;

   double raw_lot = risk_money / (sl_pips * pip_value);

   //--- ブローカーの制約に丸める
   double min_lot  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double max_lot  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double step_lot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(step_lot <= 0) step_lot = 0.01;

   double lot = MathFloor(raw_lot / step_lot) * step_lot;
   if(lot < min_lot) lot = min_lot;
   if(lot > max_lot) lot = max_lot;
   return lot;
}

//+------------------------------------------------------------------+
//| 現在の口座 equity から、当日の損益 (R or %) を計算               |
//|  - 当日開始残高は EA 起動時 or 日付変更時に保存                  |
//|  - グローバル変数 (GlobalVariable*) で永続化                      |
//+------------------------------------------------------------------+
double GetDailyOpenBalance()
{
   string gv = "FXS_DailyOpenBal";
   string gv_date = "FXS_DailyDate";
   string today = TimeToString(TimeCurrent(), TIME_DATE);  // "YYYY.MM.DD"

   if(!GlobalVariableCheck(gv_date) || GlobalVariableGet(gv_date) == 0)
   {
      // 初回 or 日付変わった
      double balance = AccountInfoDouble(ACCOUNT_BALANCE);
      GlobalVariableSet(gv, balance);
      // 日付を yyyymmdd の数値で保存
      MqlDateTime dt;
      TimeToStruct(TimeCurrent(), dt);
      GlobalVariableSet(gv_date, dt.year * 10000 + dt.mon * 100 + dt.day);
      return balance;
   }

   //--- 日付変更チェック
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   long today_int = dt.year * 10000 + dt.mon * 100 + dt.day;
   long stored = (long)GlobalVariableGet(gv_date);
   if(today_int != stored)
   {
      double balance = AccountInfoDouble(ACCOUNT_BALANCE);
      GlobalVariableSet(gv, balance);
      GlobalVariableSet(gv_date, (double)today_int);
      return balance;
   }
   return GlobalVariableGet(gv);
}

//+------------------------------------------------------------------+
//| 当日の損益率 (%, equity ベース、未決済含む)。マイナスなら損失     |
//+------------------------------------------------------------------+
double GetDailyPnLPercent()
{
   double opened = GetDailyOpenBalance();
   if(opened <= 0) return 0.0;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   return (equity - opened) / opened * 100.0;
}

//+------------------------------------------------------------------+
//| MaxDailyLossPercent を超えていれば true (新規エントリー禁止)     |
//+------------------------------------------------------------------+
bool IsDailyLossLimitHit(double max_loss_pct)
{
   if(max_loss_pct <= 0) return false;
   return GetDailyPnLPercent() <= -MathAbs(max_loss_pct);
}
//+------------------------------------------------------------------+
