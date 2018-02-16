# -*- coding: utf-8 -*-
"""
Created on Fri Jan 19 15:30:17 2018

@author: dandrews

Top level library to abstract Nethack for bots that follows AIGym conventions
"""

from nh_interface import NhClient
from nhstate import NhState
from collections import namedtuple
import numpy as np
import skimage.transform

Aspace = namedtuple("action_space", "n")

class NhEnv():
    """
    More or less replicate an AI Gym environment for connecting to a NN.
    """
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

    DEBUG_PRINT = False

    def __init__(self, username='aa'):
        self.nhc = NhClient(username)
        self.actions = self.nhc.nhdata.get_commands(1)
        self.num_actions = len(self.actions)
        self.nhstate = NhState(self.nhc)
        self.nhc.send_string('\n')
        self.nhc.start_session()
        self.nhc._clear_more()

    def __del__(self):
        self.nhc.close()

    def reset(self):
        """
        Start a new game
        """
        self.nhc.reset_game()
        self.is_done = False
        self.nhc._clear_more()
        return self.data()


    def step(self, action: int, strategy: int = 0):
        self.nhc._clear_more()
        if self.is_done:
            raise ValueError("Simulation ended and must be reset")
        last_status = self.nhc.get_status()
        last_screen = self.data()
        if self.strategies[strategy] == 'explore':
           self._do_exploration_move(action)
        else:
            self._do_direct_action(action)

        self.is_done = self.nhstate.check_game_state()

        #s_, r, t, info
        s_, info = self.data(), self.nhc.get_status()
        r = self.score_move(last_status, last_screen)

        turn = info['t']

        if self.DEBUG_PRINT:
            print(turn, end=", ")
        if int(turn) < 1 and not self.is_done:
            self.is_done = True

        t = self.is_done
        return s_, r, t, info

    def score_move(self, last_status, last_screen):
        new_status = self.nhc.get_status()
        new_screen = self.data()
        screen_diff = last_screen - new_screen
        explore = len(screen_diff[screen_diff != 0])
        score = explore - 1 # Offset score turn and punish no-ops like wall bumps
        for key in new_status:
            if key in last_status.keys():
                if last_status[key] < new_status[key]:
                    score += 1
        return score

    def auxiliary_features(self):
        return np.array(list(self.nhc.get_status().values()), dtype=np.float32)

    def _do_direct_action(self, action):
        if action >= self.num_actions:
            raise ValueError('No such action {}, limit is {}'.format(action, self.num_actions-1))
        if action not in self.nhc.nhdata.MOVE_COMMANDS:
            action = 10 # wait
        self.nhc.send_command(action)

    def _do_exploration_move(self, action):
        if action not in self.nhc.nhdata.MOVE_COMMANDS:
            # No op
            return
        else:
           self.nhc.send_string("G")
           self.nhc.send_string(str(action))

    def data(self):
        return self.resize_state(self.nhc.buffer_to_rgb())


    def resize_state(self, state):
        newsize = np.array(self.output_shape) # imresize prefers np.ndarray
        a = skimage.transform.resize(state, newsize, mode='constant', order=0)
        return a

    def close(self):
        self.nhc.close()


    def random_agent(self, reps=1):
        actions = np.arange(1,10)
        for _ in range(reps):
            action = np.random.choice(actions)
            s_, r, t, info = self.step(action, 0)

            if reps % 100 == 0:
                print("{}: {}".format(_, self.nhc.username))

            if self.is_done:
                self.reset()


if __name__ == '__main__':


    #nhe = NhEnv()
    #print("\n".join(nhe.nhc.screen.display))


#%%

    #random_agent(nhe)

#%%
    import time
    def multi_random_agent(env_array, reps = 1000):
        start = time.monotonic()
        actions = np.arange(1,10)
        for i in range(reps):
            if i % 100 == 0:
                print(i)
            for e in env_array:
                if not e.is_done:
                    strategy = np.random.choice([0,1])
                    action = np.random.choice(actions)
                    s_, r, t, info = e.step(action, strategy)
        end = time.monotonic()
        return i, end-start

#%%
    import logging
    import threading

    logging.basicConfig(level=logging.DEBUG, format='(%(threadname)-10s) %(message)s')
#%%
    def worker(env):
        try:
            env.random_agent(1)
        except:
            pass
        finally:
            return


#%%
    def create_worker(envs, num, name):
        e = NhEnv(name)
        e.reset()
        envs[num] = e
        print("done")
#%%
    def create_envs(num):
        offset = ord('b')
        envs = [None for _ in range(num)]
        for i in range(num):
            name = chr(i+offset) * 2
            print(name)
            t = threading.Thread(target=create_worker, args=(envs, i, name), name=name)
            t.start()
        for t in threading.enumerate():
            if t.name is name:
                t.join(30)
        return envs

#%%
    def threading_test(envs, index):
        sub_index = 0
        prefix = "env"
        for e in envs:
            t = threading.Thread(target=worker, args=(e,),
                                 name=prefix + "-" + str(index) + "-" +str(sub_index))
            t.start()
            sub_index += 1
        for t in threading.enumerate():
            if prefix in t.name:
                print("joining " + t.name)
                t.join(15)

#%%
    def multi_threaded_agents(envs):
        for i in range(1000):
            threading_test(envs, i)
            for e in envs:
                print("{} {}".format(e.nhc.username,e.nhc.get_status()['t'] ), end=", ")
            print()


#%%
    #envs = create_envs(1)

#%%
    #for e in envs:
    #    print("{} {}".format(e.nhc.username,e.nhc.get_status()['t'] ), end=", ")

#%%
    #multi_threaded_agents(envs)
