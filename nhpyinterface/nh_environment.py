# -*- coding: utf-8 -*-
"""
Created on Fri Jan 19 15:30:17 2018

@author: dandrews

Top level library to abstract Nethack for bots that follows AIGym conventions
"""

from nh_interface import NhInterface
from nhstate import NhState
from collections import namedtuple
import numpy as np
import skimage.transform
import logging



Aspace = namedtuple("action_space", "n")

class NhEnv():
    """
    More or less replicate an AI Gym environment for connecting to a NN.
    """
    logger = logging.getLogger(__name__)
    action_space = Aspace(9)
    is_done = False
    _action_rating = 1
    strategies = {
            0: 'direct',
            1: 'explore'
            }

    # Model's expected image size
    output_shape = [84,84,3]
    last_turn = 0

    def __init__(self, username='aa'):
        if len(username) < 2:
            raise ValueError("Usernames are at least 2 characters")
        self.logger.info("starting user {}".format(username))
        self.nhi = NhInterface(username)
        self.actions = self.nhi.nhdata.get_commands(1)
        self.num_actions = len(self.actions)
        self.nhstate = NhState(self.nhi)
        self.nhi.start_session()
        self.nhi._clear_more()

    def __del__(self):
        if 'nhc' in dir(self):
            self.nhi.close()

    def reset(self):
        """
        Start a new game
        """
        self.logger.info("Reset " + self.nhi.username)
        self.nhi.reset_game()
        self.is_done = False
        self.nhi._clear_more()
        return self.data()


    def step_with_callback(self, callback):
        if self.is_done:
            self.reset()
        action, strategy = callback(self)
        s = self.data()
        h = self.auxiliary_features()
        s_, r, t, info = self.step(action,strategy)
        return s, action, r, s_, t, h


    def step(self, action: int, strategy: int = 0):
        assert type(action) == int
        assert type(strategy) == int
        self.nhi._clear_more()
        if self.is_done:
            raise ValueError("Simulation ended and must be reset")
        self.last_status = self.nhi.get_status()
        self.last_screen = self.nhi.buffer_to_rgb()

        start_turn = self.nhi.get_status()['t']

        if self.strategies[strategy] == 'explore':
           self._do_exploration_move(action)
        else:
            self._do_direct_action(action)

        self.is_done = self.nhstate.check_game_state()

        #s_, r, t, info
        s_, info = self.data(),  self.get_info()
        r = self.score_move()
        turn = self.nhi.get_status()['t']

        # turn no-ops like wall bumps into a "search" action
        if turn == start_turn:
            self._do_direct_action(5)
            turn = self.nhi.get_status()['t']
        self.logger.info("{} turn {}".format(self.nhi.username,turn))
        if int(turn) < 1 and not self.is_done:
            self.is_done = True

        t = self.is_done
        return s_, r, t, info

    def get_info(self):
        #info = self.data(), self.nhi.get_status()
        x_ = self.nhi.screen.cursor.x / self.nhi.screen.columns
        y_ = self.nhi.screen.cursor.y / self.nhi.screen.lines
        return [x_, y_]

    def score_move(self):
        #score = -1 # died/offset turn counter
        score = 0

        score_kills = False
        score_hp = False
        score_exploration = True
        score_status = False

        if not self.is_done:

            if self.nhi.is_killed_something and score_kills:
                score = 1

            if score_exploration:
                new_status = self.nhi.get_status()
                new_screen = self.nhi.buffer_to_rgb()
                screen_diff = self.last_screen - new_screen
                explore = len(screen_diff[screen_diff != 0])
                score += explore / 50.0 # Scale the score to be approx 0-1

            if score_status:
                for key in new_status:
                    if key in self.last_status.keys() and key is not 'hp':
                        if self.last_status[key] < new_status[key]:
                            score += 1 / len(new_status.keys())
                        if self.last_status[key] > new_status[key]:
                            score -= 1 / len(new_status.keys())

            if score_hp:
                hp = int(new_status['hp'])
                hp_max = int(new_status['hp_max'])
                hp_score = ((hp + 1e-10)/(hp_max + 1e-10)) - 1
                score += hp_score

        return score

    def auxiliary_features(self):
        return self.get_info()

    def _do_direct_action(self, action):
        if action >= self.num_actions:
            raise ValueError('No such action {}, limit is {}'.format(action, self.num_actions-1))
        if action not in self.nhi.nhdata.MOVE_COMMANDS:
            action = 10 # wait
        self.nhi.send_command(action)

    def _do_exploration_move(self, action):
        if action not in self.nhi.nhdata.MOVE_COMMANDS:
            # No op
            return
        else:
           self.nhi.send_string("G")
           self.nhi.send_string(str(action))

    def data(self):
        return self.resize_state(self.nhi.buffer_to_rgb())


    def resize_state(self, state):
        newsize = np.array(self.output_shape) # imresize prefers np.ndarray
        a = skimage.transform.resize(state, newsize, mode='constant', order=0)
        return a

    def close(self):
        self.nhi.close()


    def random_agent(self, reps=1):
        actions = np.arange(1,10)
        for _ in range(reps):
            action = np.random.choice(actions)
            s_, r, t, info = self.step(action, 0)
            if self.is_done:
                self.reset()


if __name__ == '__main__':

    log_format ='(%(threadName)-0s) %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s'
    logging.basicConfig(level=logging.WARNING, format=log_format)

    nhe = NhEnv()
    print("\n".join(nhe.nhi.screen.display))

#%%
    def test_step_function(env, num):
        callback = lambda x:(np.random.randint(10),0)
        if env.is_done:
            env.reset()

        for i in range(num):
            env.step_with_callback(callback)

    #%prun test_step_function(nhe, 100)


