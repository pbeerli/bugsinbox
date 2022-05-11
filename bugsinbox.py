#!/usr/bin/env python
# ----------------------------------------------------------------------------
# bugs in a box eating each other mimicking a coalescent sequence
# call with 1 argument the number of bugs in the box
# Peter Beerli (c) 2011-2020
# based on a the noisy.py demo in pyglet.
#
# pyglet
# Copyright (c) 2006-2008 Alex Holkner
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of pyglet nor the names of its
#    contributors may be used to endorse or promote products
#    derived from this software without specific prior written
#    permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
# ----------------------------------------------------------------------------
# modified by Peter Beerli 2011, 2012, 2013
# added funny ending by David Swofford 2013
# added python3 compatibility, Peter Beerli 2020

'''Bounces icon (bug) around a window and plays noises when other bugs are met, when bugs come near
    each other one get swallowed, in analogy to the Kingman n-coalescent process. The box on the screen
    is the equivalent of the effective population size.
    '''

import os
import random
import sys
#from scipy import *
from numpy import *

from pyglet.gl import *
import pyglet
from pyglet.window import key
import time

imagelist = ['king_beetle_transp.png', 'ladybug_transp.png', 'mexican_bean_beetle_transp.png','mouselemur.png']

#'tigerbeetle2.png']


BALL_IMAGE = imagelist[0]
#BALL_SOUND = 'ball.wav'
BALL_SOUND = 'bullet.wav'
#BALL_SOUND2 = 'song.wav'
MINDISTANCE= 100.0
HUGE = 9999.0
GROW = 100
SHRINK = -100
helper = False
masterscale = 0.2
elapsed = 0.0

# added by DLS July 2013
chasing = False
cycles_since_chasing = 0
cycles_to_chase = 10
chaseMode = False
procreateMode = False
didProcreate = False
#

if len(sys.argv) > 2:
    BALL_SOUND = sys.argv[2]

sound = pyglet.resource.media(BALL_SOUND, streaming=False)
#music = pyglet.resource.media(BALL_SOUND2)
myimage = BALL_IMAGE
#
# used to calculate the speed of the bugs
#
def rect(r, w, deg=0): # radian if deg=0; degree if deg=1
    from math import cos, sin, pi
    if deg:
        w = pi * w / 180.0
    return r * cos(w), r * sin(w)

##################################################
# Population class: draw rectangle (aka the box)
#
class Population():
    width = 1000
    height = 700
    x = 0
    y = 0
    start = False
    
    # init of box
    #
    def __init__(self,window):
        self.width = window.width-200
        self.height = window.height-200
        self.x = 100
        self.y = 100
        start = False
    
    # draw the box
    #
    def draw(self):
        draw_rect(self.x,self.y,self.width,self.height)
    
    # update the box
    #
    def update(self,growvalue):
        self.width = self.width + growvalue
        self.height = self.height + growvalue
        self.x = self.x - growvalue//2
        self.y = self.y - growvalue//2


##################################################
# Balls=Bugs definition of the bug sprite and size
#
class Ball(pyglet.sprite.Sprite):
    global didProcreate
    global myimage
    ball_image = pyglet.resource.image(myimage)
    #ball_image = pyglet.image.load(myimage)
    ball_image.anchor_x = ball_image.width/2
    ball_image.anchor_y = ball_image.width/2
    width = ball_image.width
    height = ball_image.height
    # create a bug
    #
    def __init__(self):
        radius = masterscale * (self.width + self.height)/4
        x0 = population.x + radius/2 
        y0 = population.y + radius/2 
        x = x0 + random.random() * (population.width - radius)
        y = y0 + random.random() * (population.height - radius)
        super(Ball, self).__init__(self.ball_image, x, y, batch=balls_batch)
        self.scale=masterscale
        self.dx,self.dy = rect(500.0,(random.uniform(-pi,pi)),0)
        self.diff = 0.0
        self.rotation = -math.degrees(math.atan2(random.random()-0.5 , random.random()-0.5))
    
    
    # update a bug
    #
    def update(self, dt):
        if population.start == True:
            radius = masterscale * (self.width + self.height)/4
            x0 = population.x + radius/2
            y0 = population.y + radius/2
            if self.x <= x0 or self.x >= (x0 + population.width - radius):
                self.dx *= -1.0
            if self.y <= y0 or self.y >= (y0 + population.height - radius):
                self.dy *= -1.0

            oldx = self.x
            oldy = self.y
            
            self.x += self.dx * dt
            self.y += self.dy * dt
            
            self.x = min(max(self.x, x0), x0 + population.width - radius ) #self.width)
            self.y = min(max(self.y, y0), y0 + population.height - radius ) #self.height)
            self.rotation = -math.degrees(math.atan2(oldy-self.y , oldx-self.x))
        return (self.x,self.y)
    
    
    # turn a bug for chasing
    # DLS
    def turn(self, minAngle, maxAngle):
        oldx = self.x
        oldy = self.y
        if minAngle != maxAngle:
            angle = random.uniform(minAngle, maxAngle)
        else:
            angle = minAngle
        self.dx,self.dy = rect(500.0, angle,0)
        self.diff = 0.0
        self.rotation = -math.degrees(math.atan2(random.random()-0.5 , random.random()-0.5))

    def changebug(self):
        global myimage
        self.image = pyglet.image.load(myimage)
        self.ball_image.anchor_x = self.ball_image.width/2
        self.ball_image.anchor_y = self.ball_image.width/2
        self.width = self.ball_image.width
        self.height = self.ball_image.height

    def setscale(self,masterscale):
        #self.ball_image.anchor_x = self.ball_image.width/2
        #self.ball_image.anchor_y = self.ball_image.width/2
        #self.width = self.ball_image.width
        #self.height = self.ball_image.height
        self.scale = masterscale

#

# define the windows size, if you want to have a regular window then
# uncomment the next line and comment out the other one
#window = pyglet.window.Window(800, 600)
window = pyglet.window.Window(fullscreen=True)
population = Population(window)

#
#  Display the menu
#
def displayhelp():
    te  = "H         display/undisplay this help\n"
    te += "Enter     start animation\n"
    te += "R         restart animation\n"
    te += "Escape    quit application\n"
    te += "Space     increase box size\n"
    te += "Backspace decrease box size\n"
    te += "S         reduce the size of bugs\n"
    te += "I         increase the size of bugs\n"
    te += "A         add bugs\n"
    te += "D         delete bugs\n"
    te += "--------------------------------------\n"
    te += "Z         cute mode\n"
    te += "C         chase mode\n"
    te += "P         procreate mode\n\n\n"
    te += "Bugs in a Box was created by Peter Beerli (beerli@fsu.edu) in Summer 2011\n"
    te += "Improved 2013 by Dave Swofford (chase and procreate mode)\n"
    te += "further improvement 2015 and adapted to python3 2020 \n"
    te += "by Peter Beerli (new pictures, cute mode)\n"
    te += "based on the noisy example in the package pyglet\n"
    te += "and using py2applet to create an application\n"
    helplabel.text=te

#
# on any window event (mouse or key press run this function)
#
@window.event
def on_key_press(symbol, modifiers):
    global myimage
    global imagelist
    global starttime
    global helper
    global chaseMode      #DLS
    global procreateMode  #DLS
    #
    if symbol == key.H:
        if not(helper):
            helper=True
            displayhelp()
        else:
            helper=False
            helplabel.text=""
    elif symbol == key.SPACE:
        population.update(GROW)
    elif symbol == key.BACKSPACE:
        population.update(SHRINK)
    elif symbol == key.S:
        masterscale = balls[0].scale * 0.9
        for i in balls:
            i.setscale(masterscale)
    elif symbol == key.I:
        masterscale = balls[0].scale * 1.1
        for i in balls:
            i.setscale(masterscale)
    elif symbol == key.A:
        balls.append(Ball())
    elif symbol == key.D:
        if balls:
            del balls[-1]
    elif symbol == key.ENTER:
        #        print population.start
        starttime = time.time()
        population.start = not(population.start)
    elif symbol == key.R:
        myimage = imagelist[random.randint(0,3)]
        if timescale:
            del timescale[:]
        if balls:
            del balls[:]
        if len(sys.argv) > 1:
            sample = sys.argv[1]
        else:
            sample = 100
        for i in range(0,int(sample)):
            bb = Ball()
            bb.changebug()
            balls.append(bb)
        label2.text = 'k='+str(sample)
        #label2.text = 'z='+str(myimage)
        label3.text = "Time:%6i\nLast:%6i" % (0,0)
        #helplabel.text = ""
        starttime = time.time()
        population.start = False
        chasing = False
        cycles_since_chasing = 0
        chaseMode = False
        procreateMode = False
        didProcreate = False
    elif symbol == key.Z:
        myimage = imagelist[3]
        if timescale:
            del timescale[:]
        if balls:
            del balls[:]
        if len(sys.argv) > 1:
            sample = sys.argv[1]
        else:
            sample = 100
        for i in range(0,int(sample)):
            bb = Ball()
            bb.changebug()
            balls.append(bb)
        label2.text = 'k='+str(sample)
        #label2.text = 'z='+str(myimage)
        label3.text = "Time:%6i\nLast:%6i" % (0,0)
        #helplabel.text = ""
        starttime = time.time()
        population.start = False
        chasing = False
        cycles_since_chasing = 0
        chaseMode = False
        procreateMode = False
        didProcreate = False
                    

    #DLS
    elif symbol == key.ESCAPE:
        window.has_exit = True
    elif symbol == key.C:
        chaseMode = not chaseMode
    elif symbol == key.P:
        procreateMode = not procreateMode
    elif symbol == key.Q:
        sound.play()
        pass
#

#
# on any event try to draw all bugs and labels
#
@window.event
def on_draw():
    window.clear()
    population.draw()
    balls_batch.draw()
    label.draw()
    label2.draw()
    label3.draw()
    helplabel.draw()
    draw_timeintervals()


#
# update the box and the bugs
#
def update(dt):
    global chasing
    global cycles_since_chasing
    global cycles_to_chase
    global chaseMode
    global procreateMode
    global didProcreate
    if population.start:
        tim = int(time.time() - starttime)
        label3.text = "Time:%6i\nLast:%6i" % (tim, int(elapsed))
        c=[]
        for ball in balls:
            c.append(ball.update(dt))
        if(len(c)>1):
            dd=distance(c)
            mindistance = balls[0].scale * (balls[0].width + balls[0].height)/4.0
            if not chaseMode and not procreateMode:
                id=coalesce(balls,dd,mindistance) #MINDISTANCE*balls[0].scale)
            else:#DLS
                mindistance = MINDISTANCE*balls[0].scale
                if len(balls) == 2:
                    if chasing:
                        cycles_since_chasing += 1
                        if cycles_since_chasing == cycles_to_chase:
                            chasing = False
                            balls[0].turn(-0.5*pi, 0.5*pi)
                    
                    if dd[0,1] < mindistance:
                        if procreateMode:
                            didProcreate = True
                            balls.append(Ball())
                            chasing = False
                            balls[2].scale = 0.4
                            balls[2].x = balls[0].x
                            balls[2].y = balls[0].y
                            #ball[0].dx = ball[0].dx/2.0
                            #ball[0].dy = ball[0].dy/2.0
                            #ball[1].dx = ball[1].dx/2.0
                            #ball[1].dy = ball[1].dy/2.0
                            c.append(balls[2].update(dt))
                            #c.append(ball)
                            dd=distance(c)
                            chasing = False
                            return
                        else:
                            balls[0].turn(-0.5*pi, 0.5*pi)
                            balls[1].x = balls[0].x
                            balls[1].y = balls[0].y
                            balls[1].dx = 0
                            balls[1].dy = 0
                            while dd[0,1] < 1.5*mindistance:
                                balls[0].update(dt)
                                dd[0,1] = dd[1,0] = dist(balls[0], balls[1])
                            
                            # begin chasing
                            chasing = True
                            cycles_since_chasing = 0
                            balls[1].rotation = balls[0].rotation
                            balls[1].dx = balls[0].dx
                            balls[1].dy = balls[0].dy
                            for ball in balls:
                                ball.dx = ball.dx * 2
                                ball.dy = ball.dy * 2
                            cycles_to_chase = random.randint(5, 25)
                if procreateMode and didProcreate:
                    id = -1
                else:
                    id=coalesce(balls,dd,mindistance)
            if id>= 0:
                del(balls[id])


# calculate distance between two bugs
# DLS:
#
def dist(a, b):
    d1 = a.x - b.x
    d2 = a.y - b.y
    return math.sqrt(d1*d1+d2*d2)
#

#
# calculate the distance between bugs
#
def distance(c):
    cc = array(c)
    x = cc[:,0]
    y = cc[:,1]
    d = array(zeros((len(x),len(x)), dtype=float))
    for i in range(0,len(x)):
        for j in range(i+1,len(x)):
            d1 = x[i] - x[j]
            d2 = y[i] - y[j]
            td = math.sqrt(d1*d1+d2*d2)
            d[i,j] = td
            d[j,i] = td
        d[i,i] = HUGE
    return d

#
# evaluate whether bugs should coalesce into one
#
def coalesce(sample,distance,mindistance):
    global starttime
    global timescale
    global elapsed
    x = argmin(distance, axis=None)
    dims = distance.shape
    idx = unravel_index(x, dims)
    if(distance[idx[0],idx[1]]<mindistance):
        #delete(sample,idx[1],0)
        sound.play()
        label2.text = "k: "+str(len(balls)-1)
        t = time.time()-starttime
        elapsed = int(t)
        label3.text = "Time:%6i\nLast:%6i" % (elapsed, elapsed)
        timescale.append(float(t))
        return idx[1]
    else:
        return -1
#
# basic routine to draw a rectangle for the timeintervals
#
def draw_rect(x, y, width, height):
    glBegin(GL_LINE_LOOP)
    #glBegin(GL_TRIANGLES)
    glColor4f(0.99, 0.3, 0.2, 1.0)
    glVertex2f(x, y)
    glVertex2f(x + width, y)
    glVertex2f(x + width, y + height)
    glVertex2f(x, y + height)
    glEnd()
    #glBegin(GL_TRIANGLES)
    #glColor4f(0.2, 0.3, 0.2, 1.0)
    #glVertex2f(x, y)
    #glColor4f(0.0, 0.0, 1.0, 1.0)
    #glVertex2f(x + width, y)
    #glColor4f(0.0, 0.0, 1.0, 1.0)
    #glVertex2f(x + width, y + height)
    #glVertex2f(x, y + height)
    #glEnd()

#
# draw the coaelscent time intervals (they are relative, the right line is always the last
# coalescence event
def draw_timeintervals():
    global timescale
    xs = window.width // 5
    xe = window.width - xs
    xwidth = xe - xs
    ys = window.height // 15
    y = window.height - ys
    s = array(timescale)
    barheight = ys // 2
    draw_rect(xs,y,xwidth,barheight)
    if len(s) > 0:
        sss = s[-1]
        ss =  sss * ones(len(s), float)
        timescale_adj = s / ss
        #        print ss,timescale_adj
        for i in timescale_adj:
            draw_rect(xs+i*xwidth, y, 1, barheight)

###############################################
# set up the speed of the update event
# and define things and finally run
# the application
#
pyglet.clock.schedule_interval(update, 1/30.)

balls_batch = pyglet.graphics.Batch()
balls = []
starttime = time.time()
timescale=[]


if len(sys.argv) > 1:
    for i in range(0,int(sys.argv[1])):
        balls.append(Ball())
else:
    for i in range(0,int(100)):
        balls.append(Ball())

label = pyglet.text.Label('Press H for the help menu',
                          font_size=12                     ,
                          x=window.width // 2, y=10,
                          anchor_x='center')
label2 = pyglet.text.Label("k: "+str(len(balls)),
                           font_size=12,
                           x=window.width - window.width // 8, y=window.height - window.height // 15,
                           anchor_x='center')
label3 = pyglet.text.Label("Time: "+str(0),
                           font_size=12,multiline=True,width=200,
                           x=window.width // 5, y=window.height - window.height // 20,
                           anchor_x='center')
helplabel = pyglet.text.Label("",
                              font_size=12,multiline=True,width=800,
                              x=window.width // 5, y=window.height - window.height // 5, 
                              anchor_x='left')

if __name__ == '__main__':
    pyglet.app.run()
