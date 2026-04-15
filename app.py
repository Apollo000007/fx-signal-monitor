"""FX シグナル監視アプリ (Tkinter GUI)。

使い方:
    python app.py

機能:
    - 15 通貨ペアを 3 時間軸で自動分析
    - スコア順にソートして一覧表示
    - 条件ヒット時に音 + Discord/LINE 通知
    - 行クリックで詳細表示
"""
from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from tkinter import scrolledtext, ttk

import config
from alerts import (
    format_signal_message,
    play_beep,
    send_discord,
    send_line_push,
)
from data_fetcher import fetch_all
from strategy import analyze_pair


SORT_KEYS = {
    "rank": lambda s: 0,
    "pair": lambda s: s.pair,
    "score": lambda s: s.score,
    "dir": lambda s: s.direction,
    "lt": lambda s: s.lt.direction if s.lt else "",
    "mt": lambda s: s.mt.direction if s.mt else "",
    "st": lambda s: s.st.direction if s.st else "",
    "price": lambda s: s.price,
    "sl": lambda s: s.stop_loss or 0,
}


class FXSignalApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("FX Signal Monitor")
        root.geometry("1200x720")

        self.signals: list = []
        self.last_update: datetime | None = None
        self.auto_refresh = tk.BooleanVar(value=True)
        self.alerted_keys: set = set()  # (pair, direction, YYYYMMDDHH)
        self.sort_col = "score"
        self.sort_reverse = True

        self._build_ui()

        # 起動直後に初回取得
        self.root.after(600, self.refresh_async)

    # ---------- UI ----------

    def _build_ui(self) -> None:
        # 上部: コントロールバー
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)

        self.refresh_btn = ttk.Button(top, text="手動更新", command=self.refresh_async)
        self.refresh_btn.pack(side=tk.LEFT)

        ttk.Checkbutton(top, text="自動更新", variable=self.auto_refresh).pack(side=tk.LEFT, padx=8)

        self.status_var = tk.StringVar(value="初期化中...")
        ttk.Label(top, textvariable=self.status_var, font=("Meiryo", 10)).pack(side=tk.LEFT, padx=8)

        info = (
            f"閾値: {config.ALERT_THRESHOLD}  |  "
            f"更新間隔: {config.REFRESH_SECONDS}秒  |  "
            f"長期: {config.LONG_LABEL}  中期: {config.MID_LABEL}  短期: {config.SHORT_LABEL}"
        )
        ttk.Label(top, text=info, font=("Meiryo", 9)).pack(side=tk.RIGHT)

        # メイン: 分割パネル
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # 左: Treeview
        left = ttk.Frame(paned)
        paned.add(left, weight=3)

        columns = ("rank", "pair", "score", "dir", "lt", "mt", "st", "price", "sl")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", height=22)
        headings = {
            "rank": ("#", 36),
            "pair": ("ペア", 80),
            "score": ("スコア", 64),
            "dir": ("方向", 64),
            "lt": ("日足", 84),
            "mt": ("1H", 84),
            "st": ("15M", 84),
            "price": ("価格", 100),
            "sl": ("損切目安", 100),
        }
        for col, (label, w) in headings.items():
            self.tree.heading(col, text=label, command=lambda c=col: self.sort_by(c))
            self.tree.column(col, width=w, anchor=tk.CENTER)

        vsb = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # タグによる着色
        self.tree.tag_configure("alert", background="#fff3b0")
        self.tree.tag_configure("long", foreground="#0a6b2c")
        self.tree.tag_configure("short", foreground="#b30000")
        self.tree.tag_configure("none", foreground="#888888")

        # 右: 詳細パネル
        right = ttk.Frame(paned, padding=4)
        paned.add(right, weight=2)

        ttk.Label(right, text="詳細分析", font=("Meiryo", 11, "bold")).pack(anchor=tk.W)
        self.detail = scrolledtext.ScrolledText(
            right, wrap=tk.WORD, width=44, height=30, font=("Meiryo", 9)
        )
        self.detail.pack(fill=tk.BOTH, expand=True)
        self.detail.insert(tk.END, "左のリストから銘柄を選ぶと詳細を表示します。\n\n")
        self.detail.insert(tk.END, "スコアの内訳 (合計100点):\n")
        self.detail.insert(tk.END, "  +15 日足トレンド (ダウ理論)\n")
        self.detail.insert(tk.END, "  +25 4Hトレンド (メイン判定)\n")
        self.detail.insert(tk.END, "  +15 4Hで押し目/戻り目ゾーン\n")
        self.detail.insert(tk.END, "  +10 日足に障害物なし\n")
        self.detail.insert(tk.END, "  +25 15M エントリートリガー\n")
        self.detail.insert(tk.END, "  +5  4H 一目均衡表の雲\n")
        self.detail.insert(tk.END, "  +5  4H MACD ヒストグラム\n")
        self.detail.insert(tk.END, "\n※ 15Mトリガー未発生はスコア70にキャップ\n")
        self.detail.insert(tk.END, "   (セットアップは表示、通知はトリガー時のみ)\n")
        self.detail.config(state=tk.DISABLED)

    # ---------- ソート ----------

    def sort_by(self, col: str) -> None:
        if col == self.sort_col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_col = col
            self.sort_reverse = col in ("score",)
        key = SORT_KEYS.get(col, SORT_KEYS["score"])
        try:
            self.signals.sort(key=key, reverse=self.sort_reverse)
        except TypeError:
            pass
        self.render_tree()

    # ---------- データ更新 ----------

    def refresh_async(self) -> None:
        self.refresh_btn.config(state=tk.DISABLED)
        self.status_var.set("データ取得中...")
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _do_refresh(self) -> None:
        try:
            pairs_items = list(config.PAIRS.items())
            symbols = [s for _, s in pairs_items]
            long_d, mid_d, short_d = fetch_all(
                symbols,
                config.LONG_INTERVAL, config.LONG_PERIOD, config.LONG_RESAMPLE,
                config.MID_INTERVAL, config.MID_PERIOD, config.MID_RESAMPLE,
                config.SHORT_INTERVAL, config.SHORT_PERIOD, config.SHORT_RESAMPLE,
            )
            signals = []
            for label, symbol in pairs_items:
                sig = analyze_pair(
                    label, symbol,
                    long_d.get(symbol),
                    mid_d.get(symbol),
                    short_d.get(symbol),
                )
                signals.append(sig)
            signals.sort(key=SORT_KEYS[self.sort_col], reverse=self.sort_reverse)
            self.signals = signals
            self.last_update = datetime.now()
            self.root.after(0, self._on_refresh_done, None)
        except Exception as e:
            self.root.after(0, self._on_refresh_done, e)

    def _on_refresh_done(self, error: Exception | None) -> None:
        self.refresh_btn.config(state=tk.NORMAL)
        if error is not None:
            self.status_var.set(f"エラー: {error}")
        else:
            ts = self.last_update.strftime("%Y-%m-%d %H:%M:%S") if self.last_update else ""
            hits = sum(1 for s in self.signals if s.score >= config.ALERT_THRESHOLD)
            self.status_var.set(f"更新完了: {ts}  (閾値超え {hits}/{len(self.signals)})")
            self.render_tree()
            self.check_alerts()

        if self.auto_refresh.get():
            self.root.after(config.REFRESH_SECONDS * 1000, self.refresh_async)

    # ---------- 描画 ----------

    def render_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, s in enumerate(self.signals, 1):
            tags = []
            if s.direction == "long":
                tags.append("long")
            elif s.direction == "short":
                tags.append("short")
            else:
                tags.append("none")
            if s.score >= config.ALERT_THRESHOLD and s.direction != "none":
                tags.append("alert")
            values = (
                i,
                s.pair,
                s.score,
                s.direction.upper() if s.direction != "none" else "-",
                (s.lt.direction if s.lt else "-"),
                (s.mt.direction if s.mt else "-"),
                (s.st.direction if s.st else "-"),
                f"{s.price:.4f}" if s.price else "-",
                f"{s.stop_loss:.4f}" if s.stop_loss else "-",
            )
            self.tree.insert("", tk.END, iid=str(i), values=values, tags=tuple(tags))

    def on_select(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            idx = int(sel[0]) - 1
        except ValueError:
            return
        if idx < 0 or idx >= len(self.signals):
            return
        s = self.signals[idx]

        lines = [
            f"ペア: {s.pair}   ({s.symbol})",
            f"方向: {s.direction.upper()}",
            f"スコア: {s.score} / 100",
            f"現在値: {s.price:.4f}" if s.price else "現在値: -",
            f"損切目安: {s.stop_loss:.4f}" if s.stop_loss else "損切目安: -",
            f"利確目標: {s.take_profit:.4f}" if s.take_profit else "利確目標: -",
            "",
            "― 根拠 ―",
        ]
        lines += [f"  ・{r}" for r in s.reasons]
        if s.warnings:
            lines += ["", "― 警告 ―"]
            lines += [f"  ! {w}" for w in s.warnings]

        def _tf_block(label: str, tf) -> list[str]:
            if tf is None:
                return []
            out = [
                "",
                f"― {label} ―",
                f"  方向        : {tf.direction}",
                f"  終値        : {tf.close:.4f}",
                f"  SMA20/50/100: {tf.sma20:.4f} / {tf.sma50:.4f} / {tf.sma100:.4f}",
                f"  雲          : {tf.cloud_bottom:.4f} 〜 {tf.cloud_top:.4f} (価格: {tf.price_vs_cloud})",
                f"  MACDヒスト  : {tf.macd_hist:+.5f}",
            ]
            if tf.last_swing_high and tf.last_swing_low:
                out.append(f"  直近スイング: 高{tf.last_swing_high:.4f} / 安{tf.last_swing_low:.4f}")
            if tf.resistances:
                out.append(f"  上レジスタンス: " + ", ".join(f"{lv:.4f}" for lv in tf.resistances))
            if tf.supports:
                out.append(f"  下サポート    : " + ", ".join(f"{lv:.4f}" for lv in tf.supports))
            return out

        lines += _tf_block(config.LONG_LABEL, s.lt)
        lines += _tf_block(config.MID_LABEL, s.mt)
        lines += _tf_block(config.SHORT_LABEL, s.st)

        self.detail.config(state=tk.NORMAL)
        self.detail.delete("1.0", tk.END)
        self.detail.insert(tk.END, "\n".join(lines))
        self.detail.config(state=tk.DISABLED)

    # ---------- アラート ----------

    def check_alerts(self) -> None:
        """閾値超えの新規シグナルに対してアラート発火。
        同一 (ペア, 方向) は 1 時間に 1 度まで。"""
        if not self.last_update:
            return
        hour_key = self.last_update.strftime("%Y%m%d%H")
        for s in self.signals:
            if s.direction == "none" or s.score < config.ALERT_THRESHOLD:
                continue
            key = (s.pair, s.direction, hour_key)
            if key in self.alerted_keys:
                continue
            self.alerted_keys.add(key)
            self.fire_alert(s)

    def fire_alert(self, signal) -> None:
        if config.PLAY_SOUND:
            threading.Thread(target=play_beep, daemon=True).start()
        msg = format_signal_message(signal)
        if config.DISCORD_WEBHOOK_URL:
            threading.Thread(
                target=send_discord,
                args=(config.DISCORD_WEBHOOK_URL, msg),
                daemon=True,
            ).start()
        if config.LINE_CHANNEL_ACCESS_TOKEN and config.LINE_USER_ID:
            threading.Thread(
                target=send_line_push,
                args=(config.LINE_CHANNEL_ACCESS_TOKEN, config.LINE_USER_ID, msg),
                daemon=True,
            ).start()


def main() -> None:
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        else:
            style.theme_use("clam")
    except tk.TclError:
        pass
    FXSignalApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
