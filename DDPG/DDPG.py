# -*- coding: utf-8 -*-
"""
Created on Wed Nov 22 16:05:34 2017

@author: dandrews
"""
import sys
sys.path.append('D:/local/machinelearning/textmap')
from tmap import Map

from replay_buffer import ReplayBuffer
from actor_network import ActorNetwork
from critic_network import CriticNetwork
import keras
import numpy as np
from keras import backend as K
K.clear_session()

class DDPG(object):
    buffer_size = 1000
    batch_size = 100
    epochs = 500
    input_shape = (2,2)
    decay = 0.9
    TAU = 0.125
    
    
    def __init__(self):
        e = Map(self.input_shape[0],self.input_shape[1])        
        self.output_shape = e.action_space.n
        self.action_input_shape = (1,)
        
        self.environment = e
        
        self.buffer = ReplayBuffer(self.buffer_size)
        
        actor_network = ActorNetwork()        
        self.actor = actor_network.create_actor_network(
                self.input_shape,
                self.output_shape)
        self.actor_target = actor_network.create_actor_network(
                self.input_shape,
                self.output_shape)
        
        critic_network = CriticNetwork()
        self.critic = critic_network.create_critic_network(
                self.input_shape,
                self.output_shape,
                self.action_input_shape
                )        
        self.critic_target = critic_network.create_critic_network(
                self.input_shape,
                self.output_shape,
                self.action_input_shape
                )
        
        

    def step(self):
        state = np.expand_dims(self.environment.data_normalized(), axis=0)        
        prediction = self.actor.predict([state],1)
        return prediction
        
    def target_train(self, source: keras.models.Model, target: keras.models.Model):
        source_weights = source.get_weights()
        target_weights = target.get_weights()
        for i in range(len(source_weights)):
            target_weights[i] = self.TAU * source_weights[i] +\
            (1. - self.TAU) * target_weights[i]
            # move weights back to source, experimental.
            source_weights[i] = target_weights[i]
            
        
        
    
    def fill_replay_buffer(self, random_data=False):
        e = self.environment
        rewards = []
        for i in range(self.buffer_size):
            if e.done:
                e.reset()            
            a = self.get_action(random_data)
            s = e.data_normalized()
            (s_, r, t, info) = e.step(a)            
            self.buffer.add(s, [a], [r], [t], s_)
            rewards.append(r)
        return rewards
            
                
    def train_critic_from_buffer(self):
        loss_record = []
        for i in range(self.buffer_size//self.batch_size):
           s_batch, a_batch, r_batch, t_batch, s2_batch = self.buffer.sample_batch(self.batch_size)
           loss = self.critic.train_on_batch([s_batch, a_batch], r_batch)
           self.target_train(self.critic, self.critic_target)
           loss_record.append(loss)
        return loss_record
           
    def train_actor_from_buffer(self):
        loss_record = []
        for i in range(self.buffer_size//self.batch_size):
            s_batch, a_batch, r_batch, t_batch, s2_batch  = self.buffer.sample_batch(self.batch_size)
            a_batch.resize((self.batch_size,))           
            a_one_hot = np.eye(self.output_shape)[a_batch]
            
            critic_predictions = self.critic_target.predict([s_batch,a_batch])
            
            gradient  = a_one_hot * critic_predictions
            loss = self.actor.train_on_batch(s_batch, gradient)            
            self.target_train(self.actor, self.actor_target)
            loss_record.append(loss)
        return loss_record
           
    def train(self):
        random_data = False
        critic_loss = []
        actor_loss = []
        scores = []
        for i in range(self.epochs):
            s = self.fill_replay_buffer(random_data=random_data)
            scores.append(np.mean(s))
            c_loss = self.train_critic_from_buffer()
            a_loss = self.train_actor_from_buffer()
            critic_loss.extend(c_loss)
            actor_loss.extend(a_loss)
            random_data = False            
            print(i, np.mean(c_loss), end=",")
        return critic_loss, actor_loss, scores
        


    def get_action(self, random_data=False):
        if random_data:
            state = np.array(self.environment.data_normalized())
            state = np.expand_dims(state, axis=0)
            pred = self.actor_target.predict(state).squeeze()
            # e-greedy
            #action = np.argmax(pred)
            
            # weighted random
            action = np.random.choice(len(pred), p = pred)
        else: 
            action = np.random.randint(0, self.output_shape)
        return action


if __name__ == '__main__':
    ddpg = DDPG()
    m = Map(10,10)
    m.render()
    pred = ddpg.step()
    print(pred) 
    ddpg.fill_replay_buffer(random_data=True)
    self = ddpg
    s_batch, a_batch, r_batch, t_batch, s2_batch = ddpg.buffer.sample_batch(10)
#%%
    critic_loss, actor_loss, scores = ddpg.train()
    
    import matplotlib.pyplot as plt
    plt.plot(critic_loss, label="critic_loss")
    plt.plot(actor_loss, label="actor_loss")
    plt.legend()
    plt.show()
    plt.plot(scores, label="scores")
    plt.legend()
    plt.show()
    
