//+------------------------------------------------------------------+
//|                                                    FXSignal.mq5  |
//|         fx-signal-monitor 5 手法シグナルを MT5 上に視覚化する     |
//|         チャートインディケータ (発注機能なし、表示のみ)            |
//|                                                                  |
//|  動作:                                                            |
//|   1. WebRequest で Vercel の signals.json を取得                  |
//|   2. 現在チャートの通貨ペアに対応するレコードを抽出                │
//|   3. 以下を描画:                                                  │
//|      - SMA 20/50/100 (MT5 内蔵 iMA)                              │
//|      - 一目均衡表の雲 (MT5 内蔵 iIchimoku)                       │
//|      - 前日高値 / 前日安値 ライン (API から取得)                 │
//|      - エントリー / 損切り / 利確 / 2R / 3R ライン (シグナル発火時) │
//|      - 大型情報パネル (4H 相場タイプ / 5 手法のスコア・状態 / 根拠)│
//|      - エントリーバーに矢印                                       │
//|                                                                  │
//|  必須セットアップ:                                                │
//|   MT5 メニュー → Tools → Options → Expert Advisors              │
//|   "Allow WebRequest for listed URL" にチェック                   │
//|   URL リストに以下を追加:                                          │
//|     https://fx-signal-monitor.vercel.app                          │
//+------------------------------------------------------------------+
#property copyright "fx-signal-monitor"
#property link      "https://fx-signal-monitor.vercel.app"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

#include "Include/JsonExtract.mqh"

//=== 入力パラメータ ============================================================
input group "── API 取得設定 ──"
input string  ApiUrl        = "https://fx-signal-monitor.vercel.app/api/signals.json"; // signals.json URL
input int     RefreshSec    = 60;        // API ポーリング間隔 (秒)
input bool    AutoMapSymbol = true;      // チャート通貨を自動マッピング (USDJPY → USD/JPY)

input group "── 主軸手法 ──"
input string  PrimaryMethod = "triple";  // 主軸表示する手法: orz / pdhl / both / claude / triple

input group "── 表示要素 ──"
input bool    ShowSMA20     = true;
input bool    ShowSMA50     = true;
input bool    ShowSMA100    = true;
input bool    ShowCloud     = true;      // 一目均衡表の雲
input bool    ShowPDHL      = true;      // 前日高値・前日安値
input bool    ShowSignalLines = true;    // エントリー/SL/TP ライン (alert 時)
input bool    Show2R3RLines = true;      // 資産管理 2R/3R 利確ライン
input bool    ShowPanel     = true;      // 左上の情報パネル
input bool    ShowArrow     = true;      // 発火バーに矢印

input group "── 色設定 ──"
input color   ClrSMA20      = clrAqua;
input color   ClrSMA50      = clrOrchid;
input color   ClrSMA100     = clrOrange;
input color   ClrCloudUp    = C'168,85,247';      // 紫
input color   ClrCloudDown  = C'34,211,238';      // シアン
input color   ClrPDH        = C'74,222,128';      // 緑
input color   ClrPDL        = C'226,92,115';      // 赤
input color   ClrEntry      = C'34,211,238';      // シアン
input color   ClrSL         = C'226,92,115';      // 赤
input color   ClrTPstruct   = C'74,222,128';      // 緑
input color   Clr2RTP       = C'56,189,248';      // 青
input color   Clr3RTP       = C'233,196,106';     // 金
input color   PanelBg       = C'20,18,46';
input color   PanelBorder   = C'58,46,94';
input color   PanelText     = C'245,236,215';

input group "── パネル配置 ──"
input int     PanelX        = 12;       // 左マージン
input int     PanelY        = 24;       // 上マージン
input int     PanelW        = 360;
input int     FontSize      = 9;

//=== グローバル状態 ============================================================
string g_prefix = "FXSig_";    // チャートオブジェクト prefix (削除時用)
datetime g_last_fetch = 0;
string g_json_cache = "";       // 直近の signals.json 生データ
string g_last_record = "";      // 現在ペアのレコード JSON
string g_status_text = "Initializing...";

// 描画ハンドル
int h_sma20 = INVALID_HANDLE, h_sma50 = INVALID_HANDLE, h_sma100 = INVALID_HANDLE;
int h_ichimoku = INVALID_HANDLE;

// 現在のシグナル値 (タイマー更新)
double g_pdh = EMPTY_VALUE, g_pdl = EMPTY_VALUE;
double g_entry = EMPTY_VALUE, g_sl = EMPTY_VALUE, g_tp = EMPTY_VALUE;
double g_tp2r = EMPTY_VALUE, g_tp3r = EMPTY_VALUE;
string g_direction = "none";
int g_score = 0;
bool g_has_trigger = false;
bool g_is_alert = false;
string g_entry_type = "";
string g_regime = "";              // 4H regime
int g_clarity = 0;
string g_reasons_buf[];
int g_reasons_count = 0;

// 各手法の状態 (パネル表示用)
struct MethodState { string m; int score; string direction; bool has_trig; bool is_alert; };
MethodState g_methods[5];

//+------------------------------------------------------------------+
int OnInit()
{
   //--- インジケータ表示名
   IndicatorSetString(INDICATOR_SHORTNAME, "FX Signal Monitor [" + PrimaryMethod + "]");
   IndicatorSetInteger(INDICATOR_DIGITS, _Digits);

   //--- 内蔵テクニカル指標ハンドル
   if(ShowSMA20)
      h_sma20 = iMA(_Symbol, _Period, 20, 0, MODE_SMA, PRICE_CLOSE);
   if(ShowSMA50)
      h_sma50 = iMA(_Symbol, _Period, 50, 0, MODE_SMA, PRICE_CLOSE);
   if(ShowSMA100)
      h_sma100 = iMA(_Symbol, _Period, 100, 0, MODE_SMA, PRICE_CLOSE);
   if(ShowCloud)
      h_ichimoku = iIchimoku(_Symbol, _Period, 9, 26, 52);

   //--- パネル初期描画 (まだ JSON 取得前)
   if(ShowPanel) DrawPanel(true);

   //--- タイマー起動 (RefreshSec 秒ごとに OnTimer)
   EventSetTimer(RefreshSec);

   //--- 初回フェッチを即座に実行
   FetchAndUpdate();
   return INIT_SUCCEEDED;
}
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   if(h_sma20 != INVALID_HANDLE) IndicatorRelease(h_sma20);
   if(h_sma50 != INVALID_HANDLE) IndicatorRelease(h_sma50);
   if(h_sma100 != INVALID_HANDLE) IndicatorRelease(h_sma100);
   if(h_ichimoku != INVALID_HANDLE) IndicatorRelease(h_ichimoku);

   //--- 描画オブジェクト全削除
   ObjectsDeleteAll(0, g_prefix);
   Comment("");
}
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   //--- SMA / 雲 はネイティブのサブインジケータが描画するので何もしない
   //    (このインジケータは chart_window 上のラインだけを管理)
   return rates_total;
}
//+------------------------------------------------------------------+
void OnTimer()
{
   FetchAndUpdate();
}
//+------------------------------------------------------------------+
//| 通貨ペア名のマッピング:                                            |
//|   MT5 のチャート symbol "USDJPY" / "USDJPY.m" / "USDJPY-pro" など   |
//|   → Python が使う "USD/JPY" 形式に変換                              |
//+------------------------------------------------------------------+
string MapSymbolToPair(string mt5_symbol)
{
   string s = mt5_symbol;
   //--- 末尾の broker サフィックスを除去
   string suffixes[] = {".m", ".pro", "-pro", "_pro", "pro", "m", "i", "x", ".x"};
   for(int i = 0; i < ArraySize(suffixes); i++)
   {
      int p = StringFind(s, suffixes[i], StringLen(s) - StringLen(suffixes[i]));
      if(p >= 0 && p == StringLen(s) - StringLen(suffixes[i]))
      {
         s = StringSubstr(s, 0, p);
         break;
      }
   }
   StringToUpper(s);
   if(StringLen(s) >= 6)
      return StringSubstr(s, 0, 3) + "/" + StringSubstr(s, 3, 3);
   return s;
}
//+------------------------------------------------------------------+
//| Vercel から signals.json を取得して現在ペアのデータを抽出           |
//+------------------------------------------------------------------+
void FetchAndUpdate()
{
   //--- 1) WebRequest で取得
   char post[];
   char result[];
   string headers;
   int timeout = 5000;
   string req_headers = "";

   ResetLastError();
   int code = WebRequest("GET", ApiUrl, req_headers, timeout, post, result, headers);
   if(code != 200)
   {
      int err = GetLastError();
      g_status_text = StringFormat("API err: HTTP=%d MQL=%d (URL を WebRequest 許可済?)", code, err);
      Print("[FXSignal] ", g_status_text);
      DrawPanel(false);
      return;
   }

   //--- 2) bytes → string 変換
   g_json_cache = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
   g_last_fetch = TimeCurrent();

   //--- 3) 現在ペアのレコード抽出
   string pair_key = AutoMapSymbol ? MapSymbolToPair(_Symbol) : _Symbol;
   g_last_record = JsonFindRecord(g_json_cache, pair_key);
   if(g_last_record == "")
   {
      g_status_text = StringFormat("ペア %s が signals.json に見つからない", pair_key);
      Print("[FXSignal] ", g_status_text);
      DrawPanel(false);
      return;
   }

   //--- 4) PDH / PDL
   g_pdh = JsonGetNumber(g_last_record, "pdh");
   g_pdl = JsonGetNumber(g_last_record, "pdl");

   //--- 5) 各手法のサマリを取得 (パネル表示用)
   string method_keys[5] = {"orz","pdhl","both","claude","triple"};
   for(int i = 0; i < 5; i++)
   {
      string m_obj = JsonGetMethodObj(g_last_record, method_keys[i]);
      g_methods[i].m = method_keys[i];
      g_methods[i].score = (int)JsonGetNumber(m_obj, "score", 0);
      g_methods[i].direction = JsonGetString(m_obj, "direction");
      g_methods[i].has_trig = JsonGetBool(m_obj, "has_trigger");
      g_methods[i].is_alert = JsonGetBool(m_obj, "is_alert");
   }

   //--- 6) 主軸メソッドの詳細 (エントリー / SL / TP)
   string primary_obj = JsonGetMethodObj(g_last_record, PrimaryMethod);
   if(primary_obj == "")
   {
      g_status_text = StringFormat("手法 %s が見つからない", PrimaryMethod);
      DrawPanel(false);
      return;
   }
   g_direction   = JsonGetString(primary_obj, "direction");
   g_score       = (int)JsonGetNumber(primary_obj, "score", 0);
   g_entry       = JsonGetNumber(primary_obj, "price");
   g_sl          = JsonGetNumber(primary_obj, "stop_loss");
   g_tp          = JsonGetNumber(primary_obj, "take_profit");
   g_has_trigger = JsonGetBool(primary_obj, "has_trigger");
   g_is_alert    = JsonGetBool(primary_obj, "is_alert");
   g_entry_type  = JsonGetString(primary_obj, "entry_type");
   g_reasons_count = JsonGetStringArray(primary_obj, "reasons", g_reasons_buf, 6);

   //--- 4H レコードから regime / clarity
   string mt_obj = JsonGetMethodObj(g_last_record, "mt");
   if(mt_obj != "")
   {
      g_regime  = JsonGetString(mt_obj, "regime");
      g_clarity = (int)JsonGetNumber(mt_obj, "clarity", 0);
   }

   //--- 7) 2R / 3R 利確を計算 (Entry と SL から)
   if(g_entry != EMPTY_VALUE && g_sl != EMPTY_VALUE && (g_direction == "long" || g_direction == "short"))
   {
      double r = MathAbs(g_entry - g_sl);
      if(g_direction == "long")
      {
         g_tp2r = g_entry + 2.0 * r;
         g_tp3r = g_entry + 3.0 * r;
      }
      else
      {
         g_tp2r = g_entry - 2.0 * r;
         g_tp3r = g_entry - 3.0 * r;
      }
   }
   else
   {
      g_tp2r = EMPTY_VALUE;
      g_tp3r = EMPTY_VALUE;
   }

   g_status_text = StringFormat("OK · %s · 取得 %s", pair_key, TimeToString(g_last_fetch, TIME_MINUTES));

   //--- 8) 全部描画
   DrawAll();
}
//+------------------------------------------------------------------+
//| 全描画オブジェクトを再構築                                          |
//+------------------------------------------------------------------+
void DrawAll()
{
   //--- 古いオブジェクトは全部消す (prefix で識別)
   ObjectsDeleteAll(0, g_prefix);

   //--- 水平線
   if(ShowPDHL && g_pdh != EMPTY_VALUE)
      DrawHLine("PDH", g_pdh, ClrPDH, STYLE_SOLID, 2, "前日高値 " + DoubleToString(g_pdh, _Digits));
   if(ShowPDHL && g_pdl != EMPTY_VALUE)
      DrawHLine("PDL", g_pdl, ClrPDL, STYLE_SOLID, 2, "前日安値 " + DoubleToString(g_pdl, _Digits));

   //--- シグナル発火時のライン群
   if(ShowSignalLines && g_is_alert)
   {
      if(g_entry != EMPTY_VALUE)
         DrawHLine("Entry", g_entry, ClrEntry, STYLE_DOT, 2, "Entry " + DoubleToString(g_entry, _Digits));
      if(g_sl != EMPTY_VALUE)
         DrawHLine("SL", g_sl, ClrSL, STYLE_SOLID, 2, "損切り (1R) " + DoubleToString(g_sl, _Digits));
      if(g_tp != EMPTY_VALUE)
         DrawHLine("TPstruct", g_tp, ClrTPstruct, STYLE_SOLID, 2, "利確 (構造) " + DoubleToString(g_tp, _Digits));

      if(Show2R3RLines)
      {
         if(g_tp2r != EMPTY_VALUE)
            DrawHLine("TP2R", g_tp2r, Clr2RTP, STYLE_DASH, 2, "利確@2R 最低基準 " + DoubleToString(g_tp2r, _Digits));
         if(g_tp3r != EMPTY_VALUE)
            DrawHLine("TP3R", g_tp3r, Clr3RTP, STYLE_SOLID, 3, "★ 利確@3R 推奨 " + DoubleToString(g_tp3r, _Digits));
      }

      //--- エントリーバーに矢印
      if(ShowArrow && (g_direction == "long" || g_direction == "short"))
         DrawArrow(g_entry, g_direction);
   }

   //--- パネル
   if(ShowPanel) DrawPanel(true);
   ChartRedraw();
}
//+------------------------------------------------------------------+
//| 水平線描画 (右端のラベル付き)                                       |
//+------------------------------------------------------------------+
void DrawHLine(const string id, const double price, const color clr, const int style, const int width, const string label)
{
   string obj_name = g_prefix + "Line_" + id;
   if(!ObjectCreate(0, obj_name, OBJ_HLINE, 0, 0, price))
   {
      ObjectSetDouble(0, obj_name, OBJPROP_PRICE, price);
   }
   ObjectSetInteger(0, obj_name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, obj_name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, obj_name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, obj_name, OBJPROP_BACK, false);
   ObjectSetInteger(0, obj_name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, obj_name, OBJPROP_HIDDEN, true);
   ObjectSetString(0, obj_name, OBJPROP_TOOLTIP, label);

   //--- ラベルテキスト (右端に貼り付け)
   string txt_name = g_prefix + "Lbl_" + id;
   datetime t_last = iTime(_Symbol, _Period, 0);
   ObjectCreate(0, txt_name, OBJ_TEXT, 0, t_last + PeriodSeconds(_Period) * 3, price);
   ObjectSetString(0, txt_name, OBJPROP_TEXT, label);
   ObjectSetInteger(0, txt_name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, txt_name, OBJPROP_FONTSIZE, 9);
   ObjectSetString(0, txt_name, OBJPROP_FONT, "Arial Bold");
   ObjectSetInteger(0, txt_name, OBJPROP_ANCHOR, ANCHOR_LEFT);
   ObjectSetInteger(0, txt_name, OBJPROP_SELECTABLE, false);
}
//+------------------------------------------------------------------+
//| エントリーバー上に矢印                                              |
//+------------------------------------------------------------------+
void DrawArrow(double price, const string direction)
{
   string obj = g_prefix + "ArrowEntry";
   datetime t0 = iTime(_Symbol, _Period, 0);
   bool is_long = (direction == "long");
   int code = is_long ? 233 : 234;   // 233=上矢印, 234=下矢印 (Wingdings)
   double y = is_long ? iLow(_Symbol, _Period, 0) - 5 * _Point * 10 : iHigh(_Symbol, _Period, 0) + 5 * _Point * 10;
   if(!ObjectCreate(0, obj, OBJ_ARROW, 0, t0, y)) ObjectMove(0, obj, 0, t0, y);
   ObjectSetInteger(0, obj, OBJPROP_ARROWCODE, code);
   ObjectSetInteger(0, obj, OBJPROP_COLOR, is_long ? ClrPDH : ClrPDL);
   ObjectSetInteger(0, obj, OBJPROP_WIDTH, 4);
   ObjectSetInteger(0, obj, OBJPROP_SELECTABLE, false);
}
//+------------------------------------------------------------------+
//| 左上の情報パネル (Rectangle Label + 複数 Label)                     |
//+------------------------------------------------------------------+
void DrawPanel(bool full)
{
   //--- 背景
   string bg = g_prefix + "PanelBg";
   if(ObjectFind(0, bg) < 0)
   {
      ObjectCreate(0, bg, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, bg, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, bg, OBJPROP_XDISTANCE, PanelX);
      ObjectSetInteger(0, bg, OBJPROP_YDISTANCE, PanelY);
      ObjectSetInteger(0, bg, OBJPROP_XSIZE, PanelW);
      ObjectSetInteger(0, bg, OBJPROP_YSIZE, 280);
      ObjectSetInteger(0, bg, OBJPROP_BGCOLOR, PanelBg);
      ObjectSetInteger(0, bg, OBJPROP_BORDER_COLOR, PanelBorder);
      ObjectSetInteger(0, bg, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, bg, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, bg, OBJPROP_BACK, false);
      ObjectSetInteger(0, bg, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, bg, OBJPROP_HIDDEN, true);
   }

   int line_h = FontSize + 6;
   int y = PanelY + 10;
   int x = PanelX + 14;

   //--- タイトル
   string pair = AutoMapSymbol ? MapSymbolToPair(_Symbol) : _Symbol;
   PanelLabel("Title", x, y, "FX SIGNAL · " + pair, C'233,196,106', FontSize + 3, true);
   y += line_h + 6;

   if(!full || g_last_record == "")
   {
      PanelLabel("Status", x, y, g_status_text, C'201,184,138', FontSize, false);
      return;
   }

   //--- 4H regime + clarity
   color regime_color = C'201,184,138';
   string regime_label = "—";
   if(g_regime == "trend_up")   { regime_color = ClrPDH; regime_label = "上昇トレンド"; }
   else if(g_regime == "trend_down") { regime_color = ClrPDL; regime_label = "下降トレンド"; }
   else if(g_regime == "range") { regime_color = C'168,85,247'; regime_label = "レンジ"; }
   else if(g_regime == "unclear") { regime_color = C'122,107,154'; regime_label = "不明瞭"; }

   PanelLabel("Regime", x, y,
              StringFormat("4H: %s  明瞭度 %d/100", regime_label, g_clarity),
              regime_color, FontSize, false);
   y += line_h;

   //--- 主軸手法の direction / score (大型)
   color dir_color = (g_direction == "long") ? ClrPDH : (g_direction == "short") ? ClrPDL : C'201,184,138';
   string dir_label = (g_direction == "long") ? "▲ LONG" : (g_direction == "short") ? "▼ SHORT" : "— WAIT";
   string state_label;
   if(g_is_alert)         state_label = "★ ALERT";
   else if(g_has_trigger) state_label = "TRIGGER";
   else                   state_label = "SETUP";

   PanelLabel("Primary", x, y,
              StringFormat("[%s] %s  Score %d/100  %s",
                           PrimaryMethod, dir_label, g_score, state_label),
              dir_color, FontSize + 2, true);
   y += line_h + 4;

   //--- Entry / SL / TP / 3R
   if(g_is_alert)
   {
      PanelLabel("Entry", x, y, StringFormat("Entry : %s", DoubleToString(g_entry, _Digits)), ClrEntry, FontSize, false);
      y += line_h;
      PanelLabel("SL", x, y, StringFormat("損切り: %s  (1R)", DoubleToString(g_sl, _Digits)), ClrSL, FontSize, false);
      y += line_h;
      PanelLabel("TPstruct", x, y, StringFormat("利確 : %s  (構造)", DoubleToString(g_tp, _Digits)), ClrTPstruct, FontSize, false);
      y += line_h;
      if(g_tp3r != EMPTY_VALUE)
      {
         PanelLabel("TP3R", x, y, StringFormat("★3R  : %s  (推奨)", DoubleToString(g_tp3r, _Digits)), Clr3RTP, FontSize, false);
         y += line_h;
      }
   }
   else
   {
      PanelLabel("WaitMsg", x, y, "シグナル待機中 — エントリー条件未充足", C'122,107,154', FontSize, false);
      y += line_h;
   }
   y += 4;

   //--- 5 手法サマリ (mini grid)
   PanelLabel("MethodsHeader", x, y, "── 5 手法スコア ──", C'201,184,138', FontSize - 1, true);
   y += line_h;
   for(int i = 0; i < 5; i++)
   {
      string ms = StringFormat("%-7s %3d  %-5s %s",
                               StringSubstr(StringFormat("%s.....", g_methods[i].m), 0, 7),
                               g_methods[i].score,
                               g_methods[i].direction == "none" ? "—" : g_methods[i].direction,
                               g_methods[i].is_alert ? "★" : g_methods[i].has_trig ? "▶" : "·");
      color row_clr = C'201,184,138';
      if(g_methods[i].is_alert)         row_clr = C'233,196,106';
      else if(g_methods[i].has_trig)    row_clr = C'168,85,247';
      else if(g_methods[i].direction == "long")  row_clr = ClrPDH;
      else if(g_methods[i].direction == "short") row_clr = ClrPDL;

      PanelLabel("M" + IntegerToString(i), x, y, ms, row_clr, FontSize - 1, false);
      y += line_h - 2;
   }
   y += 4;

   //--- 根拠 (最大 4 件)
   if(g_reasons_count > 0)
   {
      PanelLabel("ReasonsHdr", x, y, "── 根拠 ──", C'201,184,138', FontSize - 1, true);
      y += line_h;
      int max_show = MathMin(4, g_reasons_count);
      for(int i = 0; i < max_show; i++)
      {
         string r = g_reasons_buf[i];
         if(StringLen(r) > 48) r = StringSubstr(r, 0, 47) + "…";
         PanelLabel("R" + IntegerToString(i), x, y, "• " + r, C'201,184,138', FontSize - 1, false);
         y += line_h - 2;
      }
      y += 4;
   }

   //--- フッター
   PanelLabel("Footer", x, y, "API: " + g_status_text, C'122,107,154', FontSize - 2, false);
   y += line_h;

   //--- 背景の高さ調整
   int total_h = y - PanelY + 8;
   ObjectSetInteger(0, g_prefix + "PanelBg", OBJPROP_YSIZE, total_h);
}
//+------------------------------------------------------------------+
//| OBJ_LABEL 1 行を生成/更新                                          |
//+------------------------------------------------------------------+
void PanelLabel(const string id, int x, int y, const string text, const color clr, const int font_size, const bool bold)
{
   string name = g_prefix + "Pl_" + id;
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
   }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, font_size);
   ObjectSetString(0, name, OBJPROP_FONT, bold ? "Arial Bold" : "Arial");
}
//+------------------------------------------------------------------+
