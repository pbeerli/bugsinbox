#!/usr/bin/env python
# Bugs in a Box – Kingman n-coalescent visualizer
# Peter Beerli (c) 2011-2020, updated for pyglet 2.x

import os
import random
import sys
import time
import math

import numpy as np
import pyglet
from pyglet.window import key

# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------
mydir = os.path.dirname(os.path.abspath(__file__))
os.chdir(mydir)
pyglet.resource.path = [mydir]
pyglet.resource.reindex()

IMAGELIST = [
    'king_beetle_transp.png',
    'ladybug_transp.png',
    'mexican_bean_beetle_transp.png',
    'mouselemur.png',
]

BALL_SOUND = 'bullet.wav'
HUGE = 9999.0
BOX_COLOR = (252, 77, 51, 255)   # red-orange, RGBA 0-255

masterscale = 0.2   # will be multiplied by Retina scale after window creation
elapsed = 0.0
helper = False
current_image = IMAGELIST[0]

# ------------------------------------------------------------
# Window  (borderless at full screen dimensions — avoids the macOS/pyglet
#          "Canvas has not been attached" crash that fullscreen=True triggers
#          on Apple Silicon with pyglet 2.x)
# ------------------------------------------------------------
_screen = pyglet.display.get_display().get_default_screen()
# pyglet 2.x default dpi_scaling="real" treats width/height as physical pixels
# and divides by backingScaleFactor when sizing the NSWindow frame.  Passing
# logical screen dimensions produces a window 1/scale of the screen.  Multiply
# by the Retina scale factor (via screen.get_scale()) to get physical pixels so
# the NSWindow frame ends up exactly screen.width × screen.height logical points.
_scale = _screen.get_scale()
window = pyglet.window.Window(
    width=int(_screen.width * _scale),
    height=int(_screen.height * _scale),
    style=pyglet.window.Window.WINDOW_STYLE_BORDERLESS,
)
# Raise above the menu bar and dock (which sit at NSMainMenuWindowLevel = 24).
# NSStatusWindowLevel = 25 is pyglet's own constant for exactly this purpose.
from pyglet.libs.darwin.cocoapy.cocoalibs import NSStatusWindowLevel
window._nswindow.setLevel_(NSStatusWindowLevel)
window.set_location(_screen.x, _screen.y)
# Physical pixel space is _scale× larger in each dimension; scale all size-dependent
# constants so the simulation looks identical regardless of display DPI.
masterscale *= _scale
GROW   = int(100 * _scale)
SHRINK = -GROW
LINE_W = max(1, int(_scale))   # line width scales with DPI so lines stay visible

balls_batch = pyglet.graphics.Batch()

# ------------------------------------------------------------
# Population box
# ------------------------------------------------------------
class Population:
    def __init__(self, window):
        margin = 100 + GROW // 2          # start one step smaller than maximum
        self.width = window.width - 2 * margin
        self.height = window.height - 2 * margin
        self.x = margin
        self.y = margin
        self.start = False
        self._lines = [pyglet.shapes.Line(0, 0, 0, 0, thickness=LINE_W, color=BOX_COLOR) for _ in range(4)]
        self._sync()

    def _sync(self):
        x, y, w, h = self.x, self.y, self.width, self.height
        pts = [(x, y, x+w, y), (x+w, y, x+w, y+h), (x+w, y+h, x, y+h), (x, y+h, x, y)]
        for line, (x1, y1, x2, y2) in zip(self._lines, pts):
            line.x = x1; line.y = y1; line.x2 = x2; line.y2 = y2

    def draw(self):
        for line in self._lines:
            line.draw()

    def update(self, growvalue):
        self.width += growvalue
        self.height += growvalue
        self.x -= growvalue // 2
        self.y -= growvalue // 2
        self._sync()


population = Population(window)

# ------------------------------------------------------------
# Ball (bug sprite)
# ------------------------------------------------------------
class Ball(pyglet.sprite.Sprite):
    def __init__(self):
        img = pyglet.resource.image(current_image)
        img.anchor_x = img.width // 2
        img.anchor_y = img.height // 2

        radius = masterscale * (img.width + img.height) / 4
        x0 = population.x + radius / 2
        y0 = population.y + radius / 2
        x = x0 + random.random() * (population.width - radius)
        y = y0 + random.random() * (population.height - radius)

        super().__init__(img, x, y, batch=balls_batch)
        self.scale = masterscale
        angle = random.uniform(-math.pi, math.pi)
        self.dx = 500.0 * math.cos(angle)
        self.dy = 500.0 * math.sin(angle)
        self.rotation = -math.degrees(math.atan2(random.random() - 0.5, random.random() - 0.5))

    def update(self, dt):
        if not population.start:
            return (self.x, self.y)

        iw, ih = self.image.width, self.image.height
        radius = self.scale * (iw + ih) / 4
        x0 = population.x + radius / 2
        y0 = population.y + radius / 2
        xmax = x0 + population.width - radius
        ymax = y0 + population.height - radius

        if self.x <= x0 or self.x >= xmax:
            self.dx *= -1
        if self.y <= y0 or self.y >= ymax:
            self.dy *= -1

        oldx, oldy = self.x, self.y
        self.x = min(max(self.x + self.dx * dt, x0), xmax)
        self.y = min(max(self.y + self.dy * dt, y0), ymax)
        self.rotation = -math.degrees(math.atan2(oldy - self.y, oldx - self.x))
        return (self.x, self.y)

    def setscale(self, s):
        self.scale = s

# ------------------------------------------------------------
# Distance and coalescence
# ------------------------------------------------------------
def distance(c):
    cc = np.array(c)
    x, y = cc[:, 0], cc[:, 1]
    n = len(x)
    d = np.full((n, n), HUGE)
    for i in range(n):
        for j in range(i + 1, n):
            td = math.sqrt((x[i] - x[j]) ** 2 + (y[i] - y[j]) ** 2)
            d[i, j] = d[j, i] = td
    return d


def coalesce(dd, mindistance):
    global elapsed
    idx = np.unravel_index(np.argmin(dd), dd.shape)
    if dd[idx] < mindistance:
        sound.play()
        t = time.time() - starttime
        elapsed = int(t)
        label2.text = f"k: {len(balls) - 1}"
        label3.text = f"Time:{elapsed:6d}\nLast:{elapsed:6d}"
        timescale.append(float(t))
        return int(idx[1])
    return -1

# ------------------------------------------------------------
# Drawing helpers  (pyglet 2.x: use shapes, not glBegin/glEnd)
# ------------------------------------------------------------
def _draw_box_outline(x, y, w, h):
    pts = [(x, y, x+w, y), (x+w, y, x+w, y+h), (x+w, y+h, x, y+h), (x, y+h, x, y)]
    for x1, y1, x2, y2 in pts:
        pyglet.shapes.Line(x1, y1, x2, y2, thickness=LINE_W, color=BOX_COLOR).draw()


def draw_timeintervals():
    xs = window.width // 5
    xwidth = window.width - 2 * xs
    ys = window.height // 15
    y = window.height - ys
    barheight = ys // 2

    _draw_box_outline(xs, y, xwidth, barheight)

    if timescale:
        last = timescale[-1]
        for t in timescale:
            xpos = xs + int(t / last * xwidth)
            pyglet.shapes.Line(xpos, y, xpos, y + barheight, thickness=LINE_W, color=BOX_COLOR).draw()

# ------------------------------------------------------------
# Simulation update
# ------------------------------------------------------------
def update(dt):
    global elapsed
    if not population.start:
        return

    tim = int(time.time() - starttime)
    label3.text = f"Time:{tim:6d}\nLast:{int(elapsed):6d}"

    coords = [b.update(dt) for b in balls]
    if len(coords) > 1 and balls:
        dd = distance(coords)
        mindistance = balls[0].scale * (balls[0].image.width + balls[0].image.height) / 2.0
        idx = coalesce(dd, mindistance)
        if 0 <= idx < len(balls):
            balls[idx].delete()
            del balls[idx]

# ------------------------------------------------------------
# Events
# ------------------------------------------------------------
@window.event
def on_draw():
    window.clear()
    population.draw()
    balls_batch.draw()
    label.draw()
    label2.draw()
    label3.draw()
    if helper:
        helplabel.draw()
    draw_timeintervals()


def restart():
    global starttime, elapsed
    elapsed = 0.0
    timescale.clear()
    for b in balls:
        b.delete()
    balls.clear()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    for _ in range(n):
        balls.append(Ball())
    label2.text = f"k: {len(balls)}"
    label3.text = "Time:     0\nLast:     0"
    starttime = time.time()
    population.start = False


HELP_TEXT = (
    "H         show/hide help\n"
    "Enter     start / pause\n"
    "R         restart with random bug image\n"
    "Escape    quit\n"
    "Space     increase box size\n"
    "Backspace decrease box size\n"
    "S         shrink bugs\n"
    "I         grow bugs\n"
    "A         add a bug\n"
    "D         delete a bug\n"
    "Z         cute mode (mouselemur)\n"
    "Q         play sound\n\n"
    "Bugs in a Box – Peter Beerli (c) 2011-2020\n"
    "Updated for pyglet 2.x"
)


@window.event
def on_key_press(symbol, modifiers):
    global masterscale, helper, current_image, starttime

    if symbol == key.ESCAPE:
        pyglet.app.exit()
    elif symbol == key.ENTER:
        population.start = not population.start
        if population.start:
            starttime = time.time()
    elif symbol == key.R:
        current_image = IMAGELIST[random.randint(0, len(IMAGELIST) - 2)]
        restart()
    elif symbol == key.Z:
        current_image = IMAGELIST[3]   # mouselemur
        restart()
    elif symbol == key.H:
        helper = not helper
        helplabel.text = HELP_TEXT if helper else ""
    elif symbol == key.SPACE:
        population.update(GROW)
    elif symbol == key.BACKSPACE:
        population.update(SHRINK)
    elif symbol == key.S and balls:
        masterscale = balls[0].scale * 0.9
        for b in balls:
            b.setscale(masterscale)
    elif symbol == key.I and balls:
        masterscale = balls[0].scale * 1.1
        for b in balls:
            b.setscale(masterscale)
    elif symbol == key.A:
        balls.append(Ball())
        label2.text = f"k: {len(balls)}"
    elif symbol == key.D and balls:
        balls[-1].delete()
        del balls[-1]
        label2.text = f"k: {len(balls)}"
    elif symbol == key.Q:
        sound.play()

# ------------------------------------------------------------
# Initialise
# ------------------------------------------------------------
balls = []
starttime = time.time()
timescale = []

sound = pyglet.resource.media(BALL_SOUND, streaming=False)

sample = int(sys.argv[1]) if len(sys.argv) > 1 else 100
for _ in range(sample):
    balls.append(Ball())

_fs = int(12 * _scale)   # base font size scaled for physical pixel coordinate space

label = pyglet.text.Label(
    'Press H for help  |  Enter to start',
    font_size=_fs,
    x=window.width // 2, y=int(10 * _scale),
    anchor_x='center',
)
label2 = pyglet.text.Label(
    f"k: {len(balls)}",
    font_size=_fs,
    x=window.width - window.width // 8,
    y=window.height - window.height // 15,
    anchor_x='center',
)
label3 = pyglet.text.Label(
    "Time:     0\nLast:     0",
    font_size=_fs,
    multiline=True,
    width=int(200 * _scale),
    x=window.width // 5,
    y=window.height - window.height // 20,
    anchor_x='center',
)
helplabel = pyglet.text.Label(
    "",
    font_size=_fs,
    multiline=True,
    width=int(800 * _scale),
    x=window.width // 5,
    y=window.height - window.height // 5,
    anchor_x='left',
)

pyglet.clock.schedule_interval(update, 1 / 60.0)

if __name__ == '__main__':
    pyglet.app.run()
