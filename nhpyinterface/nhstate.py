# -*- coding: utf-8 -*-
"""
Created on Tue Feb  6 17:39:19 2018

@author: dandrews
"""

from nh_interface import NhInterface
import pickle

class NhState:
    """
    Class to understand stuff about the game, like inventory and items.
    """
    DEBUG_PRINT = False
    progress_filename = "nh_progress.dat"

    def __init__(self, nhi : NhInterface):
        self.nhi = nhi

    def check_game_state(self):
        """
        Examine the game state for interesting stuff and
        clear any prompts before returning.
        returns True if game over.
        """
        done = False
        safety = 0
        threshold = 1000
        while not done and (self.nhi.is_special_prompt):
            if safety > threshold:
                message = ""
                attribs = dir(self.nhi)
                for at in [a for a in attribs if 'is_' in a]:
                    message += ' {}: {}\n'.format(at, getattr(self.nhi, at))
                raise ValueError("Unexpectedly looping\n" + message)
            if self.nhi.is_always_no_question:
                self.nhi.send_string('n\n')
            if self.nhi.is_killed or self.nhi.is_dgamelaunch:
                done = True
            self._parse_screen()
            if self.nhi.is_always_yes_question:
                self.nhi.send_string('y')
                self.nhi.send_string('\n')
            elif self.nhi.is_always_no_question:
                self.nhi.send_string('n')
                self.nhi.send_string('\n')
            else:
                self.nhi.send_string('\n')
            self._save_progress()

            # When fainted there can be a lot of messages to clear.
            if not self.nhi.is_fainted:
                safety += 1

        return done

    def _parse_screen(self):
        """
        Examine screen for interesting stuff.
        Potentially check on inventory.
        """
        if self.nhi.is_killed and self.DEBUG_PRINT:
            print()
            print("\n".join(self.nhi.screen.display))


    def _save_progress(self):
        """
        Saves the current history buffer. In the case of coming back to the
        same session, old history will be lost.
        TODO: Consider being able to continue sessions.
        """
        with open(self.progress_filename, "wb") as outfile:
            pickle.dump(self.nhi.data_history, outfile, protocol=pickle.HIGHEST_PROTOCOL)