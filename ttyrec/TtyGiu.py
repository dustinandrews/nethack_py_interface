# -*- coding: utf-8 -*-
"""
Created on Sun Apr 30 20:43:25 2017

@author: dandrews
"""
from tkinter import Tk, Text, INSERT, END, Button, N,S,E,W
import tkinter.font as tkFont
from TtyParse import TtyParse

class TtyRender:
    self.parser = None
    self.screen = None

    def __init__(self):
        self.fg = 'gray85'
        self.bg = 'black'
        self.tag = 0
        self.frame = 0
        self.parser = TtyParse(glob.glob('./*/*/*.ttyrec')[0])
        self.parser.get_metadata()
        self.parser.render_frames(0,0)
        width = self.parser.metadata.collumns
        height = self.parser.metadata.lines

        root = Tk()
        self.customFont = tkFont.Font(family="Lucida Console", size=12)
        self.text = Text(
                root, 
                font=self.customFont, 
                width=width, 
                height=height, 
                background=self.bg, 
                foreground=self.fg)
        self.text.grid(row=0, columnspan=5)
        self.text.insert(INSERT, self.get_description())     

        self.rewind_button = Button(text="<<", command=self.rewind).grid(row=1, column=0)

        self.previous_fame_button = Button(text="<", command=self.previous).grid(row=1, column=1, sticky=W+E)

        self.play_button = Button(text="|>", command=self.play).grid(row=1, column=2, sticky=W+E)

        self.next_frame = Button(text=">", command=self.next_frame).grid(row=1, column=3, sticky=W+E)

        self.fast_forward_button = Button(text=">>", command=self.fast_forward).grid(row=1, column=4)

        root.mainloop()
        
    def next_frame(self):
        self.parser.render_frames(self.frame, self.frame + 1 )
        self.frame += 1
        self.show_text()
        
    def previous(self):
        self.parser.render_frames(self.frame - 10, self.frame - 1 )
        self.frame -= 1
        self.show_text()
        
    def play(self):
        pass
    
    def rewind(self):
        if self.frame > 100:
            self.frame -= 100
            self.parser.render_frames(self.frame - 10, self.frame)
        else:
            self.frame = 1
            self.parser.render_frames(self.frame - 1, self.frame)
        self.show_text()
        
    def fast_forward(self):
        if self.frame + 100 < len(self.parser.metadata.frames):
            self.frame += 100
            self.parser.render_frames(self.frame - 100, self.frame)
        else:
            self.frame = len(self.parser.metadata.frames - 1)
            self.parser.render_frames(self.frame - 100, self.frame)
        self.show_text()
    
    
        
    
    def show_text(self):
        self.text.delete('1.0', END)
        for line in self.parser.screen.buffer:
            for c in line:
                if self.get_tag_from_char(c):
                    self.text.insert(INSERT, c.data, (str(self.tag)))
                else:
                    self.text.insert(INSERT, c.data)
            self.text.insert(INSERT, "\n")
        
    def get_tag_from_char(self, c):
        if c.fg != 'default' or c.bg !='default' or c.bold or c.italics or c.underscore or c.strikethrough or c.reverse:
            if c.fg == 'default':
                fg = self.fg
            else:
                fg = c.fg
            
            if c.bg == 'default':
                bg = self.bg
            else:
                bg = c.fg
            self.tag += 1
            if c.reverse:
                self.text.tag_config(str(self.tag), background=fg, foreground=bg, underline = c.underscore)
            else:
                self.text.tag_config(str(self.tag), background=bg, foreground=fg, underline = c.underscore)
            return True
        else:
            return False;

    def get_description(self):
        return "Filename: {}\n   Start: {}\n     End: {}\nDuration: {}\n Frame count: {}".format(
          self.parser.rec_filename,  
          self.parser.metadata.start_time,
          self.parser.metadata.end_time,
          self.parser.metadata.duration,
          len(self.parser.metadata.frames))

if __name__ == "__main__":
    tr = TtyRender()