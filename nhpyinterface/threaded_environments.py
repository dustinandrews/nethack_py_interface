# -*- coding: utf-8 -*-
"""
Created on Sun Feb 18 09:24:13 2018

@author: dandrews
"""
import concurrent.futures
from nh_environment import NhEnv
import inspect
import logging



class MultiThreadEnvironments():
    logger = logging.getLogger()
    thread_timeout = 120

    def __init__(self, callback):
        """
        The callback function must take an NhEnv as an argument and
        return a tuple of (action,strategy)
        """
        assert inspect.isfunction(callback) or inspect.ismethod(callback)
        self.callback = callback

    def step_environments(self):
        self.logger.debug("Stepping all enviroments.")
        if not self.envs:
            raise ValueError("Must call create_envs first")
        results = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(e.step_with_callback,self.callback): e \
                       for e in self.envs if not e.is_done}
            for future in concurrent.futures.as_completed(futures, self.thread_timeout):
                results[futures[future]] = future.result()
        return results

    def reset_all_environments(self):
        """
        Runs each environment on a thread with the callback
        Returns a dictionary of {environments:results}
        """
        if not self.envs:
            raise ValueError("Must call create_envs first")
        results = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(e.reset):e for e in self.envs}
            for future in concurrent.futures.as_completed(futures, self.thread_timeout):
                results[futures[future]] = future.result()
        return results

    def reset_done_environments(self):
        if not self.envs:
            raise ValueError("Must call create_envs first")
        results = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {executor.submit(e.reset):e for e in self.envs if e.is_done}
            for future in concurrent.futures.as_completed(futures, self.thread_timeout):
                results[futures[future]] = future.result()

    def create_envs(self, num):
        offset = ord('b')
        envs = []
        futures = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for i in range(num):
                name = str(chr(i+offset) * 2)
                f = executor.submit(NhEnv, name)
                futures.append(f)
            for future in concurrent.futures.as_completed(futures, self.thread_timeout):
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
        out_dict = {}
        for e in self.envs:
            out_dict[e.nhc.username] = e.nhc.get_status()['t']
        return out_dict

#%%
if __name__ == '__main__':


    log_format ='(%(threadName)-0s) %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s'
    log_level = logging.INFO
    IN_IPYNB = 'get_ipython' in vars()

    if IN_IPYNB:
        logger = logging.getLogger()
        logger.setLevel(log_level)
        for h in logger.handlers:
            h.setFormatter(logging.Formatter(log_format))
    else:
        logging.basicConfig(level=log_level, format=log_format)

#%%

    import numpy as np
    from matplotlib import pyplot as plt

    def test_callback(data):
        return (np.random.randint(10),0)

    mte = MultiThreadEnvironments(test_callback)
    mte.create_envs(10)

    def smoke_test():

        print(mte.get_env_turns())
        results = mte.step_environments()
        print(mte.get_env_turns())
        mte.close()

        for k in mte.envs:
            plt.imshow(results[k][0])
            plt.show()

#%%

    def run_muliple_sessions(n):
        mte.reset_all_environments()
        for _ in range(n):
            print(_, end=" ")
            mte.step_environments()
            print(mte.get_env_turns())

   # run_muliple_sessions(1000)

