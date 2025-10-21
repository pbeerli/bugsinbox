#!/usr/bin/env python3
# Bugs in a Box — pyglet ≥ 2.0, macOS-safe (no immediate-mode GL)
# All-in-one rewrite: robust fullscreen, resize-friendly, optimized UI (2025)
# MIT license
# (c) Peter Beerli 2025, October with help of chatgpt5
#
import os, random, sys, time, math
import numpy as np
import pyglet
from pyglet.window import key
from pyglet import shapes

# ---------------------------------------------------------------------
# Config / resources
BASEDIR = os.path.dirname(os.path.abspath(__file__))
IMG_FILES = [
    'king_beetle_transp.png',
    'ladybug_transp.png',
    'mexican_bean_beetle_transp.png',
    'mouselemur.png',
]
IMG_PATHS = [os.path.join(BASEDIR, f) for f in IMG_FILES]
SOUND_FILE = os.path.join(BASEDIR, (sys.argv[2] if len(sys.argv) > 2 else 'bullet.wav'))

# Simulation globals
HUGE = 9999.0
GROW, SHRINK = 100, -100
masterscale = 0.2
elapsed = 0.0
helper = False

# DLS modes
chasing = False
cycles_since_chasing = 0
cycles_to_chase = 10
chaseMode = False
procreateMode = False
didProcreate = False

# Motion tuning
BASE_SPEED = 500.0
def current_speed():
    # Scale base speed by box width so large windows feel similar
    return BASE_SPEED * (population.width / 1000.0 if 'population' in globals() else 1.0)

# ---------------------------------------------------------------------
# Window & batches
window = pyglet.window.Window(width=1280, height=800, resizable=True, visible=True)
try:
    window.set_vsync(False)  # optional: smoother on some Macs
except Exception:
    pass

ui_batch = pyglet.graphics.Batch()      # lines (box + time bar)
sprite_batch = pyglet.graphics.Batch()  # sprites or fallback circles
WHITE = (255, 255, 255, 255)

# Non-black background (core GL safe)
try:
    from pyglet import gl
    gl.glClearColor(0.05, 0.06, 0.09, 1.0)
except Exception:
    pass

# ---------------------------------------------------------------------
# Media loading with fallbacks
def load_image_safe(path):
    try:
        img = pyglet.image.load(path)
        img.anchor_x = img.width // 2
        img.anchor_y = img.height // 2
        return img
    except Exception as e:
        print(f"[warn] image load failed: {path} -> {e}")
        return None

IMAGES = [load_image_safe(p) for p in IMG_PATHS]
current_img_index = 0

def load_sound_safe(path):
    try:
        return pyglet.media.load(path, streaming=False)
    except Exception as e:
        print(f"[warn] sound load failed: {path} -> {e} (muted)")
        class _Null:
            def play(self): pass
        return _Null()
sound = load_sound_safe(SOUND_FILE)

# ---------------------------------------------------------------------
# Helpers
def rect(r, w, deg=0):
    from math import cos, sin, pi
    if deg: w = pi * w / 180.0
    return r * cos(w), r * sin(w)

# ---------------------------------------------------------------------
# Population (red box) drawn with shapes.Line
class Population:
    def __init__(self, window):
        self.x, self.y = 100, 100
        self.width  = max(200, window.width  - 200)
        self.height = max(200, window.height - 200)
        self.start = False

        self._edge_top    = shapes.Line(0,0,0,0, thickness=1, batch=ui_batch)
        self._edge_bottom = shapes.Line(0,0,0,0, thickness=1, batch=ui_batch)
        self._edge_left   = shapes.Line(0,0,0,0, thickness=1, batch=ui_batch)
        self._edge_right  = shapes.Line(0,0,0,0, thickness=1, batch=ui_batch)
        for ln in (self._edge_top, self._edge_bottom, self._edge_left, self._edge_right):
            ln.color = (252,77,51)
        self._sync_edges()

    def _sync_edges(self):
        x, y, w, h = self.x, self.y, self.width, self.height
        self._edge_bottom.x, self._edge_bottom.y, self._edge_bottom.x2, self._edge_bottom.y2 = x, y, x+w, y
        self._edge_top.x,    self._edge_top.y,    self._edge_top.x2,    self._edge_top.y2    = x, y+h, x+w, y+h
        self._edge_left.x,   self._edge_left.y,   self._edge_left.x2,   self._edge_left.y2   = x, y, x, y+h
        self._edge_right.x,  self._edge_right.y,  self._edge_right.x2,  self._edge_right.y2  = x+w, y, x+w, y+h

    def update(self, growvalue):
        self.width  = max(100, self.width  + growvalue)
        self.height = max(100, self.height + growvalue)
        self.x -= growvalue // 2
        self.y -= growvalue // 2
        self._sync_edges()

population = Population(window)

# ---------------------------------------------------------------------
# Bug: sprite with PNG, or fallback circle if PNG missing
class Bug:
    def __init__(self, img):
        self.is_sprite = img is not None
        radius_pix = masterscale * ((img.width + img.height)/4 if img else 64)
        x0 = population.x + radius_pix/2
        y0 = population.y + radius_pix/2
        x = x0 + random.random() * max(1, (population.width  - radius_pix))
        y = y0 + random.random() * max(1, (population.height - radius_pix))

        if self.is_sprite:
            self.sprite = pyglet.sprite.Sprite(img, x, y, batch=sprite_batch)
            self.sprite.scale = masterscale
            self.width = img.width
            self.height= img.height
        else:
            r = int(max(4, radius_pix/2))
            self.circle = shapes.Circle(x, y, r, color=(200,220,255), batch=sprite_batch)
            self.width = self.height = 2*r

        self.dx, self.dy = rect(current_speed(), random.uniform(-math.pi, math.pi), 0)
        self.rotation = -math.degrees(math.atan2(random.random()-0.5, random.random()-0.5))

    @property
    def x(self): return self.sprite.x if self.is_sprite else self.circle.x
    @x.setter
    def x(self, v):
        if self.is_sprite: self.sprite.x = v
        else: self.circle.x = v
    @property
    def y(self): return self.sprite.y if self.is_sprite else self.circle.y
    @y.setter
    def y(self, v):
        if self.is_sprite: self.sprite.y = v
        else: self.circle.y = v

    def setscale(self, s):
        if self.is_sprite: self.sprite.scale = s
        else: self.circle.radius = max(2, int(s*(self.width+self.height)/8))

    def changebug(self, new_img):
        if new_img is None: return
        if self.is_sprite:
            self.sprite.image = new_img
        else:
            self.is_sprite = True
            self.sprite = pyglet.sprite.Sprite(new_img, self.x, self.y, batch=sprite_batch)
            self.circle.delete()
        new_img.anchor_x = new_img.width // 2
        new_img.anchor_y = new_img.height // 2
        self.width, self.height = new_img.width, new_img.height

    def turn(self, minAngle, maxAngle):
        angle = random.uniform(minAngle, maxAngle) if minAngle != maxAngle else minAngle
        self.dx, self.dy = rect(current_speed(), angle, 0)
        self.rotation = -math.degrees(math.atan2(random.random()-0.5, random.random()-0.5))

    def update(self, dt):
        if not population.start: return (self.x, self.y)
        radius = masterscale * (self.width + self.height)/4
        x0 = population.x + radius/2
        y0 = population.y + radius/2
        if self.x <= x0 or self.x >= (x0 + population.width - radius):  self.dx *= -1.0
        if self.y <= y0 or self.y >= (y0 + population.height - radius): self.dy *= -1.0
        oldx, oldy = self.x, self.y
        # clamp, then move, then clamp again
        self.x = min(max(self.x, x0), x0 + population.width  - radius)
        self.y = min(max(self.y, y0), y0 + population.height - radius)
        self.x += self.dx * dt
        self.y += self.dy * dt
        self.x = min(max(self.x, x0), x0 + population.width  - radius)
        self.y = min(max(self.y, y0), y0 + population.height - radius)
        if self.is_sprite:
            self.sprite.rotation = -math.degrees(math.atan2(oldy-self.y, oldx-self.x))
        return (self.x, self.y)

# ---------------------------------------------------------------------
# Labels
label   = pyglet.text.Label('Press H for help; F pseudo-fullscreen; ESC exit FS/quit',
                            font_size=12, color=WHITE,
                            x=window.width//2, y=10, anchor_x='center')
label2  = pyglet.text.Label("k: 0", font_size=12, color=WHITE,
                            x=window.width - window.width//8,
                            y=window.height - window.height//15,
                            anchor_x='center')
label3  = pyglet.text.Label("Time: 0", font_size=12, multiline=True, width=200, color=WHITE,
                            x=window.width//5, y=window.height - window.height//20, anchor_x='center')
helplabel = pyglet.text.Label("", font_size=12, multiline=True, width=800, color=WHITE,
                              x=window.width//5, y=window.height - window.height//5, anchor_x='left')

def displayhelp():
    te  = "H         display/undisplay this help\n"
    te += "Enter     start/stop animation\n"
    te += "R         restart animation\n"
    te += "Escape    quit (or exit pseudo-fullscreen first)\n"
    te += "Space     increase box size\n"
    te += "Backspace decrease box size\n"
    te += "S         reduce the size of bugs\n"
    te += "I         increase the size of bugs\n"
    te += "A         add bugs\n"
    te += "D         delete bugs\n"
    te += "--------------------------------------\n"
    te += "Z         cute mode (mouse lemur)\n"
    te += "C         chase mode\n"
    te += "P         procreate mode\n"
    return te

# ---------------------------------------------------------------------
# Time bar (optimized with dirty flag)
_time_tick_lines, _time_box_lines = [], []
timebar_dirty = True

def _clear_time_lines():
    for ln in _time_tick_lines: ln.delete()
    _time_tick_lines.clear()
    for ln in _time_box_lines: ln.delete()
    _time_box_lines.clear()

def draw_timeintervals():
    global timebar_dirty
    _clear_time_lines()
    xs = window.width // 5
    xe = window.width - xs
    xwidth = xe - xs
    ys = window.height // 15
    y = window.height - ys
    barheight = ys // 2
    _time_box_lines.extend([
        shapes.Line(xs, y, xe, y, thickness=1, batch=ui_batch),
        shapes.Line(xs, y+barheight, xe, y+barheight, thickness=1, batch=ui_batch),
        shapes.Line(xs, y, xs, y+barheight, thickness=1, batch=ui_batch),
        shapes.Line(xe, y, xe, y+barheight, thickness=1, batch=ui_batch),
    ])
    for ln in _time_box_lines: ln.color = (252,77,51)
    if timescale:
        s = np.array(timescale)
        last = s[-1]
        for i in (s/last):
            x_tick = xs + int(i * xwidth)
            tln = shapes.Line(x_tick, y, x_tick, y+barheight, thickness=1, batch=ui_batch)
            tln.color = (40,40,255)
            _time_tick_lines.append(tln)
    timebar_dirty = False

# ---------------------------------------------------------------------
# Pseudo-fullscreen helpers (Cocoa, full frame)
# --- PSEUDO-FULLSCREEN that uses Retina scale correctly (points -> pixels) ---

_fs_active = False
_win_geom  = {"x": 100, "y": 100, "w": window.width, "h": window.height}

def _remember_window_geom():
    try:
        x, y = window.get_location()
    except Exception:
        x, y = _win_geom["x"], _win_geom["y"]
    _win_geom.update({"x": x, "y": y, "w": window.width, "h": window.height})

def _get_full_screen_rect_pixels():
    """
    Return (x_px, y_px, w_px, h_px) for the PRIMARY screen in *pixels*.
    We read Cocoa frame (points) and multiply by backingScaleFactor.
    """
    try:
        from pyglet.libs.darwin.cocoapy import ObjCClass
        NSScreen = ObjCClass('NSScreen')
        main = NSScreen.mainScreen()
        fr = main.frame()                    # NSRect, in points
        scale = float(main.backingScaleFactor())
        x_px = int(fr.origin.x   * scale)
        y_px = int(fr.origin.y   * scale)
        w_px = int(fr.size.width * scale)
        h_px = int(fr.size.height* scale)
        return x_px, y_px, w_px, h_px
    except Exception:
        # Fallback: use current framebuffer as best guess
        try:
            fbw, fbh = window.get_framebuffer_size()
            return 0, 0, int(fbw), int(fbh)
        except Exception:
            return 0, 0, int(window.width), int(window.height)

def enter_pseudo_fullscreen():
    """Borderless, fills full screen in pixels (Retina-correct)."""
    global _fs_active
    if _fs_active:
        return
    _remember_window_geom()
    try: window.set_fullscreen(False)      # ensure not in native FS
    except Exception: pass
    try: window.set_style("borderless")    # hide title bar
    except Exception: pass

    x_px, y_px, w_px, h_px = _get_full_screen_rect_pixels()

    # IMPORTANT: set size/location in *pixels* on Retina
    window.set_size(w_px, h_px)
    try:
        window.set_location(x_px, y_px)
    except Exception:
        # Some backends ignore pixel coords for location; best-effort only
        pass

    _fs_active = True

def exit_pseudo_fullscreen():
    global _fs_active
    if not _fs_active:
        return
    try: window.set_style("default")
    except Exception: pass
    window.set_size(int(_win_geom["w"]), int(_win_geom["h"]))
    try: window.set_location(int(_win_geom["x"]), int(_win_geom["y"]))
    except Exception: pass
    _fs_active = False
# --- end Retina-correct pseudo-FS ---


# ---------------------------------------------------------------------
# Events
def _rescale_bugs(old_box, new_box):
    ox, oy, ow, oh = old_box
    nx, ny, nw, nh = new_box
    if ow <= 0 or oh <= 0:
        return
    for b in bugs + kids:
        rx = (b.x - ox) / ow
        ry = (b.y - oy) / oh
        b.x = nx + rx * nw
        b.y = ny + ry * nh

@window.event
def on_key_press(symbol, modifiers):
    global current_img_index, masterscale
    global chasing, cycles_since_chasing, chaseMode, procreateMode, didProcreate
    global timescale, starttime, helper, timebar_dirty

    if symbol == key.F:
        if _fs_active: exit_pseudo_fullscreen()
        else: enter_pseudo_fullscreen()
    elif symbol == key.ESCAPE:
        if _fs_active: exit_pseudo_fullscreen()
        else: window.close()
    elif symbol == key.H:
        helper = not helper
        helplabel.text = "" if not helper else displayhelp()
    elif symbol == key.SPACE:
        population.update(GROW); timebar_dirty = True
    elif symbol == key.BACKSPACE:
        population.update(SHRINK); timebar_dirty = True
    elif symbol == key.S:
        masterscale = (bugs[0].sprite.scale if (bugs and bugs[0].is_sprite) else masterscale) * 0.9
        for b in bugs: b.setscale(masterscale)
    elif symbol == key.I:
        masterscale = (bugs[0].sprite.scale if (bugs and bugs[0].is_sprite) else masterscale) * 1.1
        for b in bugs: b.setscale(masterscale)
    elif symbol == key.A:
        img = IMAGES[current_img_index]
        bugs.append(Bug(img))
        label2.text = 'k=' + str(len(bugs))
    elif symbol == key.D:
        if bugs:
            del bugs[-1]
            label2.text = 'k=' + str(len(bugs))
    elif symbol == key.ENTER:
        starttime = time.time()
        population.start = not population.start
    elif symbol == key.R:
        current_img_index = random.randint(0, len(IMAGES)-1)
        timescale.clear(); bugs.clear()
        sample = int(sys.argv[1]) if len(sys.argv) > 1 else 100
        for _ in range(sample):
            bugs.append(Bug(IMAGES[current_img_index]))
        label2.text = 'k=' + str(sample)
        label3.text = "Time:%6i\nLast:%6i" % (0,0)
        starttime = time.time()
        population.start = False
        chasing = False; cycles_since_chasing = 0
        chaseMode = procreateMode = didProcreate = False
        timebar_dirty = True
    elif symbol == key.Z:
        current_img_index = len(IMAGES)-1
        timescale.clear(); bugs.clear()
        sample = int(sys.argv[1]) if len(sys.argv) > 1 else 100
        for _ in range(sample):
            bugs.append(Bug(IMAGES[current_img_index]))
        label2.text = 'k=' + str(sample)
        label3.text = "Time:%6i\nLast:%6i" % (0,0)
        starttime = time.time()
        population.start = False
        chasing = False; cycles_since_chasing = 0
        chaseMode = procreateMode = didProcreate = False
        timebar_dirty = True
    elif symbol == key.C:
        chaseMode = not chaseMode
    elif symbol == key.P:
        procreateMode = not procreateMode
    elif symbol == key.Q:
        sound.play()

@window.event
def on_resize(width, height):
    global timebar_dirty
    old_box = (population.x, population.y, population.width, population.height)

    # center with 100px margins
    population.x = 100
    population.y = 100
    population.width  = max(200, width  - 200)
    population.height = max(200, height - 200)
    population._sync_edges()

    # rescale bug positions to preserve relative layout
    new_box = (population.x, population.y, population.width, population.height)
    _rescale_bugs(old_box, new_box)

    # labels
    label.x, label.y   = width // 2, 10
    label2.x, label2.y = width - width // 8, height - height // 15
    label3.x, label3.y = width // 5, height - height // 20
    helplabel.x, helplabel.y = width // 5, height - height // 5

    timebar_dirty = True

@window.event
def on_draw():
    window.clear()
    if timebar_dirty:
        draw_timeintervals()
    ui_batch.draw()
    sprite_batch.draw()
    label.draw(); label2.draw(); label3.draw(); helplabel.draw()

# ---------------------------------------------------------------------
# Distance / coalescence
def dist(a, b): return math.hypot(a.x - b.x, a.y - b.y)

def distance(coords):
    cc = np.array(coords); x = cc[:,0]; y = cc[:,1]
    n = len(x)
    d = np.zeros((n,n), dtype=float)
    for i in range(n):
        for j in range(i+1, n):
            td = math.hypot(x[i]-x[j], y[i]-y[j])
            d[i,j] = d[j,i] = td
        d[i,i] = HUGE
    return d

def coalesce(sample, distance_mat, mindistance):
    global starttime, timescale, elapsed, timebar_dirty
    x = np.argmin(distance_mat, axis=None)
    idx = np.unravel_index(x, distance_mat.shape)
    if distance_mat[idx[0], idx[1]] < mindistance:
        sound.play()
        label2.text = "k: " + str(len(bugs) - 1)
        t = time.time() - starttime
        elapsed = int(t)
        label3.text = "Time:%6i\nLast:%6i" % (elapsed, elapsed)
        timescale.append(float(t))
        timebar_dirty = True
        return idx[1]
    return -1

def update(dt):
    global chasing, cycles_since_chasing, cycles_to_chase, chaseMode, procreateMode, didProcreate
    if population.start:
        tim = int(time.time() - starttime)
        label3.text = "Time:%6i\nLast:%6i" % (tim, int(elapsed))
        coords = [b.update(dt) for b in bugs] + [k.update(dt) for k in kids]
        if len(coords) > 1 and bugs:
            dd = distance(coords)
            mindistance = masterscale * (bugs[0].width + bugs[0].height) / 2.0
            if not chaseMode and not procreateMode:
                idx = coalesce(bugs, dd, mindistance)
            else:
                if len(bugs) == 2:
                    if chasing:
                        cycles_since_chasing += 1
                        if cycles_since_chasing == cycles_to_chase:
                            chasing = False
                            bugs[0].turn(-0.5*math.pi, 0.5*math.pi)
                    if dd[0,1] < mindistance:
                        if procreateMode:
                            didProcreate = True
                            kid = Bug(IMAGES[current_img_index])
                            kids.append(kid)
                            chasing = False
                            kid.setscale(0.4*masterscale)
                            kid.x, kid.y = bugs[0].x, bugs[0].y
                            coords.append(kid.update(dt))
                            dd = distance(coords)
                            time.sleep(0.2)
                            return
                        else:
                            bugs[0].turn(-0.5*math.pi, 0.5*math.pi)
                            bugs[1].x, bugs[1].y = bugs[0].x, bugs[0].y
                            bugs[1].dx = bugs[1].dy = 0
                            while dd[0,1] < 1.5*mindistance:
                                bugs[0].update(dt)
                                dd[0,1] = dd[1,0] = dist(bugs[0], bugs[1])
                            chasing = True
                            cycles_since_chasing = 0
                            bugs[1].dx, bugs[1].dy = bugs[0].dx, bugs[0].dy
                            for b in bugs:
                                b.dx *= 2; b.dy *= 2
                            cycles_to_chase = random.randint(5,25)
                idx = -1 if (procreateMode and didProcreate) else coalesce(bugs, dd, mindistance)
            if idx >= 0:
                del bugs[idx]

# ---------------------------------------------------------------------
# Init
bugs, kids, timescale = [], [], []
starttime = time.time()
sample = int(sys.argv[1]) if len(sys.argv) > 1 else 100
for _ in range(sample):
    bugs.append(Bug(IMAGES[current_img_index]))
label2.text = "k: " + str(len(bugs))

# Build UI once
draw_timeintervals()

pyglet.clock.schedule_interval(update, 1/30.0)

if __name__ == '__main__':
    pyglet.app.run()
