# ============================================================
# 一次関数ゲーム（Python / Pygame 版）
# ------------------------------------------------------------
# 実行方法:
#   「一次関数ゲームPygame起動.command」をダブルクリック
#   または ターミナルで  python3 一次関数ゲーム_pygame.py
#
# ・Pygameは「毎秒60回、画面全体を描き直す」本格的なゲームの作り方です。
# ・async / await の形で書いてあるので、あとで pygbag という道具を使うと
#   ほぼこのままブラウザ（Web）でも動かせます。
# ・効果音とBGMは、その場で波形を計算して作っています（音声ファイル不要）。
# ============================================================

import asyncio
import array
import math
import random
import pygame
from fractions import Fraction

# ===== 画面まわりの定数 =====
WIN_W, WIN_H = 812, 584
GX, GY = 16, 88            # グラフ領域の左上
GRID_SIZE = 480
SCALE = 22                 # 1マス = 22ピクセル → -10〜10 が入る
OX, OY = GX + 240, GY + 240  # 原点の位置
PX, PY, PW, PH = 512, 88, 284, 480  # 右パネル

TOTAL = 10
HIT_DIST = 0.45

# ===== 色（RGB）=====
BG      = (26, 26, 46)
PANEL   = (22, 33, 62)
BOX     = (15, 52, 96)
CARD    = (15, 26, 51)
WHITE   = (255, 255, 255)
LIGHT   = (224, 224, 255)
GRAY    = (150, 150, 170)
DGRAY   = (85, 85, 95)
GOLD    = (255, 215, 0)
ORANGE  = (255, 184, 77)
GREEN   = (46, 204, 113)
RED     = (231, 76, 60)
GRID_C  = (207, 224, 247)
AXIS_C  = (51, 51, 51)
PAPER   = (240, 246, 255)

ACCENT = {1: (108, 99, 255), 2: (255, 122, 61), 3: (46, 204, 113)}
MUZZLE = {1: (122, 95, 208), 2: (200, 90, 30), 3: (30, 143, 78)}
BODYC  = {1: (155, 126, 222), 2: (255, 154, 86), 3: (46, 204, 113)}

# ===== 問題に使う数 =====
INT_SLOPES  = [-4, -3, -2, -1, 1, 2, 3, 4]
FRAC_SLOPES = [Fraction(1, 2), Fraction(1, 3), Fraction(2, 3),
               Fraction(-1, 2), Fraction(-1, 3), Fraction(-2, 3)]
FIX_SLOPES  = [-2, -1, 1, 2]
FIX_FRAC    = [Fraction(1, 2), Fraction(1, 3), Fraction(2, 3), Fraction(-1, 2)]
INTERCEPTS  = list(range(-5, 6))
A_POOL      = [-3, -2, -1, 1, 2, 3]
B_POOL      = list(range(-5, 6))
LEVEL_NAMES = {1: "レベル1（かたむき）", 2: "レベル2（切片）", 3: "レベル3（2個同時）"}

# 日本語フォント（上から順に探して最初に見つかったものを使う）
FONT_PATHS = [
    "NotoSansJP-Regular.ttf",  # Web公開用に同じフォルダへ置いた場合
    "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
]


# 座標変換：グラフの座標 → 画面のピクセル
def sx(x): return OX + x * SCALE
def sy(y): return OY - y * SCALE


# ===== 効果音を波形計算で作る =====
RATE = 22050

def _to_sound(buf):
    try:
        return pygame.mixer.Sound(buffer=buf.tobytes())
    except pygame.error:
        return None

def load_or_make(path, maker):
    """soundsフォルダにWAVファイルがあれば読み込み、なければ計算で作る
    （Web版ではWAVを読む方が確実なため）"""
    try:
        return pygame.mixer.Sound(path)
    except (FileNotFoundError, pygame.error, OSError):
        return maker()

def make_sweep(f0, f1, dur, vol=0.2, kind="square"):
    """f0からf1へ音の高さが変わる音を作る"""
    n = int(RATE * dur)
    buf = array.array("h")
    ph = 0.0
    for i in range(n):
        f = f0 + (f1 - f0) * i / n
        ph += f / RATE
        if kind == "square":
            v = 1.0 if ph % 1 < 0.5 else -1.0
        else:
            v = math.sin(2 * math.pi * ph)
        env = 1 - i / n  # だんだん小さく
        buf.append(int(32767 * vol * env * v))
    return _to_sound(buf)

def make_explosion():
    """ノイズ＋低い音＝爆発音"""
    n = int(RATE * 0.35)
    buf = array.array("h")
    ph = 0.0
    for i in range(n):
        f = 130 + (45 - 130) * i / n
        ph += f / RATE
        v = 0.6 * math.sin(2 * math.pi * ph) + 0.55 * random.uniform(-1, 1)
        env = 1 - i / n
        s = int(32767 * 0.5 * env * v)
        buf.append(max(-32767, min(32767, s)))
    return _to_sound(buf)

def make_notes(notes, step, vol=0.2, kind="square"):
    """音符のリストをつなげて1つの音にする（0は休み）"""
    buf = array.array("h")
    for f in notes:
        n = int(RATE * step)
        ph = 0.0
        for i in range(n):
            if f == 0:
                buf.append(0)
                continue
            ph += f / RATE
            if kind == "square":
                v = 1.0 if ph % 1 < 0.5 else -1.0
            else:  # triangle（やわらかい音）
                v = 4 * abs(ph % 1 - 0.5) - 1
            env = min(1.0, (n - i) / (0.05 * RATE))  # 音の切れ目をなめらかに
            buf.append(int(32767 * vol * env * v))
    return _to_sound(buf)

BGM_NOTES = [523, 0, 659, 0, 784, 659, 523, 0, 587, 0, 494, 0, 392, 0, 440, 0,
             523, 0, 659, 0, 784, 880, 784, 0, 659, 0, 523, 0, 587, 0, 523, 0]


class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("一次関数ゲーム（Pygame版）")
        self.clock = pygame.time.Clock()
        self.running = True
        self._fonts = {}
        self.hotspots = []   # クリックできる場所のリスト（毎フレーム作り直す）

        # --- 効果音 ---
        self.sound_on = True
        self.snd_shoot = load_or_make("sounds/shoot.ogg",
                                      lambda: make_sweep(720, 220, 0.16, vol=0.18))
        self.snd_hit = load_or_make("sounds/hit.ogg", make_explosion)
        self.snd_miss = load_or_make("sounds/miss.ogg",
                                     lambda: make_sweep(300, 140, 0.28, vol=0.15))
        self.snd_end = load_or_make("sounds/end.ogg",
                                    lambda: make_notes([523, 659, 784, 1047], 0.15, vol=0.2))
        self.bgm = load_or_make("sounds/bgm.ogg",
                                lambda: make_notes(BGM_NOTES, 0.2, vol=0.10, kind="triangle"))
        self.bgm_playing = False

        # --- ゲームの状態 ---
        self.scene = "menu"        # menu / play / result
        self.sel_level = 1
        self.sel_time = 10
        self.level = 1
        self.problem_time = 10
        self.problem_index = 0
        self.score = 0
        self.timer_val = 10.0
        self.target = None
        self.targets = []
        self.beam = None
        self.shot_fired = False
        self.resolving = False
        self.resolve_at = 0        # 次の問題へ進む時刻（ミリ秒）
        self.msg = ""
        self.msg_color = WHITE
        # 選択中の答えと正解
        self.sel_slope = None
        self.sel_intercept = None
        self.sel_a = None
        self.sel_b = None
        self.correct_slope = None
        self.fixed_slope = None
        self.correct_intercept = 0
        self.correct_a = 0
        self.correct_b = 0
        self.choices = {}          # {"single": [...], "a": [...], "b": [...]}

    # ===== フォント =====
    def font(self, size):
        if size not in self._fonts:
            f = None
            for p in FONT_PATHS:
                try:
                    f = pygame.font.Font(p, size)
                    break
                except (FileNotFoundError, OSError, pygame.error):
                    continue
            if f is None:
                f = pygame.font.SysFont("hiraginosans", size)
            self._fonts[size] = f
        return self._fonts[size]

    def txt(self, s, size, color, pos, anchor="topleft"):
        img = self.font(size).render(s, True, color)
        r = img.get_rect(**{anchor: pos})
        self.screen.blit(img, r)
        return r

    # ===== 音 =====
    def play(self, snd):
        if self.sound_on and snd:
            snd.play()

    def start_bgm(self):
        if self.bgm and not self.bgm_playing:
            self.bgm.play(loops=-1)
            self.bgm_playing = True

    def stop_bgm(self):
        if self.bgm and self.bgm_playing:
            self.bgm.stop()
            self.bgm_playing = False

    def toggle_sound(self):
        self.sound_on = not self.sound_on
        if self.bgm:
            self.bgm.set_volume(1.0 if self.sound_on else 0.0)

    # ===== ボタン部品 =====
    def button(self, rect, label, size, bg, fg, cb, border=None, bw=2):
        pygame.draw.rect(self.screen, bg, rect, border_radius=9)
        if border:
            pygame.draw.rect(self.screen, border, rect, width=bw, border_radius=9)
        self.txt(label, size, fg, rect.center, anchor="center")
        if cb:
            self.hotspots.append((rect, cb))

    # ===== イベント処理 =====
    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for r, cb in self.hotspots:
                    if r.collidepoint(e.pos):
                        cb()
                        break

    # ===== ゲーム開始・メニュー =====
    def start_game(self):
        self.level = self.sel_level
        self.problem_time = self.sel_time
        self.scene = "play"
        self.problem_index = 0
        self.score = 0
        self.start_bgm()
        self.new_problem()

    def go_menu(self):
        self.scene = "menu"
        self.stop_bgm()

    # ===== 問題づくり =====
    def new_problem(self):
        self.resolving = False
        self.shot_fired = False
        self.beam = None
        self.timer_val = float(self.problem_time)
        self.sel_slope = self.sel_intercept = self.sel_a = self.sel_b = None
        self.msg = ""
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
            pool = FRAC_SLOPES if is_frac else INT_SLOPES
            self.choices = {"single": self.pick6(pool, self.correct_slope)}

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
            self.choices = {"single": self.pick6(INTERCEPTS, self.correct_intercept)}

        else:
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
            self.choices = {"a": self.pick6(A_POOL, self.correct_a),
                            "b": self.pick6(B_POOL, self.correct_b)}

    @staticmethod
    def pick6(pool, correct):
        others = [v for v in pool if v != correct]
        random.shuffle(others)
        result = [correct] + others[:5]
        random.shuffle(result)
        return result

    # ===== いま選んでいる直線 =====
    def current_line(self):
        if self.level == 1:
            return (self.sel_slope, 0)
        if self.level == 2:
            return (self.fixed_slope, self.sel_intercept)
        return (self.sel_a, self.sel_b)

    def can_shoot(self):
        a, b = self.current_line()
        return a is not None and b is not None and not self.shot_fired

    def answer_text(self):
        if self.level == 1:
            return f"a={self.correct_slope}"
        if self.level == 2:
            return f"b={self.correct_intercept}"
        return f"a={self.correct_a}, b={self.correct_b}"

    # ===== 発射 =====
    def shoot(self):
        if self.scene != "play" or not self.can_shoot():
            return
        a, b = self.current_line()
        a, b = float(a), float(b)
        if self.level == 3:
            self.beam = {"a": a, "b": b, "x": -9.0, "x0": -9.0, "dir": 1, "speed": 13.0}
        else:
            d = 1 if self.target["x"] >= 0 else -1
            self.beam = {"a": a, "b": b, "x": 0.0, "x0": 0.0, "dir": d, "speed": 10.0}
        self.shot_fired = True
        self.play(self.snd_shoot)

    def update_beam(self, dt):
        if not self.beam:
            return
        bm = self.beam
        remain = bm["speed"] * dt
        # 少しずつ進めて当たり判定が飛ばないようにする
        while remain > 0 and self.beam:
            step = min(0.15, remain)
            remain -= step
            bm["x"] += bm["dir"] * step
            y = bm["a"] * bm["x"] + bm["b"]

            if self.level == 3:
                for t in self.targets:
                    if not t["hit"] and math.hypot(bm["x"] - t["x"], y - t["y"]) < HIT_DIST:
                        t["hit"] = True
                if bm["x"] > 9:
                    self.beam = None
                    self.finish_lv3()
                continue

            t = self.target
            if math.hypot(bm["x"] - t["x"], y - t["y"]) < HIT_DIST:
                t["hit"] = True
                self.score += 10
                self.play(self.snd_hit)
                self.set_msg("◎ 命中！ +10点", GREEN)
                self.beam = None
                self.schedule_next(1000)
            elif abs(bm["x"]) > 11 or abs(y) > 11:
                self.play(self.snd_miss)
                self.set_msg(f"× ハズレ… 正解は {self.answer_text()}", RED)
                self.beam = None
                self.schedule_next(1200)

    def finish_lv3(self):
        hits = sum(1 for t in self.targets if t["hit"])
        self.score += hits * 5
        self.play(self.snd_hit if hits > 0 else self.snd_miss)
        if hits == 2:
            self.set_msg("◎ 2個命中！ +10点", GREEN)
        elif hits == 1:
            self.set_msg(f"△ 1個命中 +5点（正解 {self.answer_text()}）", ORANGE)
        else:
            self.set_msg(f"× ハズレ… 正解は {self.answer_text()}", RED)
        self.schedule_next(1300)

    def set_msg(self, text, color):
        self.msg = text
        self.msg_color = color

    def schedule_next(self, ms):
        if not self.resolving:
            self.resolving = True
            self.resolve_at = pygame.time.get_ticks() + ms

    # ===== 更新（毎フレーム）=====
    def update(self, dt):
        if self.scene != "play":
            return
        if self.resolving and pygame.time.get_ticks() >= self.resolve_at:
            self.problem_index += 1
            if self.problem_index >= TOTAL:
                self.scene = "result"
                self.stop_bgm()
                self.play(self.snd_end)
            else:
                self.new_problem()
            return
        if not self.shot_fired and not self.resolving:
            self.timer_val -= dt
            if self.timer_val <= 0:
                self.timer_val = 0
                self.shot_fired = True
                self.play(self.snd_miss)
                self.set_msg(f"時間切れ！ 正解は {self.answer_text()}", ORANGE)
                self.schedule_next(1200)
        self.update_beam(dt)

    # ===== 描画（毎フレーム）=====
    def draw(self):
        self.hotspots = []
        self.screen.fill(BG)
        if self.scene == "menu":
            self.draw_menu()
        elif self.scene == "play":
            self.draw_play()
        else:
            self.draw_result()

    # --- メニュー画面 ---
    def draw_menu(self):
        cxw = WIN_W // 2
        self.txt("一次関数ゲーム", 30, WHITE, (cxw, 62), anchor="center")
        self.txt("かたむきや切片を決めて、円盤を撃ち落とそう！", 15,
                 (184, 184, 224), (cxw, 104), anchor="center")

        self.txt("レベルをえらぶ", 13, GRAY, (cxw - 210, 132))
        descs = [
            ("レベル1（かたむき）", "かたむき a をあてる（y = ax）"),
            ("レベル2（切片）", "傾き固定・切片 b をあてる（y = ax + b）"),
            ("レベル3（2個同時）", "傾きと切片の両方・円盤2個を撃墜！"),
        ]
        for i, (name, desc) in enumerate(descs):
            lv = i + 1
            r = pygame.Rect(cxw - 210, 154 + i * 70, 420, 62)
            sel = (self.sel_level == lv)
            pygame.draw.rect(self.screen, CARD, r, border_radius=10)
            pygame.draw.rect(self.screen, GOLD if sel else (51, 51, 68), r,
                             width=2, border_radius=10)
            self.txt(name, 16, ACCENT[lv], (r.x + 16, r.y + 8))
            self.txt(desc, 12, (153, 153, 170), (r.x + 16, r.y + 35))
            self.hotspots.append((r, lambda lv=lv: setattr(self, "sel_level", lv)))

        self.txt("1問のタイムをえらぶ", 13, GRAY, (cxw - 210, 372))
        for i, (t, d) in enumerate([(10, "むずかしい"), (20, "ふつう"), (30, "やさしい")]):
            r = pygame.Rect(cxw - 210 + i * 144, 394, 132, 56)
            sel = (self.sel_time == t)
            pygame.draw.rect(self.screen, CARD, r, border_radius=10)
            pygame.draw.rect(self.screen, GOLD if sel else (51, 51, 68), r,
                             width=2, border_radius=10)
            self.txt(f"{t}秒", 17, WHITE, (r.centerx, r.y + 16), anchor="center")
            self.txt(d, 11, (153, 153, 170), (r.centerx, r.y + 40), anchor="center")
            self.hotspots.append((r, lambda t=t: setattr(self, "sel_time", t)))

        start = pygame.Rect(cxw - 210, 474, 420, 56)
        self.button(start, "ス タ ー ト", 19, ACCENT[1], WHITE, self.start_game)

        self.draw_sound_btn()

    def draw_sound_btn(self):
        r = pygame.Rect(WIN_W - 96, 16, 80, 32)
        label = "音:ON" if self.sound_on else "音:OFF"
        self.button(r, label, 13, PANEL, WHITE if self.sound_on else GRAY,
                    self.toggle_sound, border=(80, 80, 110), bw=1)

    # --- プレイ画面 ---
    def draw_play(self):
        ac = ACCENT[self.level]
        self.txt("一次関数ゲーム", 20, LIGHT, (GX, 24))
        self.txt(LEVEL_NAMES[self.level], 13, ac, (GX + 220, 32))
        self.draw_sound_btn()

        # グラフ領域
        pygame.draw.rect(self.screen, PAPER, (GX, GY, GRID_SIZE, GRID_SIZE))
        pygame.draw.rect(self.screen, ac, (GX - 3, GY - 3, GRID_SIZE + 6, GRID_SIZE + 6),
                         width=3, border_radius=4)
        self.draw_grid()
        if not self.beam:
            self.draw_preview()
        if self.level == 3:
            for t in self.targets:
                self.draw_ufo(t)
        elif self.target:
            self.draw_ufo(self.target)
        self.draw_beam()
        self.draw_cannon()

        # ---- 右パネル ----
        pygame.draw.rect(self.screen, PANEL, (PX, PY, PW, PH), border_radius=12)
        pygame.draw.rect(self.screen, ac, (PX, PY, PW, PH), width=2, border_radius=12)
        x, w = PX + 14, PW - 28
        y = PY + 12

        self.txt("この問題", 13, LIGHT, (x, y + 4))
        self.txt(str(math.ceil(max(self.timer_val, 0))), 22, ORANGE,
                 (x + w, y), anchor="topright")
        y += 34
        pygame.draw.rect(self.screen, (51, 51, 51), (x, y, w, 10), border_radius=5)
        frac = max(self.timer_val, 0) / self.problem_time
        if frac > 0:
            pygame.draw.rect(self.screen, ac, (x, y, int(w * frac), 10), border_radius=5)
        y += 20

        self.txt("問題", 13, LIGHT, (x, y))
        self.txt(f"{self.problem_index + 1} / {TOTAL}", 14, WHITE,
                 (x + w, y), anchor="topright")
        y += 24
        self.txt("得点", 13, LIGHT, (x, y + 2))
        self.txt(str(self.score), 22, ORANGE, (x + w, y - 4), anchor="topright")
        y += 30
        pygame.draw.line(self.screen, (51, 52, 68), (x, y), (x + w, y))
        y += 8

        # 傾き固定（Lv2）
        if self.level == 2:
            r = pygame.Rect(x, y, w, 28)
            pygame.draw.rect(self.screen, (58, 42, 26), r, border_radius=8)
            pygame.draw.rect(self.screen, ORANGE, r, width=2, border_radius=8)
            self.txt(f"傾き a = {self.fixed_slope}（固定）", 13, ORANGE,
                     r.center, anchor="center")
            y += 34

        # 式の表示
        r = pygame.Rect(x, y, w, 36)
        pygame.draw.rect(self.screen, BOX, r, border_radius=8)
        self.txt(self.formula_text(), 16, WHITE, r.center, anchor="center")
        y += 44

        # 選択肢
        if self.level == 3:
            self.txt("傾き a", 11, GRAY, (x, y)); y += 18
            y = self.draw_choices(x, y, w, "a", self.correct_a, self.sel_a,
                                  lambda v: setattr(self, "sel_a", v), 30)
            self.txt("切片 b", 11, GRAY, (x, y)); y += 18
            y = self.draw_choices(x, y, w, "b", self.correct_b, self.sel_b,
                                  lambda v: setattr(self, "sel_b", v), 30)
        elif self.level == 1:
            y = self.draw_choices(x, y, w, "single", self.correct_slope, self.sel_slope,
                                  lambda v: setattr(self, "sel_slope", v), 38)
        else:
            y = self.draw_choices(x, y, w, "single", self.correct_intercept,
                                  self.sel_intercept,
                                  lambda v: setattr(self, "sel_intercept", v), 38,
                                  prefix="b = ")

        # 発射ボタン
        y += 4
        r = pygame.Rect(x, y, w, 44)
        if self.can_shoot():
            self.button(r, "発 射 ！", 17, ac, WHITE, self.shoot)
        else:
            self.button(r, "発 射 ！", 17, DGRAY, (150, 150, 150), None)
        y += 52

        # メッセージ
        if self.msg:
            self.txt(self.msg, 13, self.msg_color, (x + w // 2, y + 8), anchor="center")

        # メニューに戻る
        r = pygame.Rect(x + w // 2 - 70, PY + PH - 30, 140, 22)
        self.txt("メニューに戻る", 11, (136, 136, 153), r.center, anchor="center")
        self.hotspots.append((r, self.go_menu))

    def formula_text(self):
        if self.level == 1:
            a = self.sel_slope if self.sel_slope is not None else "?"
            return f"y = {a} × x"
        if self.level == 2:
            b = self.sel_intercept
            a = self.fixed_slope
            if b is None:
                return f"y = {a}x + ?"
            if b == 0:
                return f"y = {a}x"
            return f"y = {a}x {'+' if b > 0 else '-'} {abs(b)}"
        a = self.sel_a if self.sel_a is not None else "?"
        b = self.sel_b
        bt = "+ ?" if b is None else (f"+ {b}" if b >= 0 else f"- {abs(b)}")
        return f"y = {a}x {bt}"

    def draw_choices(self, x, y, w, key, correct, selected, setter, bh, prefix=""):
        """6択ボタンを2行×3列で描く。クリック処理も登録する"""
        gap = 6
        bw_ = (w - gap * 2) // 3
        for i, v in enumerate(self.choices.get(key, [])):
            r = pygame.Rect(x + (i % 3) * (bw_ + gap), y + (i // 3) * (bh + gap), bw_, bh)
            if self.shot_fired:
                if v == correct:
                    bg, fg = (39, 174, 96), WHITE       # 正解は緑
                elif v == selected:
                    bg, fg = (192, 57, 43), WHITE       # まちがった選択は赤
                else:
                    bg, fg = BOX, (120, 130, 160)
                cb = None
            elif v == selected:
                bg, fg, cb = ACCENT[self.level], WHITE, None
            else:
                bg, fg = BOX, LIGHT
                cb = (lambda v=v: (setter(v)))
            pygame.draw.rect(self.screen, bg, r, border_radius=8)
            if v == selected and not self.shot_fired:
                pygame.draw.rect(self.screen, GOLD, r, width=2, border_radius=8)
            self.txt(prefix + str(v), 14, fg, r.center, anchor="center")
            if cb:
                self.hotspots.append((r, cb))
        return y + bh * 2 + gap + 8

    # --- グラフの描画 ---
    def draw_grid(self):
        clip = pygame.Rect(GX, GY, GRID_SIZE, GRID_SIZE)
        self.screen.set_clip(clip)
        for i in range(-10, 11):
            pygame.draw.line(self.screen, GRID_C, (sx(i), GY), (sx(i), GY + GRID_SIZE))
            pygame.draw.line(self.screen, GRID_C, (GX, sy(i)), (GX + GRID_SIZE, sy(i)))
        pygame.draw.line(self.screen, AXIS_C, (GX, OY), (GX + GRID_SIZE, OY), 2)
        pygame.draw.line(self.screen, AXIS_C, (OX, GY), (OX, GY + GRID_SIZE), 2)
        # 矢印
        gxr = GX + GRID_SIZE
        pygame.draw.polygon(self.screen, AXIS_C,
                            [(gxr - 4, OY), (gxr - 14, OY - 6), (gxr - 14, OY + 6)])
        pygame.draw.polygon(self.screen, AXIS_C,
                            [(OX, GY + 4), (OX - 6, GY + 14), (OX + 6, GY + 14)])
        # 数字（2きざみ）
        for i in range(-10, 11, 2):
            if i == 0:
                continue
            self.txt(str(i), 10, (102, 102, 102), (sx(i), OY + 12), anchor="center")
            self.txt(str(i), 10, (102, 102, 102), (OX + 6, sy(i)), anchor="midleft")
        self.txt("x", 13, (85, 85, 85), (gxr - 12, OY - 12), anchor="center")
        self.txt("y", 13, (85, 85, 85), (OX + 12, GY + 8), anchor="center")
        self.screen.set_clip(None)

    def dashed_line(self, p1, p2, color, width=2, dash=8, gap=6):
        x1, y1 = p1
        x2, y2 = p2
        length = math.hypot(x2 - x1, y2 - y1)
        if length == 0:
            return
        ux, uy = (x2 - x1) / length, (y2 - y1) / length
        d = 0
        while d < length:
            e = min(d + dash, length)
            pygame.draw.line(self.screen, color,
                             (x1 + ux * d, y1 + uy * d),
                             (x1 + ux * e, y1 + uy * e), width)
            d = e + gap

    def draw_preview(self):
        a, b = self.current_line()
        if a is None or b is None:
            return
        a, b = float(a), float(b)
        self.screen.set_clip(pygame.Rect(GX, GY, GRID_SIZE, GRID_SIZE))
        self.dashed_line((sx(-11), sy(a * -11 + b)), (sx(11), sy(a * 11 + b)),
                         ACCENT[self.level])
        if self.level >= 2:
            pygame.draw.circle(self.screen, ACCENT[self.level], (sx(0), sy(b)), 5)
        self.screen.set_clip(None)

    def draw_cannon(self):
        a, b = self.current_line()
        a = float(a) if a is not None else 0.0
        b = float(b) if b is not None else 0.0
        surf = pygame.Surface((80, 80), pygame.SRCALPHA)
        pygame.draw.rect(surf, MUZZLE[self.level], (52, 32, 16, 16), border_radius=3)
        pygame.draw.rect(surf, BODYC[self.level], (24, 24, 32, 32), border_radius=7)
        pygame.draw.rect(surf, (255, 255, 255, 70), (29, 28, 22, 8), border_radius=4)
        deg = math.degrees(math.atan(a))
        rot = pygame.transform.rotate(surf, deg)
        self.screen.set_clip(pygame.Rect(GX, GY, GRID_SIZE, GRID_SIZE))
        self.screen.blit(rot, rot.get_rect(center=(sx(0), sy(b))))
        self.screen.set_clip(None)

    def draw_ufo(self, t):
        px, py = sx(t["x"]), sy(t["y"])
        r = 0.5 * SCALE
        wing = GREEN if t["hit"] else (168, 50, 74)
        body = (26, 122, 68) if t["hit"] else (26, 26, 64)
        self.screen.set_clip(pygame.Rect(GX, GY, GRID_SIZE, GRID_SIZE))
        pygame.draw.ellipse(self.screen, wing,
                            (px - r * 1.9, py - r * 0.45, r * 3.8, r * 0.9))
        pygame.draw.ellipse(self.screen, body,
                            (px - r * 0.95, py - r * 0.85, r * 1.9, r * 1.7))
        pygame.draw.ellipse(self.screen, (120, 120, 170),
                            (px - r * 0.55, py - r * 0.6, r * 0.5, r * 0.35))
        self.txt(f'({t["x"]}, {t["y"]})', 11, (51, 51, 51),
                 (px + r * 1.9 + 5, py - 8), anchor="midleft")
        self.screen.set_clip(None)

    def draw_beam(self):
        if not self.beam:
            return
        bm = self.beam
        x0, x1 = bm["x0"], bm["x"]
        y0, y1 = bm["a"] * x0 + bm["b"], bm["a"] * x1 + bm["b"]
        self.screen.set_clip(pygame.Rect(GX, GY, GRID_SIZE, GRID_SIZE))
        pygame.draw.line(self.screen, (255, 122, 61),
                         (sx(x0), sy(y0)), (sx(x1), sy(y1)), 4)
        pygame.draw.circle(self.screen, (255, 213, 74), (sx(x1), sy(y1)), 8)
        self.screen.set_clip(None)

    # --- 結果画面 ---
    def draw_result(self):
        cxw = WIN_W // 2
        if self.score >= 100:
            rank = "パーフェクト！天才！"
        elif self.score >= 70:
            rank = "すばらしい！"
        elif self.score >= 40:
            rank = "よくできました！"
        else:
            rank = "もう一度チャレンジ！"
        self.txt("ゲーム終了！", 28, ORANGE, (cxw, 140), anchor="center")
        self.txt(f"{LEVEL_NAMES[self.level]} ・ 1問 {self.problem_time}秒", 14,
                 (184, 184, 224), (cxw, 186), anchor="center")
        self.txt(rank, 18, ORANGE, (cxw, 232), anchor="center")
        self.txt(f"{self.score} / 100点", 44, WHITE, (cxw, 300), anchor="center")

        r1 = pygame.Rect(cxw - 180, 370, 170, 52)
        self.button(r1, "もう一度", 16, ACCENT[1], WHITE, self.start_game)
        r2 = pygame.Rect(cxw + 10, 370, 170, 52)
        self.button(r2, "メニュー", 16, (68, 68, 85), WHITE, self.go_menu)
        self.draw_sound_btn()


# ===== メインループ（pygbagでWeb化するときもこの形のまま使える）=====
async def main():
    pygame.mixer.pre_init(RATE, -16, 1, 512)
    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass  # 音が出せない環境でもゲームは動かす
    game = Game()
    while game.running:
        dt = game.clock.tick(60) / 1000.0
        game.handle_events()
        game.update(dt)
        game.draw()
        pygame.display.flip()
        await asyncio.sleep(0)
    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
