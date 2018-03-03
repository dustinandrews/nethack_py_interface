# -*- coding: utf-8 -*-
"""
Created on Sun Feb 18 09:24:13 2018

@author: dandrews
"""
import concurrent.futures
from nh_environment import NhEnv
import inspect
import logging
import time



class MultiThreadEnvironments():
    logger = logging.getLogger()
    thread_timeout = 300
    envs = []

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
        futures = []
        envs = []
        complete = 0
        # initial connect may be throttled or thread starvation problems
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for i in range(num):
                self.logger.debug("queued {}".format(i + complete))
                name = 'bot{:03}'.format(i)
                f = executor.submit(NhEnv, name)
                futures.append(f)
                time.sleep(0.1) # don't hit throttles
            for future in concurrent.futures.as_completed(futures, self.thread_timeout):
                try:
                    e = future.result()
                    envs.append(e)
                except Exception as exc:
                    self.logger.error("create env exception {}".format(exc))
                complete += 1
                self.logger.debug("completed {}", complete)
        self.envs = envs

    def close(self):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            if self.envs:
                for e in self.envs:
                    f = executor.submit(e.close)
                    futures.append(f)
                for future in concurrent.futures.as_completed(futures):
                    pass

    def get_env_turns(self):
        out_dict = {}
        for e in self.envs:
            out_dict[e.nhi.username] = e.nhi.get_status()['t']
        return out_dict

#%%
if __name__ == '__main__':

    def test_callback(data):
        return (np.random.randint(10),0)
    mte = MultiThreadEnvironments(test_callback)
#%%

    log_format ='(%(threadName)-0s) %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s'
    logging.basicConfig(level=logging.WARNING, format=log_format)

    IN_IPYNB = 'get_ipython' in vars()
    if IN_IPYNB:
        logger = mte.logger
        logger.setLevel(logging.WARNING)
        for h in logger.handlers:
            h.setFormatter(logging.Formatter(log_format))



#%%
    import numpy as np
    from matplotlib import pyplot as plt

#    mte.create_envs(10)

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

#%%
    import threading
    def time_steps(num):
        results = {}
        for i in num:
            print(i)
            mte = MultiThreadEnvironments(test_callback)
            try:
                mte.create_envs(i)
            except Exception as exp:
                print ("failed at {} with {}".format(i, exp))
                for t in threading.enumerate():
                    print(t.name)
                return exp
            print("created")
            mte.reset_done_environments()
            print("reset")
            start = time.monotonic()
            for t in range(100):
#                for e in mte.envs:
#                    e.step_with_callback(test_callback)
                mte.step_environments()
            end = time.monotonic()
            print("100 steps done for {}".format(len(mte.envs)))
            elapsed = end-start
            print(i, elapsed)
            results[i] = elapsed
            mte.close()
            del mte

        return results

    #time_steps()
    data = time_steps([1,2,4, 8, 16, 32, 64])
    for d in data:
            print("{:.3f}\t{:.3f}\t{:.3f}\t{:.3f}".format(d, data[d], d * 100, (d*100)/data[d]))