//+------------------------------------------------------------------+
//|                                                   TradeOps.mqh   |
//|  注文発行 / ポジション管理 ラッパ                                   |
//|                                                                  |
//|  Magic Number 設計:                                               |
//|     MagicBase + pair_index * 10 + method_index                   |
//|       pair_index : 0〜14 (15 ペア)                                |
//|       method_index : 0=orz 1=pdhl 2=both 3=claude 4=triple 5=dtp 6=pa |
//|     例: USDJPY (idx=0) × triple (idx=4) → MagicBase+4             |
//|  これにより同 pair × method の重複オープンを防止できる。           |
//+------------------------------------------------------------------+
#property strict
#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

CTrade        g_trade;
CPositionInfo g_pos;

//--- method 文字列 → index
int MethodIndex(const string method)
{
   if(method == "orz")    return 0;
   if(method == "pdhl")   return 1;
   if(method == "both")   return 2;
   if(method == "claude") return 3;
   if(method == "triple") return 4;
   if(method == "dtp")    return 5;
   if(method == "pa")     return 6;
   return -1;
}

string MethodNameByIndex(const int i)
{
   string names[7] = {"orz", "pdhl", "both", "claude", "triple", "dtp", "pa"};
   if(i >= 0 && i < 7) return names[i];
   return "";
}

//+------------------------------------------------------------------+
//| 与えられた MagicBase, pair_index, method から magic を組み立て   |
//+------------------------------------------------------------------+
long BuildMagic(const long base_magic, const int pair_index, const int method_index)
{
   return base_magic + pair_index * 10 + method_index;
}

//+------------------------------------------------------------------+
//| この magic で開いている position があれば true                    |
//+------------------------------------------------------------------+
bool HasOpenPositionWithMagic(const long magic)
{
   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
   {
      if(!g_pos.SelectByIndex(i)) continue;
      if(g_pos.Magic() == magic) return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| 全ポジション数 (この EA が建てたもの限定)                          |
//+------------------------------------------------------------------+
int CountOpenPositionsByMagicBase(const long base_magic, const long base_magic_max)
{
   int n = 0;
   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
   {
      if(!g_pos.SelectByIndex(i)) continue;
      long m = g_pos.Magic();
      if(m >= base_magic && m <= base_magic_max) n++;
   }
   return n;
}

//+------------------------------------------------------------------+
//| 価格を symbol の digits に丸める                                  |
//+------------------------------------------------------------------+
double NormalizeForSymbol(const string symbol, const double price)
{
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   return NormalizeDouble(price, digits);
}

//+------------------------------------------------------------------+
//| 成行で買い/売りエントリー                                          |
//|                                                                  |
//| direction : "long" / "short"                                     |
//| 戻り値    : 成功した position ticket、失敗時 0                    |
//+------------------------------------------------------------------+
ulong OpenMarketOrder(
   const string symbol,
   const string direction,
   const double lot,
   const double sl,
   const double tp,
   const long magic,
   const int slippage_pts,
   const string comment_str
)
{
   //--- 銘柄を Market Watch にあるか確認 (なければ追加)
   if(!SymbolSelect(symbol, true))
   {
      Print("[TradeOps] SymbolSelect 失敗: ", symbol);
      return 0;
   }

   //--- スプレッド・ティック情報取得
   MqlTick tick;
   if(!SymbolInfoTick(symbol, tick))
   {
      Print("[TradeOps] tick 取得失敗: ", symbol);
      return 0;
   }

   double price = (direction == "long") ? tick.ask : tick.bid;
   double sl_n  = NormalizeForSymbol(symbol, sl);
   double tp_n  = NormalizeForSymbol(symbol, tp);
   double lot_n = NormalizeDouble(lot, 2);

   //--- CTrade のパラメータ設定
   g_trade.SetExpertMagicNumber(magic);
   g_trade.SetDeviationInPoints(slippage_pts);
   g_trade.SetTypeFillingBySymbol(symbol);

   bool ok;
   if(direction == "long")
      ok = g_trade.Buy(lot_n, symbol, price, sl_n, tp_n, comment_str);
   else
      ok = g_trade.Sell(lot_n, symbol, price, sl_n, tp_n, comment_str);

   if(!ok)
   {
      Print("[TradeOps] 注文失敗: ", symbol, " ", direction, " lot=", lot_n,
            " ret_code=", g_trade.ResultRetcode(), " (", g_trade.ResultRetcodeDescription(), ")");
      return 0;
   }

   ulong ticket = g_trade.ResultPosition();
   Print("[TradeOps] OPEN ", symbol, " ", direction, " lot=", lot_n,
         " entry=", DoubleToString(price, _Digits),
         " SL=", DoubleToString(sl_n, _Digits),
         " TP=", DoubleToString(tp_n, _Digits),
         " magic=", magic, " ticket=", ticket);
   return ticket;
}

//+------------------------------------------------------------------+
//| 現在のスプレッド (pips) — フィルター用                            |
//+------------------------------------------------------------------+
double CurrentSpreadPips(const string symbol)
{
   MqlTick tick;
   if(!SymbolInfoTick(symbol, tick)) return 999.0;
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   double pip = (digits == 3 || digits == 5)
                ? SymbolInfoDouble(symbol, SYMBOL_POINT) * 10.0
                : SymbolInfoDouble(symbol, SYMBOL_POINT);
   if(pip <= 0) return 999.0;
   return (tick.ask - tick.bid) / pip;
}
//+------------------------------------------------------------------+
