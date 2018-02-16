# -*- coding: utf-8 -*-
"""
Created on Tue Feb  6 17:39:19 2018

@author: dandrews
"""

from nh_interface import NhClient
import pickle

class NhState:
    """
    Class to understand stuff about the game, like inventory and items.
    """
    DEBUG_PRINT = False
    progress_filename = "nh_progress.dat"

    def __init__(self, nhc : NhClient):
        self.nhc = nhc

    def check_game_state(self):
        """
        Examine the game state for interesting stuff and
        clear any prompts before returning.
        returns True if game over.
        """
        done = False
        safety = 0
        threshold = 10
        while not done and (self.nhc.is_special_prompt):
            if safety > threshold:
                attribs = dir(self.nhc)
                for at in [a for a in attribs if 'is_' in a]:
                    print('{}: {}'.format(at, getattr(self.nhc, at)))
                raise ValueError("Unexpectedly looping")

            if self.nhc.is_always_no_question:
                self.nhc.send_string('n\n')
            if self.nhc.is_killed or self.nhc.is_dgamelaunch:
                done = True
            self._parse_screen()
            if self.nhc.is_always_yes_question:
                self.nhc.send_string('y')
                self.nhc.send_string('\n')
            elif self.nhc.is_always_no_question:
                self.nhc.send_string('n')
                self.nhc.send_string('\n')
            else:
                self.nhc.send_string('\n')
            self._save_progress()

            # When fainted there can be a lot of messages to clear.
            if not self.nhc.is_fainted:
                safety += 1

        return done

    def _parse_screen(self):
        """
        Examine screen for interesting stuff.
        Potentially check on inventory.
        """
        if self.nhc.is_killed and self.DEBUG_PRINT:
            print()
            print("\n".join(self.nhc.screen.display))


    def _save_progress(self):
        """
        Saves the current history buffer. In the case of coming back to the
        same session, old history will be lost.
        TODO: Consider being able to continue sessions.
        """
        with open(self.progress_filename, "wb") as outfile:
            pickle.dump(self.nhc.data_history, outfile, protocol=pickle.HIGHEST_PROTOCOL)