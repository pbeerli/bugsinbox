import pyglet
# import all of opengl functions
from pyglet.gl import *
import pyglet.gl as gl

win = pyglet.window.Window()

@win.event
def on_draw():
    # create a line context
    gl.glBegin(GL_LINES)
    # create a line, x,y,z
    glVertex3f(100.0,100.0,0.25)
    glVertex3f(200.0,300.0,-0.75)
    glEnd()

pyglet.app.run()
