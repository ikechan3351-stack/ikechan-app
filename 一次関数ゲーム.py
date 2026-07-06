# ============================================================
# 一次関数ゲーム（Python / tkinter 版）
# ------------------------------------------------------------
# 実行方法:
#   ターミナルで  python3 一次関数ゲーム.py
#   （tkinter は Python に最初から入っているので追加インストール不要）
#
# HTML版（一次関数ゲーム.html）と同じ区分で書いてあります。
# 「同じゲームを別の言語で書くとどうなるか」を見比べてみてください。
# ============================================================

import tkinter as tk
import random
import math
import sys
import subprocess
from fractions import Fraction   # Python標準の「分数」クラス

# ===== 定数（ゲーム全体の設定）=====
W, H = 480, 480          # キャンバスの大きさ（ピクセル）
SCALE = 22               # 1マスの大きさ → -10〜10 が画面に入る
CX, CY = W / 2, H / 2    # 原点（画面の中央）
TOTAL = 10               # 全10問
HIT_DIST = 0.45          # 命中とみなす距離

BG    = "#1a1a2e"        # 背景色
PANEL = "#16213e"        # 右パネルの色
BOX   = "#0f3460"        # ボタン・式表示の背景色
FONT  = "Hiragino Sans"

ACCENT = {1: "#6c63ff", 2: "#ff7a3d", 3: "#2ecc71"}   # レベルごとのテーマ色
MUZZLE = {1: "#7a5fd0", 2: "#c85a1e", 3: "#1e8f4e"}   # 大砲の砲口の色
BODYC  = {1: "#9b7ede", 2: "#ff9a56", 3: "#2ecc71"}   # 大砲の本体の色

# 問題に使う数
INT_SLOPES  = [-4, -3, -2, -1, 1, 2, 3, 4]
FRAC_SLOPES = [Fraction(1, 2), Fraction(1, 3), Fraction(2, 3),
               Fraction(-1, 2), Fraction(-1, 3), Fraction(-2, 3)]
FIX_SLOPES  = [-2, -1, 1, 2]
FIX_FRAC    = [Fraction(1, 2), Fraction(1, 3), Fraction(2, 3), Fraction(-1, 2)]
INTERCEPTS  = list(range(-5, 6))
A_POOL      = [-3, -2, -1, 1, 2, 3]
B_POOL      = list(range(-5, 6))

LEVEL_NAMES = {1: "レベル1（かたむき）", 2: "レベル2（切片）", 3: "レベル3（2個同時）"}


# 座標変換：グラフの座標 → 画面のピクセル
def sx(x): return CX + x * SCALE
def sy(y): return CY - y * SCALE


class Game:
    def __init__(self, root):
        self.root = root
        root.title("一次関数ゲーム（Python版）")
        root.configure(bg=BG)

        # --- 状態を入れる変数 ---
        self.state = "menu"          # menu / playing / gameover
        self.sound_on = True
        self.sel_level = 1           # メニューで選択中のレベル
        self.sel_time = 10           # メニューで選択中のタイム
        self.level = 1
        self.problem_time = 10
        self.problem_index = 0
        self.score = 0
        self.timer_val = 10.0
        self.target = None           # Lv1・2の的
        self.targets = []            # Lv3の的（2個）
        self.beam = None
        self.shot_fired = False
        self.resolving = False
        self.loop_after_id = None
        self.next_after_id = None
        # 選択中の答え
        self.sel_slope = None
        self.sel_intercept = None
        self.sel_a = None
        self.sel_b = None
        # 正解
        self.correct_slope = None
        self.fixed_slope = None
        self.correct_intercept = 0
        self.correct_a = 0
        self.correct_b = 0
        self.choice_rows = {}

        # --- 3つの画面を作る ---
        self.build_menu_ui()
        self.build_game_ui()
        self.build_result_ui()
        self.show_frame(self.menu_frame)

        # ウィンドウを前面に出す（Macでは後ろに隠れて開くことがあるため）
        root.lift()
        root.attributes("-topmost", True)
        root.after(500, lambda: root.attributes("-topmost", False))
        root.focus_force()

    # ===== 画面切り替え =====
    def show_frame(self, frame):
        for f in (self.menu_frame, self.game_frame, self.result_frame):
            f.pack_forget()
        frame.pack(padx=14, pady=14)

    def cancel_afters(self):
        for attr in ("loop_after_id", "next_after_id"):
            aid = getattr(self, attr)
            if aid:
                self.root.after_cancel(aid)
                setattr(self, attr, None)

    # ===== メニュー画面 =====
    def build_menu_ui(self):
        f = tk.Frame(self.root, bg=BG)
        self.menu_frame = f

        tk.Label(f, text="🎯 一次関数ゲーム", font=(FONT, 26, "bold"),
                 fg="white", bg=BG).pack(pady=(16, 2))
        tk.Label(f, text="かたむきや切片を決めて、円盤を撃ち落とそう！",
                 font=(FONT, 13), fg="#b8b8e0", bg=BG).pack(pady=(0, 18))

        tk.Label(f, text="レベルをえらぶ", font=(FONT, 12, "bold"),
                 fg="#888", bg=BG).pack(anchor="w", padx=6)

        descs = [
            ("📈  レベル1", "かたむき a をあてる（y = ax）"),
            ("📊  レベル2", "傾き固定・切片 b をあてる（y = ax + b）"),
            ("🎯  レベル3", "傾きと切片の両方・円盤2個を撃墜！"),
        ]
        self.level_cards = []
        for i, (name, desc) in enumerate(descs):
            card = tk.Frame(f, bg="#0f1a33", highlightthickness=2,
                            highlightbackground="#334", padx=12, pady=8, cursor="hand2")
            card.pack(fill="x", pady=4, padx=4)
            tk.Label(card, text=name, font=(FONT, 15, "bold"),
                     fg=ACCENT[i + 1], bg="#0f1a33", anchor="w").pack(fill="x")
            tk.Label(card, text=desc, font=(FONT, 11),
                     fg="#99a", bg="#0f1a33", anchor="w").pack(fill="x")
            self.bind_deep(card, lambda e, lv=i + 1: self.pick_level(lv))
            self.level_cards.append(card)

        tk.Label(f, text="1問のタイムをえらぶ", font=(FONT, 12, "bold"),
                 fg="#888", bg=BG).pack(anchor="w", padx=6, pady=(16, 2))

        tf = tk.Frame(f, bg=BG)
        tf.pack(fill="x", padx=4)
        self.time_btns = []
        for t, d in [(10, "むずかしい"), (20, "ふつう"), (30, "やさしい")]:
            b = tk.Frame(tf, bg="#0f1a33", highlightthickness=2,
                         highlightbackground="#334", padx=10, pady=6, cursor="hand2")
            b.pack(side="left", expand=True, fill="x", padx=4)
            tk.Label(b, text=f"{t}秒", font=(FONT, 15, "bold"),
                     fg="white", bg="#0f1a33").pack()
            tk.Label(b, text=d, font=(FONT, 10),
                     fg="#99a", bg="#0f1a33").pack()
            self.bind_deep(b, lambda e, tt=t: self.pick_time(tt))
            self.time_btns.append((t, b))

        start = tk.Label(f, text="▶ スタート", font=(FONT, 17, "bold"),
                         bg="#6c63ff", fg="white", pady=12, cursor="hand2")
        start.pack(fill="x", pady=(22, 8), padx=4)
        start.bind("<Button-1>", lambda e: self.start_game())

        self.update_menu_styles()

    def bind_deep(self, widget, fn):
        """枠の中の文字をクリックしても反応するように、子どもにも同じ処理を付ける"""
        widget.bind("<Button-1>", fn)
        for c in widget.winfo_children():
            self.bind_deep(c, fn)

    def pick_level(self, lv):
        self.sel_level = lv
        self.update_menu_styles()

    def pick_time(self, t):
        self.sel_time = t
        self.update_menu_styles()

    def update_menu_styles(self):
        for i, card in enumerate(self.level_cards):
            sel = (i + 1 == self.sel_level)
            card.config(highlightbackground="#ffd700" if sel else "#334")
        for t, b in self.time_btns:
            sel = (t == self.sel_time)
            b.config(highlightbackground="#ffd700" if sel else "#334")

    # ===== ゲーム画面 =====
    def build_game_ui(self):
        f = tk.Frame(self.root, bg=BG)
        self.game_frame = f

        top = tk.Frame(f, bg=BG)
        top.pack(pady=(0, 8))
        tk.Label(top, text="🎯 一次関数ゲーム", font=(FONT, 18, "bold"),
                 fg="#e0e0ff", bg=BG).pack(side="left")
        self.sound_btn = tk.Label(top, text="🔊", font=(FONT, 14), fg="white",
                                  bg=PANEL, padx=10, pady=3, cursor="hand2")
        self.sound_btn.pack(side="left", padx=12)
        self.sound_btn.bind("<Button-1>", lambda e: self.toggle_sound())

        body = tk.Frame(f, bg=BG)
        body.pack()

        self.canvas = tk.Canvas(body, width=W, height=H, bg="#f0f6ff",
                                highlightthickness=3, highlightbackground=ACCENT[1])
        self.canvas.grid(row=0, column=0, padx=(0, 12), sticky="n")

        p = tk.Frame(body, bg=PANEL, padx=14, pady=12)
        p.grid(row=0, column=1, sticky="n")

        r1 = tk.Frame(p, bg=PANEL)
        r1.pack(fill="x")
        tk.Label(r1, text="⏱ この問題", font=(FONT, 12), fg="#e0e0ff",
                 bg=PANEL).pack(side="left")
        self.time_lbl = tk.Label(r1, text="10", font=(FONT, 18, "bold"),
                                 fg="#ffb84d", bg=PANEL)
        self.time_lbl.pack(side="right")

        self.bar = tk.Canvas(p, width=212, height=10, bg="#333", highlightthickness=0)
        self.bar.pack(pady=(2, 8))
        self.bar_fill = self.bar.create_rectangle(0, 0, 212, 10,
                                                  fill=ACCENT[1], width=0)

        r2 = tk.Frame(p, bg=PANEL)
        r2.pack(fill="x")
        tk.Label(r2, text="問題", font=(FONT, 12), fg="#e0e0ff", bg=PANEL).pack(side="left")
        self.prob_lbl = tk.Label(r2, text="1 / 10", font=(FONT, 13, "bold"),
                                 fg="white", bg=PANEL)
        self.prob_lbl.pack(side="right")

        r3 = tk.Frame(p, bg=PANEL)
        r3.pack(fill="x", pady=(2, 8))
        tk.Label(r3, text="💯 得点", font=(FONT, 12), fg="#e0e0ff", bg=PANEL).pack(side="left")
        self.score_lbl = tk.Label(r3, text="0", font=(FONT, 18, "bold"),
                                  fg="#ffb84d", bg=PANEL)
        self.score_lbl.pack(side="right")

        self.fixed_lbl = tk.Label(p, text="", font=(FONT, 13, "bold"),
                                  fg="#ffb84d", bg="#3a2a1a", pady=5)
        # ↑Lv2のときだけ pack して表示する

        self.formula_lbl = tk.Label(p, text="y = ? × x", font=(FONT, 16, "bold"),
                                    fg="white", bg=BOX, pady=8)
        self.formula_lbl.pack(fill="x", pady=4)

        self.choice_area = tk.Frame(p, bg=PANEL)
        self.choice_area.pack(fill="x", pady=4)

        self.shoot_lbl = tk.Label(p, text="🚀 発射！", font=(FONT, 15, "bold"),
                                  bg="#555", fg="#999", pady=10, cursor="hand2")
        self.shoot_lbl.pack(fill="x", pady=6)
        self.shoot_lbl.bind("<Button-1>", lambda e: self.shoot())

        self.msg_lbl = tk.Label(p, text="", font=(FONT, 13, "bold"),
                                fg="white", bg=PANEL, wraplength=200, height=2)
        self.msg_lbl.pack(fill="x")

        back = tk.Label(p, text="≡ メニューに戻る", font=(FONT, 10, "underline"),
                        fg="#889", bg=PANEL, cursor="hand2")
        back.pack(pady=(4, 0))
        back.bind("<Button-1>", lambda e: self.show_menu())

    # ===== 結果画面 =====
    def build_result_ui(self):
        self.result_frame = tk.Frame(self.root, bg=BG)

    # ===== サウンド（macOS の afplay で効果音を鳴らす）=====
    def play(self, kind):
        if not self.sound_on:
            return
        names = {"shoot": "Pop", "hit": "Glass", "miss": "Basso", "end": "Hero"}
        if sys.platform == "darwin":
            try:
                subprocess.Popen(
                    ["afplay", f"/System/Library/Sounds/{names[kind]}.aiff"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        else:
            self.root.bell()

    def toggle_sound(self):
        self.sound_on = not self.sound_on
        self.sound_btn.config(text="🔊" if self.sound_on else "🔇")

    # ===== ゲーム開始 =====
    def start_game(self):
        self.cancel_afters()
        self.level = self.sel_level
        self.problem_time = self.sel_time
        self.state = "playing"
        self.problem_index = 0
        self.score = 0
        self.score_lbl.config(text="0")
        ac = ACCENT[self.level]
        self.canvas.config(highlightbackground=ac)
        self.bar.itemconfig(self.bar_fill, fill=ac)
        self.show_frame(self.game_frame)
        self.new_problem()
        self.game_loop()

    def show_menu(self):
        self.state = "menu"
        self.cancel_afters()
        self.show_frame(self.menu_frame)

    # ===== 問題づくり =====
    def new_problem(self):
        self.resolving = False
        self.shot_fired = False
        self.beam = None
        self.timer_val = float(self.problem_time)
        self.sel_slope = self.sel_intercept = self.sel_a = self.sel_b = None
        self.msg_lbl.config(text="")
        self.prob_lbl.config(text=f"{self.problem_index + 1} / {TOTAL}")
        is_frac = self.problem_index >= 8   # 最後の2問は分数

        if self.level == 1:
            if is_frac:
                self.correct_slope = random.choice(FRAC_SLOPES)
                k = random.choice([-2, 2])
                tx = self.correct_slope.denominator * k
                ty = self.correct_slope.numerator * k
            else:
                self.correct_slope = random.choice(INT_SLOPES)
                while True:
                    tx = random.randint(-4, 4)
                    ty = self.correct_slope * tx
                    if tx != 0 and abs(ty) <= 9:
                        break
            self.target = {"x": tx, "y": ty, "hit": False}

        elif self.level == 2:
            self.fixed_slope = random.choice(FIX_FRAC if is_frac else FIX_SLOPES)
            self.correct_intercept = random.choice(INTERCEPTS)
            for _ in range(60):
                if is_frac:
                    k = random.choice([-2, -1, 1, 2])
                    tx = Fraction(self.fixed_slope).denominator * k
                else:
                    tx = random.randint(-4, 4) or 3
                ty = self.fixed_slope * tx + self.correct_intercept
                if abs(ty) <= 9:
                    break
            self.target = {"x": int(tx), "y": int(ty), "hit": False}
            self.fixed_lbl.config(text=f"傾き a = {self.fixed_slope}（固定）")

        else:  # レベル3
            while True:
                self.correct_a = random.choice(A_POOL)
                self.correct_b = random.choice(B_POOL)
                xs = [x for x in [-4, -3, -2, -1, 1, 2, 3, 4]
                      if abs(self.correct_a * x + self.correct_b) <= 9]
                if len(xs) >= 2:
                    break
            random.shuffle(xs)
            self.targets = [
                {"x": xs[0], "y": self.correct_a * xs[0] + self.correct_b, "hit": False},
                {"x": xs[1], "y": self.correct_a * xs[1] + self.correct_b, "hit": False},
            ]

        # Lv2のときだけ「傾き固定」表示を出す
        if self.level == 2:
            self.fixed_lbl.pack(fill="x", pady=2, before=self.formula_lbl)
        else:
            self.fixed_lbl.pack_forget()

        self.rebuild_choices()
        self.update_formula()
        self.refresh_shoot()
        self.draw_scene()

    # ===== 選択肢（6択）=====
    def rebuild_choices(self):
        for w in self.choice_area.winfo_children():
            w.destroy()
        self.choice_rows = {}

        if self.level == 1:
            pool = FRAC_SLOPES if self.problem_index >= 8 else INT_SLOPES
            self.make_row(pool, self.correct_slope, str, "single", self.pick_single)
        elif self.level == 2:
            self.make_row(INTERCEPTS, self.correct_intercept,
                          lambda v: f"b = {v}", "single", self.pick_single)
        else:
            tk.Label(self.choice_area, text="傾き a", font=(FONT, 11, "bold"),
                     fg="#aaa", bg=PANEL, anchor="w").pack(fill="x")
            self.make_row(A_POOL, self.correct_a, str, "a", self.pick_a)
            tk.Label(self.choice_area, text="切片 b", font=(FONT, 11, "bold"),
                     fg="#aaa", bg=PANEL, anchor="w").pack(fill="x")
            self.make_row(B_POOL, self.correct_b, str, "b", self.pick_b)

    def make_row(self, pool, correct, to_text, key, cmd):
        others = [v for v in pool if v != correct]
        random.shuffle(others)
        choices = [correct] + others[:5]
        random.shuffle(choices)

        fr = tk.Frame(self.choice_area, bg=PANEL)
        fr.pack(fill="x", pady=2)
        row = []
        for i, v in enumerate(choices):
            lb = tk.Label(fr, text=to_text(v), font=(FONT, 13, "bold"),
                          bg=BOX, fg="#e0e0ff", pady=7, cursor="hand2")
            lb.grid(row=i // 3, column=i % 3, padx=3, pady=3, sticky="ew")
            lb.bind("<Button-1>", lambda e, v=v, w=lb, c=cmd: c(v, w))
            row.append((v, lb))
        for c in range(3):
            fr.grid_columnconfigure(c, weight=1)
        self.choice_rows[key] = row

    def restyle_row(self, key, selected_val):
        for v, w in self.choice_rows.get(key, []):
            if v == selected_val:
                w.config(bg=ACCENT[self.level], fg="white")
            else:
                w.config(bg=BOX, fg="#e0e0ff")

    def pick_single(self, v, w):
        if self.shot_fired:
            return
        if self.level == 1:
            self.sel_slope = v
        else:
            self.sel_intercept = v
        self.restyle_row("single", v)
        self.update_formula()
        self.refresh_shoot()
        self.draw_scene()

    def pick_a(self, v, w):
        if self.shot_fired:
            return
        self.sel_a = v
        self.restyle_row("a", v)
        self.update_formula()
        self.refresh_shoot()
        self.draw_scene()

    def pick_b(self, v, w):
        if self.shot_fired:
            return
        self.sel_b = v
        self.restyle_row("b", v)
        self.update_formula()
        self.refresh_shoot()
        self.draw_scene()

    # ===== 式の表示・発射ボタンの状態 =====
    def update_formula(self):
        if self.level == 1:
            a = self.sel_slope if self.sel_slope is not None else "?"
            self.formula_lbl.config(text=f"y = {a} × x")
        elif self.level == 2:
            self.formula_lbl.config(text=self.eq_str(self.fixed_slope, self.sel_intercept))
        else:
            a = self.sel_a if self.sel_a is not None else "?"
            if self.sel_b is None:
                bt = "+ ?"
            elif self.sel_b >= 0:
                bt = f"+ {self.sel_b}"
            else:
                bt = f"- {abs(self.sel_b)}"
            self.formula_lbl.config(text=f"y = {a}x {bt}")

    @staticmethod
    def eq_str(a, b):
        if b is None:
            return f"y = {a}x + ?"
        if b == 0:
            return f"y = {a}x"
        return f"y = {a}x {'+' if b > 0 else '-'} {abs(b)}"

    def can_shoot(self):
        if self.level == 1:
            return self.sel_slope is not None
        if self.level == 2:
            return self.sel_intercept is not None
        return self.sel_a is not None and self.sel_b is not None

    def refresh_shoot(self):
        ok = self.can_shoot() and not self.shot_fired
        self.shoot_lbl.config(bg=ACCENT[self.level] if ok else "#555",
                              fg="white" if ok else "#999")

    # ===== 発射・当たり判定 =====
    def shoot(self):
        if self.state != "playing" or self.beam or self.shot_fired:
            return
        if not self.can_shoot():
            return
        if self.level == 1:
            a, b = float(self.sel_slope), 0.0
            d = 1 if self.target["x"] >= 0 else -1
            self.beam = {"a": a, "b": b, "x": 0.0, "x0": 0.0, "dir": d, "speed": 0.32}
        elif self.level == 2:
            a, b = float(self.fixed_slope), float(self.sel_intercept)
            d = 1 if self.target["x"] >= 0 else -1
            self.beam = {"a": a, "b": b, "x": 0.0, "x0": 0.0, "dir": d, "speed": 0.32}
        else:
            self.beam = {"a": float(self.sel_a), "b": float(self.sel_b),
                         "x": -9.0, "x0": -9.0, "dir": 1, "speed": 0.44}
        self.shot_fired = True
        self.play("shoot")
        self.refresh_shoot()
        self.reveal_answers()

    def reveal_answers(self):
        """発射したら、正解を緑・まちがった選択を赤にする"""
        checks = []
        if self.level == 1:
            checks = [("single", self.correct_slope, self.sel_slope)]
        elif self.level == 2:
            checks = [("single", self.correct_intercept, self.sel_intercept)]
        else:
            checks = [("a", self.correct_a, self.sel_a),
                      ("b", self.correct_b, self.sel_b)]
        for key, correct, chosen in checks:
            for v, w in self.choice_rows.get(key, []):
                if v == correct:
                    w.config(bg="#27ae60", fg="white")
                elif v == chosen:
                    w.config(bg="#c0392b", fg="white")

    def update_beam(self):
        if not self.beam:
            return
        bm = self.beam
        bm["x"] += bm["dir"] * bm["speed"]
        y = bm["a"] * bm["x"] + bm["b"]

        if self.level == 3:
            for t in self.targets:
                if not t["hit"] and math.hypot(bm["x"] - t["x"], y - t["y"]) < HIT_DIST:
                    t["hit"] = True
            if bm["x"] > 9:
                self.beam = None
                self.finalize_lv3()
            return

        t = self.target
        if math.hypot(bm["x"] - t["x"], y - t["y"]) < HIT_DIST:
            t["hit"] = True
            self.score += 10
            self.score_lbl.config(text=str(self.score))
            self.play("hit")
            self.set_msg("🎉 命中！ +10点", "#2ecc71")
            self.beam = None
            self.schedule_next(1000)
        elif abs(bm["x"]) > 11 or abs(y) > 11:
            self.play("miss")
            self.set_msg(f"😢 ハズレ… 正解は {self.answer_text()}", "#ff6b6b")
            self.beam = None
            self.schedule_next(1200)

    def finalize_lv3(self):
        hits = sum(1 for t in self.targets if t["hit"])
        self.score += hits * 5
        self.score_lbl.config(text=str(self.score))
        if hits > 0:
            self.play("hit")
        else:
            self.play("miss")
        if hits == 2:
            self.set_msg("🎉 2個命中！ +10点", "#2ecc71")
        elif hits == 1:
            self.set_msg(f"😲 1個命中 +5点（正解 {self.answer_text()}）", "#ffb84d")
        else:
            self.set_msg(f"😢 ハズレ… 正解は {self.answer_text()}", "#ff6b6b")
        self.schedule_next(1300)

    def answer_text(self):
        if self.level == 1:
            return f"a={self.correct_slope}"
        if self.level == 2:
            return f"b={self.correct_intercept}"
        return f"a={self.correct_a}, b={self.correct_b}"

    def set_msg(self, text, color):
        self.msg_lbl.config(text=text, fg=color)

    # ===== 次の問題へ =====
    def schedule_next(self, ms):
        if self.resolving:
            return
        self.resolving = True
        self.next_after_id = self.root.after(ms, self.advance)

    def advance(self):
        self.next_after_id = None
        if self.state != "playing":
            return
        self.problem_index += 1
        if self.problem_index >= TOTAL:
            self.end_game()
        else:
            self.new_problem()

    # ===== ゲームループ（30ミリ秒ごとに繰り返す）=====
    def game_loop(self):
        if self.state != "playing":
            return
        if not self.shot_fired and not self.resolving:
            self.timer_val -= 0.03
            if self.timer_val <= 0:
                self.timer_val = 0
                self.shot_fired = True
                self.play("miss")
                self.set_msg(f"⏰ 時間切れ！ 正解は {self.answer_text()}", "#ffb84d")
                self.refresh_shoot()
                self.schedule_next(1200)

        self.time_lbl.config(text=str(math.ceil(max(self.timer_val, 0))))
        frac = max(self.timer_val, 0) / self.problem_time
        self.bar.coords(self.bar_fill, 0, 0, 212 * frac, 10)

        self.update_beam()
        self.draw_scene()
        self.loop_after_id = self.root.after(30, self.game_loop)

    # ===== 終了 =====
    def end_game(self):
        self.state = "gameover"
        self.cancel_afters()
        self.play("end")

        if self.score >= 100:
            rank = "🏆 パーフェクト！天才！"
        elif self.score >= 70:
            rank = "🥇 すばらしい！"
        elif self.score >= 40:
            rank = "🥈 よくできました！"
        else:
            rank = "🥉 もう一度チャレンジ！"

        f = self.result_frame
        for w in f.winfo_children():
            w.destroy()
        tk.Label(f, text="🎉 ゲーム終了！", font=(FONT, 24, "bold"),
                 fg="#ffb84d", bg=BG).pack(pady=(30, 4))
        tk.Label(f, text=f"{LEVEL_NAMES[self.level]} ・ 1問 {self.problem_time}秒",
                 font=(FONT, 12), fg="#b8b8e0", bg=BG).pack()
        tk.Label(f, text=rank, font=(FONT, 15, "bold"),
                 fg="#ffb84d", bg=BG).pack(pady=(14, 0))
        tk.Label(f, text=f"{self.score} / 100点", font=(FONT, 40, "bold"),
                 fg="white", bg=BG).pack(pady=(4, 20))

        btns = tk.Frame(f, bg=BG)
        btns.pack(pady=(0, 30))
        again = tk.Label(btns, text="🔄 もう一度", font=(FONT, 14, "bold"),
                         bg="#6c63ff", fg="white", padx=24, pady=10, cursor="hand2")
        again.pack(side="left", padx=6)
        again.bind("<Button-1>", lambda e: self.start_game())
        menu = tk.Label(btns, text="≡ メニュー", font=(FONT, 14, "bold"),
                        bg="#445", fg="white", padx=24, pady=10, cursor="hand2")
        menu.pack(side="left", padx=6)
        menu.bind("<Button-1>", lambda e: self.show_menu())

        self.show_frame(self.result_frame)

    # ===== 描画（毎フレーム全部描き直す）=====
    def draw_scene(self):
        c = self.canvas
        c.delete("all")
        self.draw_grid()
        if self.state != "playing":
            return
        if not self.beam:
            self.draw_preview()
        if self.level == 3:
            for t in self.targets:
                self.draw_ufo(t)
        elif self.target:
            self.draw_ufo(self.target)
        self.draw_beam()
        self.draw_cannon()

    def draw_grid(self):
        c = self.canvas
        for i in range(-11, 12):
            c.create_line(sx(i), 0, sx(i), H, fill="#cfe0f7")
            c.create_line(0, sy(i), W, sy(i), fill="#cfe0f7")
        # 軸
        c.create_line(0, CY, W, CY, fill="#333", width=2)
        c.create_line(CX, 0, CX, H, fill="#333", width=2)
        # 矢印
        c.create_polygon(W - 4, CY, W - 14, CY - 6, W - 14, CY + 6, fill="#333")
        c.create_polygon(CX, 4, CX - 6, 14, CX + 6, 14, fill="#333")
        # 数字（2きざみ）
        for i in range(-10, 11, 2):
            if i == 0:
                continue
            c.create_text(sx(i), CY + 13, text=str(i), font=(FONT, 9), fill="#666")
            c.create_text(CX + 6, sy(i), text=str(i), font=(FONT, 9),
                          fill="#666", anchor="w")
        c.create_text(W - 10, CY - 10, text="x", font=(FONT, 12, "bold"), fill="#555")
        c.create_text(CX + 12, 8, text="y", font=(FONT, 12, "bold"), fill="#555")

    def current_line(self):
        """いま選択中の直線 (a, b)。まだ選んでいないところは None"""
        if self.level == 1:
            return (self.sel_slope, 0)
        if self.level == 2:
            return (self.fixed_slope, self.sel_intercept)
        return (self.sel_a, self.sel_b)

    def draw_preview(self):
        a, b = self.current_line()
        if a is None or b is None:
            return
        a, b = float(a), float(b)
        self.canvas.create_line(sx(-11), sy(a * -11 + b), sx(11), sy(a * 11 + b),
                                fill=ACCENT[self.level], width=2, dash=(7, 6))
        if self.level >= 2:  # 切片の点を目立たせる
            r = 5
            self.canvas.create_oval(sx(0) - r, sy(b) - r, sx(0) + r, sy(b) + r,
                                    fill=ACCENT[self.level], outline="")

    def draw_cannon(self):
        a, b = self.current_line()
        a = float(a) if a is not None else 0.0
        b = float(b) if b is not None else 0.0
        ang = -math.atan(a)
        px, py = sx(0), sy(b)

        def rot_rect(x0, y0, x1, y1):
            pts = []
            for qx, qy in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
                rx = qx * math.cos(ang) - qy * math.sin(ang)
                ry = qx * math.sin(ang) + qy * math.cos(ang)
                pts += [px + rx, py + ry]
            return pts

        c = self.canvas
        c.create_polygon(rot_rect(12, -8, 28, 8), fill=MUZZLE[self.level], outline="")
        c.create_polygon(rot_rect(-16, -16, 16, 16), fill=BODYC[self.level], outline="")
        c.create_polygon(rot_rect(-11, -12, 11, -4), fill="white",
                         stipple="gray50", outline="")

    def draw_ufo(self, t):
        c = self.canvas
        px, py = sx(t["x"]), sy(t["y"])
        r = 0.5 * SCALE
        wing = "#2ecc71" if t["hit"] else "#a8324a"
        body = "#1a7a44" if t["hit"] else "#1a1a40"
        c.create_oval(px - r * 1.9, py - r * 0.45, px + r * 1.9, py + r * 0.45,
                      fill=wing, outline="")
        c.create_oval(px - r * 0.95, py - r * 0.85, px + r * 0.95, py + r * 0.85,
                      fill=body, outline="")
        c.create_oval(px - r * 0.5, py - r * 0.55, px, py - r * 0.15,
                      fill="white", stipple="gray50", outline="")
        c.create_text(px + r * 1.9 + 6, py - 4, text=f'({t["x"]}, {t["y"]})',
                      font=(FONT, 11, "bold"), fill="#333", anchor="w")

    def draw_beam(self):
        if not self.beam:
            return
        bm = self.beam
        x0, x1 = bm["x0"], bm["x"]
        y0, y1 = bm["a"] * x0 + bm["b"], bm["a"] * x1 + bm["b"]
        c = self.canvas
        c.create_line(sx(x0), sy(y0), sx(x1), sy(y1), fill="#ff7a3d", width=4)
        c.create_oval(sx(x1) - 8, sy(y1) - 8, sx(x1) + 8, sy(y1) + 8,
                      fill="#ffd54a", outline="")


# ===== ここからプログラムが始まる =====
if __name__ == "__main__":
    root = tk.Tk()
    game = Game(root)
    root.mainloop()
