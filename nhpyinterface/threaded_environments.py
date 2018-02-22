# -*- coding: utf-8 -*-
"""
Created on Sun Feb 18 09:24:13 2018

@author: dandrews
"""
import concurrent.futures
from nh_environment import NhEnv
import inspect

class MultiThreadEnvironments():

    def __init__(self, callback):
        """
        The callback function must take an NhEnv as an argument and
        return a tuple of (action,strategy)
        """
        assert inspect.isfunction(callback) or inspect.ismethod(callback)
        self.callback = callback

    def step_environments(self):
        if not self.envs:
            raise ValueError("Must call create_envs first")
        results = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(e.step_with_callback,self.callback): e  for e in self.envs}
            for future in concurrent.futures.as_completed(futures, 20):
                results[futures[future]] = future.result()
        return results

    def reset_done_environments(self):
        """
        Runs each environment on a thread with the callback
        Returns a dictionary of {environments:results}
        """
        if not self.envs:
            raise ValueError("Must call create_envs first")
        results = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(e.reset):e for e in self.envs if e.is_done}
            for future in concurrent.futures.as_completed(futures, 20):
                results[futures[future]] = future.result()
        return results

    def create_envs(self, num):
        offset = ord('b')
        envs = []
        futures = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for i in range(num):
                name = str(chr(i+offset) * 2)
                f = executor.submit(NhEnv, name)
                futures.append(f)
            for future in concurrent.futures.as_completed(futures):
                envs.append(future.result())
        self.envs = envs

    def close(self):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for e in self.envs:
                f = executor.submit(e.close)
                futures.append(f)
            for future in concurrent.futures.as_completed(futures):
                pass

    def get_env_turns(self):
        out_str = []
        for e in self.envs:
            out_str.append("{} {}".format(e.nhc.username,e.nhc.get_status()['t'] ))
        return out_str

if __name__ == '__main__':
    import numpy as np

    def test_callback(data):
        return (np.random.randint(10),0)

    mte = MultiThreadEnvironments(test_callback)
    mte.create_envs(10)
    print(mte.get_env_turns())
    results = mte.step_environments()
    print(mte.get_env_turns())
    mte.close()
#%%
    def run_1k():
        for _ in range(1000):
            mte.reset_done_environments()
            mte.step_environments()
            print(mte.get_env_turns())

