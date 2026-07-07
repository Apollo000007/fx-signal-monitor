//+------------------------------------------------------------------+
//|                                                   TradeOps.mqh   |
//|  注文発行 / ポジション管理 ラッパ                                   |
//|                                                                  |
//|  Magic Number 設計:                                               |
//|     MagicBase + pair_index * 10 + method_index                   |
//|       pair_index : 0〜14 (15 ペア)                                |
//|       method_index : 0=orz 1=pdhl 2=both 3=claude 4=triple 5=dtp 6=pa 7=mtf 8=cs |
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
   if(method == "mtf")    return 7;
   if(method == "cs")     return 8;
   return -1;
}

string MethodNameByIndex(const int i)
{
   string names[9] = {"orz", "pdhl", "both", "claude", "triple", "dtp", "pa", "mtf", "cs"};
   if(i >= 0 && i < 9) return names[i];
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
//| 同一通貨・同方向のエクスポージャ数 (この EA の建玉限定)             |
//|   例: EURUSD sell = USD買い。既に USDCHF buy (=USD買い) があれば 1 |
//|   【R2教訓】USDロング×3 の重ね玉で口座が壊れた再発防止。            |
//|   base/quote: 新規候補の通貨 ("USD","JPY" 等 3 文字)               |
//|   is_long   : 新規候補が買い (base買い/quote売り) か               |
//+------------------------------------------------------------------+
int CountSameCcyExposure(const string base, const string quote, const bool is_long,
                         const long magic_min, const long magic_max)
{
   int cnt = 0;
   int total = PositionsTotal();
   for(int i = 0; i < total; i++)
   {
      if(!g_pos.SelectByIndex(i)) continue;
      long m = g_pos.Magic();
      if(m < magic_min || m > magic_max) continue;
      string sym = g_pos.Symbol();               // 例: "USDCHFmicro"
      if(StringLen(sym) < 6) continue;
      string pb = StringSubstr(sym, 0, 3);       // ポジションの base
      string pq = StringSubstr(sym, 3, 3);       // ポジションの quote
      bool pos_long = (g_pos.PositionType() == POSITION_TYPE_BUY);
      // 既存ポジションの通貨方向: base は買いなら+1、quote は逆
      int pb_e = pos_long ? 1 : -1;
      int pq_e = pos_long ? -1 : 1;
      // 新規候補の通貨方向
      int nb_e = is_long ? 1 : -1;
      int nq_e = is_long ? -1 : 1;
      if((pb == base  && pb_e == nb_e) || (pb == quote && pb_e == nq_e) ||
         (pq == base  && pq_e == nb_e) || (pq == quote && pq_e == nq_e))
         cnt++;
   }
   return cnt;
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
