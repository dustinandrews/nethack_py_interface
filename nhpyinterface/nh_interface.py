# -*- coding: utf-8 -*-
"""
Created on Mon Jan  8 17:00:26 2018

@author: dandrews

With inspiration from the lmj nethack client https://github.com/lmjohns3/shrieker
"""
from pyte import Screen, ByteStream
import telnetlib
#from sprites import SpriteSheet
import numpy as np
import matplotlib.pyplot as plt
from nhdata import NhData
import collections
import os
import logging
import time



class Point:
    __slots__ = ['x', 'y']
    def __init__(self, x, y):
        self.x = x
        self.y = y

MapXY = collections.namedtuple('mapxy', 'x y')

class NhInterface:
    """
    Uses telnet to connect to Nethack and communicate on a basic level with
    it. Note to self: Do not put game logic here. This is a low level interface.
    """
    logger = logging.getLogger(__name__)
    game_address = 'localhost'
    game_port = 23
    cols = 80
    rows = 24
    encoding = 'ascii'
    SAVE_HISTORY = False
    history = []
    data_history = []
    command_history = []
    wb_message = b'welcome back to NetHack!'
    MAX_GLYPH = 1012
    map_x_y = MapXY(21,80)
    nhdata = NhData()
    monster_count = len(nhdata.monsters.monster_data)
    tn = None
    _more_prompt = b'ore--\x1b[27m\x1b[3z'
    is_always_yes_question = False
    is_always_no_question  = False
    is_killed              = False
    is_end                 = False
    is_stale               = False
    is_more                = False
    is_killed_something    = False
    is_special_prompt      = False
    is_game_screen         = False
    is_blank               = False
    is_count               = False
    is_dgamelaunch         = False
    is_dg_logged_in        = False
    is_fainted             = False
    is_call_prompt         = False

    _special_prompts = ['end', 'more', 'always_yes_question',
                        'always_no_question', 'count',
                        'call_prompt', 'throw_prompt',
                        'entry_problem'
                        ]


    _states = {
        'always_yes_question': ['Force its termination? [yn]', 'Really save?',],
        'always_no_question':['who are you?', 'Still climb?' , 're you sure?', 'Really quit?', 'Really attack'],
        'killed':['killed by', 'Voluntary challenges'],
        'end':['(end)'],
        'stale':['stale'],
        'more':['--More--'],
        'killed_something':['You kill'],
        'dgamelaunch':['dgamelaunch'],
        'count':['Count: '],
        'dg_logged_in':['Logged in as'],
        'game_screen':['Dlvl:'],
        'fainted':['Fainted'],
        'call_prompt':['Call a'],
        'throw_prompt':['What do you want to throw?'],
        'entry_problem':['There was a problem with your last entry.']
        }


    sprite_sheet_name = "sprite_sheets/chozo32.bmp"
    local_dir = os.path.abspath(os.path.dirname(__file__))
    sprite_sheet_name = os.path.join(local_dir, sprite_sheet_name)

    def __init__(self, username='aa'):
        self.username = username
        #self.sprite_sheet = SpriteSheet(self.sprite_sheet_name, 40, 30)
        self._init_screen()
        self.tn = self._connect_with_retry()

        # Create placeholder for return data that is often updated
        self.npdata = np.zeros((self.map_x_y.x, self.map_x_y.y), dtype=np.float32)

    def __del__(self):
         self.close()

    def start_session(self):
        self.logger.info('(re)start session ' + self.username)

        if not self.tn:
            self.logger.debug('connect session ' + self.username)
            self._connect_with_retry()

        self._clear_more()
        if not self.is_dgamelaunch:
            self.logger.debug('Not in dgamelaunch menu ' +  self.username)
            return
        prompt = b'=>'
        if not self.is_dg_logged_in or self.is_game_screen:
            self.logger.info('log in ' + self.username)
            self.tn.read_until(prompt,2)
            self.send_and_read_to_prompt(prompt, b'l')
            message = self.username.encode(self.encoding) + b'\n'
            self.send_and_read_to_prompt(prompt, message)
            self.send_and_read_to_prompt(prompt, message)
        self.send_and_read_to_prompt(prompt, b'p') # play
        self._clear_more()

        # Important not to send anything while stale processes are being killed
        # Ideally won't end up in this loop much outside of testing.
        while self.is_stale:
            self.logger.info("stale " + self.username)
            data = self.tn.read_until(b'seconds.', 1)
            self.byte_stream.feed(data)
            page = self.screen.display
            if self.SAVE_HISTORY:
                self.history.append(page)
            self._read_states()
        self.tn.read_until(self._more_prompt, 1)
        self._clear_more()

    def reset_game(self):
        self.logger.info('Resetting ' + self.username)

        if not self.tn:
            self._connect_with_retry()
            self._read_states()

        self._clear_more()
        if self.is_dgamelaunch:
                self.logger.debug("dgamelaunch " + self.username)


        t = self.nhdata.get_status(self.screen.display)['t']
        if self.is_game_screen and t != 1:
            self.send_and_read_to_prompt(b'[yes/no]?', b'#quit\n')
            self.send_and_read_to_prompt(b'(end)', b'yes\n')
            self._clear_more()

        self.start_session()


    def _clear_more(self):
        self._read_states()
        while self.is_end or self.is_more\
            or self.is_blank or self.is_call_prompt\
            or self.is_entry_problem:
            self.logger.debug('clearing prompts')
            self.send_and_read_to_prompt(self._more_prompt, b'\n')

    def render_glyphs(self):
        """
        Creates a three channel numpy array and copies the correct glyphs
        to the array.

        Compatible with png and matplotlib
        ex:
            png.from_array(img.tolist(), 'RGB').save('map.png')
        """
        screen = np.zeros((self.map_x_y.x*32,self.map_x_y.y*32,3))
        glyphs = self.buffer_to_npdata()
        for row in range(len(glyphs)):
            for col in range(len(glyphs[row])):
                    glyph  = glyphs[row,col]
                    tile = self.sprite_sheet.get_image_by_number(int(glyph))
                    screen[row*32:(row*32)+32,col*32:(col*32)+32,:] = tile
        return screen

    def send_and_read_to_prompt(self, prompt, message, timeout=2):
        if type(prompt) == str:
            prompt = prompt.encode('ascii')

        if type(message) == str:
            message = message.encode('ascii')

        if not self.tn:
            self.start_session()

        try:
            self.tn.write(message)
            data = self.tn.read_until(prompt, timeout)
            data += self.tn.read_very_eager()
            self.byte_stream.feed(data)
        except EOFError:
           self.logger.warning("Telnet connection lost")
           self.tn = None
           return b''
        if self.SAVE_HISTORY:
            self.data_history.append(data)
            self.command_history.append(message)
            self.history.append(self.screen.display)
            self.logger.debug(message)
            self.logger.debug("".join(self.screen.display))
        self._read_states()
        return data

    def close(self):
        if self.tn:
            if self.is_game_screen:
                self.send_string('S')
                self.send_string('y')
                self.send_string('\n')
            else:
                self.send_string('q')
            self.tn.close()
            self.tn = None
        return ("closed " + self.username)

    def _init_screen(self):
        self.byte_stream = ByteStream()
        self.screen = Screen(self.cols,self.rows)
        self.byte_stream = ByteStream()
        self.byte_stream.attach(self.screen)

    def buffer_to_npdata(self):
        self.npdata = np.vectorize(self.nhdata.collapse_glyph)(self.screen.glyph_map)

#        skiplines = 1
#        self.npdata *= 0
#        self.npdata += 829 # set default to solid rock
#        for line in range(skiplines,self.map_x_y.x+skiplines):
#            for row in range(self.map_x_y.y):
#                if self.screen.buffer[line] == {}:
#                    continue
#                glyph = self.screen.buffer[line][row].glyph
#                glyph = self.nhdata.collapse_glyph(glyph)
#                if not self.screen.buffer[line][row].data == ' ':
#                    self.npdata[line-skiplines,row] = glyph

        return self.npdata

    def buffer_to_rgb(self):
        npdata = self.buffer_to_npdata()
        min_m, max_m = self.nhdata.monsters.minkey, self.nhdata.monsters.maxkey
        min_o, max_o = self.nhdata.objects.minkey, self.nhdata.objects.maxkey
        min_r, max_r = self.nhdata.rooms.minkey, self.nhdata.rooms.maxkey
        r,b,g = npdata.copy().astype(np.float32), npdata.copy().astype(np.float32), npdata.copy().astype(np.float32)

        r = self._normalize_layer(r, min_m, max_m) # creatures
        b = self._normalize_layer(b, min_r, max_r) # room
        g = self._normalize_layer(g, min_o, max_o) # object

        rgb = np.zeros((r.shape + (3,)))
        rgb[:,:,0] = r
        rgb[:,:,1] = b
        rgb[:,:,2] = g

        # cursor axis are flipped v.s. image or I made more x,y mistakes
        if self.screen.cursor.y < self.map_x_y.x and self.screen.cursor.x < self.map_x_y.y:
            rgb[self.screen.cursor.y, self.screen.cursor.x, :] = 1 # highlight player.

        return rgb

    def _normalize_layer(self, data, min_val, max_val, skew=0.2):
        #backup = data.copy()
        data[data < min_val] = min_val
        data[data > max_val] = min_val
        data += -(min_val)
        data /= max_val

        if data.min() < 0:
            raise ValueError("dang")

        #skew data away from 0
        data *= 1.0 - skew
        data[data>0] += skew

        return data

    def _connect_with_retry(self):
        retries = 0
        limit = 3
        while retries < limit:
            try:
                self.logger.debug("Connection to {} retry {}".format(self.game_address, retries))
                self.tn = telnetlib.Telnet(self.game_address)
                data = self.tn.read_until(b'\x1b[19;3H=> ', 2)
                self.byte_stream.feed(data)
                return
            except ConnectionRefusedError:
                retries += 1
                time.sleep(1 * retries )
        self.logger.warning("{} connection refused".format(self.username))
        raise ConnectionRefusedError


    def _read_states(self):
        if not self.tn:
            self.logger.warning("{} unexpectedly lost connection.".format(self.username))
            self.start_session()
        # TODO: is this ever not b''?
        data = self.tn.read_very_eager()
        self.byte_stream.feed(data)
        page = " ".join(self.screen.display)
        self.is_special_prompt = False
        for s in self._states:
            setattr(self, "is_" + s, False)
            for string in self._states[s]:
                if string in page:
                    setattr(self, "is_" + s, True)
                    for sp in self._special_prompts:
                        if sp in s:
                            self.is_special_prompt = True

        self.is_blank = True
        for c in page:
            if c != ' ':
                self.is_blank = False
                break
        if self.is_game_screen and self.screen.cursor.y == 0 and not self.is_special_prompt:
            raise ValueError("Unexpected prompt {}".format(self.screen.display[0]))




    def _get_states(self):
        states = {}
        for s in self._states:
            states[s] = getattr(self, "is_" + s)
        states['blank'] = self.is_blank
        return states

    def _create_login(self, login_name):
        prompt = b'=>'
        message = login_name
        self.send_and_read_to_prompt(prompt, 'r')
        self.send_and_read_to_prompt(b'', message)
        self.send_and_read_to_prompt(prompt,"\n")
        self.send_and_read_to_prompt(b'', message)
        self.send_and_read_to_prompt(prompt,"\n")
        self.send_and_read_to_prompt(b'', message)
        self.send_and_read_to_prompt(prompt, "\n")
        self.send_and_read_to_prompt(prompt, login_name + '@local.host\n')
        self.send_string("q")


    def imshow_map(self):
        img = self.render_glyphs()
        fig, ax = plt.subplots(figsize=(12,4))
        ax.axis('off')
        ax.imshow(img)
        plt.tight_layout()

    def get_visible_mobs(self):
        npdata = self.buffer_to_npdata()
        mobs = np.argwhere(npdata < self.monster_count)
        visible = []
        for mob in mobs:
            if not np.array_equal(mob, [self.cursor.x, self.cursor.y]):
                visible.append([mob, npdata[mob[0],mob[1]]])
        return visible

    def get_status(self):
        return self.nhdata.get_status(self.screen.display)

    def send_command(self, action_num):
        command = self.nhdata.COMMANDS[action_num]
        data = command.command
        self.send_and_read_to_prompt(b'\x1b[3z', data.encode('ascii'))

    def send_string(self, string):
        self.send_and_read_to_prompt(b'\x1b[3z', string)



if __name__ == '__main__':
    sampledata1 = b'\x1b[2;0z\x1b[2;1z\x1b[H\x1b[K\x1b[2;3z\x1b[2J\x1b[H\x1b[2;1z\x1b[2;3z\x1b[4;69H\x1b[0;832z-\x1b[1z\x1b[0;831z-\x1b[1z\x1b[0;831z-\x1b[1z\x1b[0;831z-\x1b[1z\x1b[0;831z-\x1b[1z\x1b[0;831z-\x1b[1z\x1b[0;831z-\x1b[1z\x1b[0;831z-\x1b[1z\x1b[0;833z-\x1b[1z\x1b[0m\x1b[5;69H\x1b[0;830z|\x1b[1z\x1b[0;848z\x1b[0m\x1b[1m\x1b[30m.\x1b[1z\x1b[0;16z\x1b[0m\x1b[1m\x1b[37m\x1b[7md\x1b[0m\x1b[0m\x1b[1z\x1b[0;848z\x1b[1m\x1b[30m.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;830z\x1b[0m|\x1b[1z\x1b[0m\x1b[6;69H\x1b[0;830z|\x1b[1z\x1b[0;45z\x1b[0m\x1b[1m\x1b[37mh\x1b[1z\x1b[0;848z\x1b[0m\x1b[1m\x1b[30m.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;830z\x1b[0m|\x1b[1z\x1b[0m\x1b[7;69H\x1b[0;844z\x1b[1m\x1b[31m+\x1b[1z\x1b[0;848z\x1b[0m\x1b[1m\x1b[30m.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;830z\x1b[0m|\x1b[1z\x1b[0m\x1b[8;69H\x1b[0;830z|\x1b[1z\x1b[0;848z\x1b[0m\x1b[1m\x1b[30m.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;830z\x1b[0m|\x1b[1z\x1b[0m\x1b[9;70H\x1b[0;848z\x1b[1m\x1b[30m.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;830z\x1b[0m|\x1b[1z\x1b[0m\x1b[10;69H\x1b[0;830z|\x1b[1z\x1b[0;848z\x1b[0m\x1b[1m\x1b[30m.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;848z.\x1b[1z\x1b[0;830z\x1b[0m|\x1b[1z\x1b[0m\x1b[11;69H\x1b[0;834z-\x1b[1z\x1b[0;831z-\x1b[1z\x1b[0;831z-\x1b[1z\x1b[0;831z-\x1b[1z\x1b[0;831z-\x1b[1z\x1b[0;831z-\x1b[1z\x1b[0;831z-\x1b[1z\x1b[0;831z-\x1b[1z\x1b[0;835z-\x1b[1z\x1b[0m\x1b[6;70H\x1b[2;2z\x1b[23;1H\x1b[K[\x1b[7m\x08\x1b[1m\x1b[32m\x1b[CAa the Stripling\x1b[0m\x1b[0m\x1b[0m\r\x1b[23;18H]          St:18/02 Dx:14 Co:16 In:8 Wi:9 Ch:8  Lawful S:0\r\x1b[24;1H'
    sampledata2 = b'Dlvl:1  $:0  HP:\x1b[K\r\x1b[1m\x1b[32m\x1b[24;17H18(18)\x1b[0m\r\x1b[24;23H Pw:\r\x1b[1m\x1b[32m\x1b[24;27H1(1)\x1b[0m\r\x1b[24;31H AC:6  Xp:1/0 T:1\x1b[2;1z\x1b[HVelkommen aa, the dwarven Valkyrie, welcome back to NetHack!\x1b[K\x1b[2;3z\x1b[6;70H\x1b[3z'
    sampledata = sampledata1 + sampledata2
#%%
    def smoke_test():
        nhi = NhInterface()
        nhi.start_session()
        rgb = nhi.buffer_to_rgb()
        plt.imshow(rgb)
        plt.show()
        nhi.send_string(".")
        rgb = nhi.buffer_to_rgb()
        plt.imshow(rgb)
        plt.show()
        return nhi

    nhi = smoke_test()

#%%

    def create_logins(prefix, start, num):
        log_format ='(%(threadName)-0s) %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s'
        logging.basicConfig(level=logging.INFO, format=log_format)
        import concurrent
        futures = []
        envs = []
        index = 0
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for i in range(num):
                name = "{}{:03}".format(prefix,i)
                f = executor.submit(NhInterface, name)
                futures.append(f)
            for future in concurrent.futures.as_completed(futures, 120):
                envs.append(future.result())

            for i in range(num):
                name = "{}{:03}".format(prefix,i+start)
                f = executor.submit(envs[i]._create_login, name)
            for future in concurrent.futures.as_completed(futures, 120):
                print('{}:{}'.format(index,name), end= ", ")
                index += 1


