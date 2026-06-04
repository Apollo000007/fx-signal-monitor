//+------------------------------------------------------------------+
//|                                                  FXSignalEA.mq5  |
//|         fx-signal-monitor シグナル連動 自動売買 EA                 |
//|                                                                  |
//|  設計思想:                                                        |
//|     - シグナル生成は Python 側 (Vercel) に任せる (単一の真実)     |
//|     - EA は signals.json をポーリングし、is_alert=True で発注する │
//|     - Magic Number でこの EA の建玉だけ管理 (他 EA / 手動注文と  │
//|       競合しない)                                                  │
//|     - 手法 orz/pdhl/triple/dtp/pa を任意に有効化可能。デフォルト │
//|       は triple のみ (+EV 実証)。pdhl/orz は降格 (is_alert 出ず) │
//|     - SL / TP は MT5 サーバ側に乗せる (PC が落ちても約定する)    │
//|     - UseTP3R=true で 3R 利確 (推奨)、false でも signals.json 側 │
//|       で最低2R床済 (risk.min_rr_tp) なので 1:1 にはならない      │
//|     - is_alert は Python 側で +EV ゲート済 (ev_whitelist):       │
//|       DTPは4ペアのみ・PDHL/ORZは出ない。EA は is_alert に従うだけ │
//|       → 推奨: UseTriple=true + UseDTP=true, MaxConcurrentTrades  │
//|         で相関上限を絞る (2週間デモの GBP/USD3連敗の再発防止)    │
//|                                                                  │
//|  安全装置:                                                        │
//|     - MaxConcurrentTrades : 同時建玉上限                          │
//|     - MaxDailyLossPercent : 当日損失 N% 超で新規エントリー停止   │
//|     - MaxSpreadPips       : スプレッドが広い時は見送り            │
//|     - 取引時間ガード (UTC 月曜 0時 〜 金曜 22時 のみ)              │
//|     - DryRun              : 注文を実際には出さずログのみ          │
//|                                                                  │
//|  必須セットアップ:                                                │
//|     Tools → Options → Expert Advisors                            │
//|     ✅ Allow Algorithmic Trading                                  │
//|     ✅ Allow WebRequest for listed URL                            │
//|     URL リスト: https://fx-signal-monitor.vercel.app              │
//+------------------------------------------------------------------+
#property copyright "fx-signal-monitor"
#property link      "https://fx-signal-monitor.vercel.app"
#property version   "1.00"
#property description "Auto trading EA powered by fx-signal-monitor 5-strategy signals"

#include "Include/JsonExtract.mqh"
#include "Include/RiskMgmt.mqh"
#include "Include/TradeOps.mqh"

//=== 入力パラメータ ============================================================
input group "━━━ 1. 基本設定 ━━━"
input bool    EnableTrading      = false;   // ★ false の間は注文しない (動作確認用)
input bool    DryRun             = true;    // ★ true なら実発注せずログのみ
input string  ApiUrl             = "https://fx-signal-monitor.vercel.app/api/signals.json";
input int     RefreshSec         = 60;      // API ポーリング間隔 (秒)
input long    MagicBase          = 880000;  // この EA の建玉に振る magic 番号の基点

input group "━━━ 2. 対象通貨ペア ━━━"
input string  TradingPairs       = "USDJPY,EURUSD,GBPUSD,AUDUSD,NZDUSD,USDCAD,USDCHF,EURJPY,GBPJPY,AUDJPY,NZDJPY,CADJPY,CHFJPY,EURGBP"; // カンマ区切り (ZARJPY除外)
input bool    AutoMapSymbol      = true;    // ブローカーのサフィックスを自動付与 (USDJPY → USDJPY.m 等)

input group "━━━ 3. 有効化する手法 ━━━"
input bool    UseORZ             = false;
input bool    UsePDHL            = false;
input bool    UseTriple          = true;    // デフォルトは triple のみ (backtest 60d で唯一の +EV)
input bool    UseDTP             = false;   // Daily Trend Pullback (検証してから有効化推奨)
input bool    UsePA              = false;   // Price Action ローソク足パターン (EVホワイトリスト準拠)
// 注: claude / both 手法は廃止。triple の内部計算では claude を使うが
//     単独の発注対象からは除外 (magic index は互換維持のため据え置き)

input group "━━━ 4. リスク・資金管理 ━━━"
input double  AccountRiskPercent = 0.5;     // 1 トレードあたりのリスク% (口座残高比)
input int     MaxConcurrentTrades= 5;       // 同時建玉上限
input double  MaxDailyLossPercent= 3.0;     // 当日損失 N% 超 で新規停止
input bool    UseTP3R            = true;    // true: 3R 利確、false: 構造的 TP
input double  MaxSpreadPips      = 3.0;     // スプレッド広時は見送り
input int     SlippagePoints     = 30;      // 許容スリッページ (points; 1 pip = 10 points で digits=5)

input group "━━━ 5. 取引時間ガード ━━━"
input bool    UseTimeGuard       = true;    // 週末・休場時間は禁止
input int     WeekStart_Hour     = 22;      // 日曜 22:00 UTC から取引解禁 (= 月曜朝アジア時間)
input int     WeekEnd_Hour       = 21;      // 金曜 21:00 UTC で取引終了 (= NY クローズ前)

input group "━━━ 6. ロギング ━━━"
input bool    Verbose            = true;    // 詳細ログ

//=== グローバル ================================================================
string g_json_cache = "";
datetime g_last_fetch = 0;
int g_pairs_count = 0;
string g_pairs[];
string g_pairs_yfinance[];  // "USD/JPY" 形式
string g_pairs_mt5[];       // ブローカー固有名 (USDJPY, USDJPY.m 等)
long g_magic_min = 0, g_magic_max = 0;

bool g_use_methods[7];      // {orz, pdhl, both, claude, triple, dtp, pa}
string g_method_names[7] = {"orz", "pdhl", "both", "claude", "triple", "dtp", "pa"};

//+------------------------------------------------------------------+
int OnInit()
{
   //--- パラメータの sanity check
   if(MagicBase < 100)
   {
      Print("[FXSignalEA] MagicBase は 100 以上にしてください");
      return INIT_PARAMETERS_INCORRECT;
   }
   g_magic_min = MagicBase;
   g_magic_max = MagicBase + 14 * 10 + 6;  // 最大 pair_idx=14, method_idx=6 (pa)

   //--- ペア配列を構築
   ParseTradingPairs();
   if(g_pairs_count == 0)
   {
      Print("[FXSignalEA] TradingPairs が空です");
      return INIT_PARAMETERS_INCORRECT;
   }

   //--- 手法フラグ
   g_use_methods[0] = UseORZ;
   g_use_methods[1] = UsePDHL;
   g_use_methods[2] = false;        // both 廃止
   g_use_methods[3] = false;        // claude 廃止 (triple 内部計算でのみ使用)
   g_use_methods[4] = UseTriple;
   g_use_methods[5] = UseDTP;
   g_use_methods[6] = UsePA;
   bool any = false;
   for(int i = 0; i < 7; i++) if(g_use_methods[i]) { any = true; break; }
   if(!any)
   {
      Print("[FXSignalEA] 少なくとも 1 つの手法を有効化してください");
      return INIT_PARAMETERS_INCORRECT;
   }

   //--- 初期メッセージ
   PrintFormat("[FXSignalEA] init: %d pairs, methods=%s%s%s%s%s, risk=%.2f%%, dryrun=%s, trading=%s",
               g_pairs_count,
               UseORZ ? "ORZ " : "",
               UsePDHL ? "PDHL " : "",
               UseTriple ? "TRIPLE " : "",
               UseDTP ? "DTP " : "",
               UsePA ? "PA " : "",
               AccountRiskPercent,
               DryRun ? "ON" : "OFF",
               EnableTrading ? "ON" : "OFF");

   //--- 初回フェッチを少し遅らせる (init 終了後)
   EventSetTimer(RefreshSec);
   //--- 初回はすぐ
   ProcessSignals();
   return INIT_SUCCEEDED;
}
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("[FXSignalEA] deinit, reason=", reason);
}
//+------------------------------------------------------------------+
void OnTimer()
{
   ProcessSignals();
}
//+------------------------------------------------------------------+
//| TradingPairs (CSV) をパース。MT5 のブローカー名へのマッピング込み |
//+------------------------------------------------------------------+
void ParseTradingPairs()
{
   string raw = TradingPairs;
   StringReplace(raw, " ", "");
   string parts[];
   int n = StringSplit(raw, ',', parts);
   g_pairs_count = 0;
   ArrayResize(g_pairs_yfinance, n);
   ArrayResize(g_pairs_mt5, n);

   for(int i = 0; i < n; i++)
   {
      string p = parts[i];
      if(StringLen(p) < 6) continue;
      string mt5_name = ResolveBrokerSymbol(p);
      if(mt5_name == "")
      {
         PrintFormat("[FXSignalEA] ペア %s はブローカー名で見つかりません — スキップ", p);
         continue;
      }
      //--- yfinance 形式 (USD/JPY) を作る
      string yf_name = StringSubstr(p, 0, 3) + "/" + StringSubstr(p, 3, 3);
      g_pairs_yfinance[g_pairs_count] = yf_name;
      g_pairs_mt5[g_pairs_count] = mt5_name;
      g_pairs_count++;
   }
   ArrayResize(g_pairs_yfinance, g_pairs_count);
   ArrayResize(g_pairs_mt5, g_pairs_count);
}
//+------------------------------------------------------------------+
//| "USDJPY" → ブローカー固有のシンボル名 (USDJPY / USDJPY.m / USDJPY-pro 等)
//| Market Watch に存在しないものは "" を返す                          |
//+------------------------------------------------------------------+
string ResolveBrokerSymbol(const string base)
{
   string candidates[] = {base, base + ".m", base + ".pro", base + "-pro", base + "_pro", base + ".x", base + "i"};
   for(int i = 0; i < ArraySize(candidates); i++)
   {
      if(SymbolSelect(candidates[i], true)) return candidates[i];
   }
   return "";
}
//+------------------------------------------------------------------+
//| シグナル取得 → 各ペア × 各 method を評価して発注                   |
//+------------------------------------------------------------------+
void ProcessSignals()
{
   //--- 1) 取引時間ガード
   if(UseTimeGuard && !IsTradingTimeOK())
   {
      if(Verbose) Print("[FXSignalEA] 時間外 (週末/休場) - skip");
      return;
   }

   //--- 2) 日次損失リミット
   if(IsDailyLossLimitHit(MaxDailyLossPercent))
   {
      if(Verbose)
         PrintFormat("[FXSignalEA] 日次損失 %.2f%% (限度 %.2f%%) - 新規エントリー停止",
                     GetDailyPnLPercent(), MaxDailyLossPercent);
      return;
   }

   //--- 3) 同時建玉数チェック
   int current_positions = CountOpenPositionsByMagicBase(g_magic_min, g_magic_max);
   if(current_positions >= MaxConcurrentTrades)
   {
      if(Verbose) PrintFormat("[FXSignalEA] 同時建玉上限 %d 到達 - skip", MaxConcurrentTrades);
      return;
   }

   //--- 4) API フェッチ
   if(!FetchSignalsJson())
   {
      return;
   }

   //--- 5) 各ペア × 各 method を評価
   for(int p = 0; p < g_pairs_count; p++)
   {
      EvaluatePair(p, current_positions);
      //--- 上限到達なら break
      current_positions = CountOpenPositionsByMagicBase(g_magic_min, g_magic_max);
      if(current_positions >= MaxConcurrentTrades) break;
   }
}
//+------------------------------------------------------------------+
//| 取引時間 OK?                                                       |
//|   日曜 WeekStart_Hour 以前は NG                                    |
//|   金曜 WeekEnd_Hour 以降は NG                                      |
//|   土曜は終日 NG                                                    |
//+------------------------------------------------------------------+
bool IsTradingTimeOK()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);  // サーバ時刻
   int dow = dt.day_of_week;          // 0=Sun, 1=Mon, ..., 6=Sat

   if(dow == 6) return false;          // 土曜は完全休止
   if(dow == 0 && dt.hour < WeekStart_Hour) return false;
   if(dow == 5 && dt.hour >= WeekEnd_Hour) return false;
   return true;
}
//+------------------------------------------------------------------+
bool FetchSignalsJson()
{
   char post[];
   char result[];
   string resp_headers;
   ResetLastError();
   int code = WebRequest("GET", ApiUrl, "", 5000, post, result, resp_headers);
   if(code != 200)
   {
      int err = GetLastError();
      PrintFormat("[FXSignalEA] API エラー: HTTP=%d MQL=%d (URL を WebRequest 許可済?)", code, err);
      return false;
   }
   g_json_cache = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
   g_last_fetch = TimeCurrent();
   return true;
}
//+------------------------------------------------------------------+
//| 1 ペアを 5 手法分評価                                              |
//+------------------------------------------------------------------+
void EvaluatePair(const int pair_index, int current_positions_unused)
{
   string yf_name = g_pairs_yfinance[pair_index];
   string mt5_name = g_pairs_mt5[pair_index];

   string record = JsonFindRecord(g_json_cache, yf_name);
   if(record == "")
   {
      if(Verbose) PrintFormat("[FXSignalEA] %s レコード無し", yf_name);
      return;
   }

   //--- スプレッドフィルター
   double spread_pips = CurrentSpreadPips(mt5_name);
   if(spread_pips > MaxSpreadPips)
   {
      if(Verbose) PrintFormat("[FXSignalEA] %s スプレッド %.1fpips > %.1f - skip",
                              mt5_name, spread_pips, MaxSpreadPips);
      return;
   }

   //--- 各 method を評価
   for(int mi = 0; mi < 7; mi++)
   {
      if(!g_use_methods[mi]) continue;
      string method = g_method_names[mi];

      //--- 既に同 pair × method で建玉中ならスキップ
      long magic = BuildMagic(MagicBase, pair_index, mi);
      if(HasOpenPositionWithMagic(magic)) continue;

      //--- メソッド objects を取得
      string m_obj = JsonGetMethodObj(record, method);
      if(m_obj == "") continue;

      bool is_alert = JsonGetBool(m_obj, "is_alert");
      if(!is_alert) continue;

      string direction = JsonGetString(m_obj, "direction");
      double entry     = JsonGetNumber(m_obj, "price");
      double sl        = JsonGetNumber(m_obj, "stop_loss");
      double tp_struct = JsonGetNumber(m_obj, "take_profit");
      int    score     = (int)JsonGetNumber(m_obj, "score", 0);

      if((direction != "long" && direction != "short")
         || entry == EMPTY_VALUE || sl == EMPTY_VALUE)
         continue;

      //--- TP 選択: 3R 推奨 or 構造
      double tp_final;
      if(UseTP3R)
      {
         double r = MathAbs(entry - sl);
         tp_final = (direction == "long") ? entry + 3.0 * r : entry - 3.0 * r;
      }
      else
      {
         if(tp_struct == EMPTY_VALUE) continue;
         tp_final = tp_struct;
      }

      //--- direction と SL/TP の整合性 sanity check
      if(direction == "long" && !(sl < entry && entry < tp_final))
      {
         PrintFormat("[FXSignalEA] %s %s long: SL/TP 不整合 entry=%.5f SL=%.5f TP=%.5f - skip",
                     yf_name, method, entry, sl, tp_final);
         continue;
      }
      if(direction == "short" && !(tp_final < entry && entry < sl))
      {
         PrintFormat("[FXSignalEA] %s %s short: SL/TP 不整合 entry=%.5f SL=%.5f TP=%.5f - skip",
                     yf_name, method, entry, sl, tp_final);
         continue;
      }

      //--- ロット計算
      //    SL までの距離は entry-SL で計算するが、約定価格はライブの bid/ask になるので
      //    後段で再計算して NormalizeLot する
      double lot = CalcLotByRisk(mt5_name, AccountRiskPercent, entry, sl);
      if(lot <= 0)
      {
         PrintFormat("[FXSignalEA] %s %s ロット計算失敗 - skip", yf_name, method);
         continue;
      }

      //--- ログ
      string action = DryRun ? "DRYRUN" : (EnableTrading ? "OPEN" : "DISABLED");
      PrintFormat("[FXSignalEA] [%s] %s %s %s score=%d entry=%.5f SL=%.5f TP=%.5f lot=%.2f spread=%.1fp",
                  action, yf_name, method, direction, score,
                  entry, sl, tp_final, lot, spread_pips);

      //--- 発注
      if(!EnableTrading || DryRun) continue;

      string comment_str = StringFormat("FXS:%s:%s", method, yf_name);
      ulong ticket = OpenMarketOrder(
         mt5_name, direction, lot, sl, tp_final, magic, SlippagePoints, comment_str
      );
      if(ticket > 0)
      {
         //--- 建玉数チェックを再度
         int positions_now = CountOpenPositionsByMagicBase(g_magic_min, g_magic_max);
         if(positions_now >= MaxConcurrentTrades) return;
      }
   }
}
//+------------------------------------------------------------------+
