from os import chdir
chdir('...')

from GAN_Tools import get_default_device, to_device, Generator, Critic, Results, Environment

import pandas as pd
import numpy as np
from os import mkdir
from os.path import isdir, exists
from torch import optim
import random
from torch import manual_seed

from plotnine import ggplot, aes, geom_line, geom_vline, labels, scales

#Laptop
PATH = '...'

##Check dir structure, and make sub-directories if not present
if not isdir(PATH+'/Results'):
    mkdir(PATH+'/Results')
if not isdir(PATH+'/Results/External_Results'):
    mkdir(PATH+'/Results/External_Results')
if not isdir(PATH+'/Results/Main_Results'):
    mkdir(PATH+'/Results/Main_Results')
if not isdir(PATH+'/Results/External_Results/Saved_Pars'):
    mkdir(PATH+'/Results/External_Results/Saved_Pars')
if not isdir(PATH+'/Results/Main_Results/Saved_Pars'):
    mkdir(PATH+'/Results/Main_Results/Saved_Pars')
if not isdir(PATH+'/Results/Main_Results/overrep'):
    mkdir(PATH+'/Results/Main_Results/overrep')
if not isdir(PATH+'/Results/Main_Results/overrep/Saved_Pars'):
    mkdir(PATH+'/Results/Main_Results/overrep/Saved_Pars')
if not isdir(PATH+'/Data'):
    mkdir(PATH+'/Data')
    print('WARNING: ENSURE DATA IS COPIED INTO THIS DIRECTORY')


Env_pre = Environment()
Env_pre.device = get_default_device()

experiment_data = 'metabolomics'

Env_pre.PATH = PATH

np.random.seed(117)
manual_seed(117)
random.seed(117)

#%%
###TRAINING
#pars
Env_pre.func_optim = optim.SGD
Env_pre.n_features = 218
Env_pre.alpha = 0
Env_pre.beta = 13
Env_pre.batch_size = 30
Env_pre.iter_critic = 4

dropout_prob = 0.5

#%%
##remove IDs if real data
def prepare_dat(path_dir, file_name, n_cols_rem):
    if not exists(path_dir + '/' + file_name[:-4] + '_inp.csv'):
        dat_temp = pd.read_csv(path_dir + '/' + file_name)
        dat_temp = dat_temp.iloc[:, n_cols_rem:]
        dat_temp.to_csv(path_dir + '/' + file_name[:-4] + '_inp.csv', index = False)

#remove ID and label
if experiment_data == 'microarray':
    prepare_dat(PATH + '/Data', 'dat_ext.csv', 2)
if experiment_data == 'simulation':
    prepare_dat(PATH + '/Data', 'dat_ext.csv', 0)
if experiment_data == 'metabolomics':
    prepare_dat(PATH + '/Data', 'dat_ext.csv', 2)
else:
    print('Error')
    
    
     
#%%
##Train pre_GAN on external data

#For sim
#Env_pre.path_dat = PATH + '/sim_dat_ext.csv'
#For real
Env_pre.path_dat = PATH + '/Data/dat_ext_inp.csv'

Env_pre.path_results = PATH + '/Results/External_Results'
Env_pre.path_pars = Env_pre.path_results + '/Saved_Pars'



Env_pre.n_training_samples = sum(1 for line in open(Env_pre.path_dat)) - 1 #number of records in file (excludes header)

Env_pre.critic = Critic(Env_pre.n_features, Env_pre.init_weights, 200, dropout_prob)
Env_pre.generator = Generator(Env_pre.n_features, Env_pre.init_weights, 50, dropout_prob)
Env_pre.results_record = Results(path = Env_pre.path_results, saved_results = False)

to_device(Env_pre.critic.train(), Env_pre.device)
to_device(Env_pre.generator.train(), Env_pre.device)


##transformer generated based on batch of size 200 or max data if < 200 (95 samples in metabolomics)
if experiment_data == 'metabolomics':
    Env_pre.transformer = Env_pre.get_scaler(95, '/ext_transformer.pkl')
else:
    Env_pre.transformer = Env_pre.get_scaler(200, '/ext_transformer.pkl')



#%%
##First training loop
if experiment_data == 'microarray':
    Env_pre.lr = 0.0005
    n_epochs = 1000
if experiment_data == 'simulation':
    Env_pre.lr = 0.001
    n_epochs = 1000
if experiment_data == 'metabolomics':
    Env_pre.lr = 0.001
    n_epochs = 1000

telapsed_1 = Env_pre.train(n_epochs)

#%%
##Grow
#input
##check for null values
max_loss = 15
min_loss = -10

i_losses = Env_pre.results_record.record['n_pre_layers'] == 1.0
losses = Env_pre.results_record.record['loss_critic'][i_losses]
ind_check = np.array([np.nan, np.nan])

if losses.gt(max_loss).sum() > 0: #check for null values
    ind_check[0] = losses.gt(max_loss).argmax()
if losses.lt(min_loss).sum() > 0:
    ind_check[1] = losses.lt(min_loss).argmax()

if np.isnan(ind_check).sum() == 2: #no values gt or lt limits
    ind_null = len(losses)
else:
    ind_null = int(ind_check[np.nanargmin(ind_check)]) + 1
    
losses = losses[:ind_null]
print('Null value at index {}, epoch {}'.format(ind_null, ind_null * 20))

nEpoch_pars, graph_loss = Env_pre.findApEl(offset = ind_null)

plot = (
    ggplot(Env_pre.results_record.record.iloc[:ind_null-1])
    + geom_line(color = 'red', mapping = aes(y = 'loss_critic', x = 'epoch'))
    + geom_line(color = 'blue', mapping = aes(y = 'loss_gen', x = 'epoch'))
    + geom_vline(xintercept = nEpoch_pars, size = 0.2)
    + labels.xlab('Epoch')
    + labels.ylab('Loss')
    + scales.ylim(-10, 15)
)

graph_loss.save(Env_pre.path_results+'/plot_loss_bestFit' + '_loop_1' + '.png')
plot.save(Env_pre.path_results+'/plot_loss' + '_loop_1' + '.png')
Env_pre.select_pars(str(nEpoch_pars))
Env_pre.generator.save_pars(Env_pre.path_pars, 'complete_loop_1')

Env_pre.results_record.save_results(Env_pre.PATH + '/Results')


Env_pre.generator.grow(100)
Env_pre.critic.grow(100)

to_device(Env_pre.generator, Env_pre.device)
to_device(Env_pre.critic, Env_pre.device)



#%%
##Second training loop
#input
if experiment_data == 'microarray':
    Env_pre.lr = 0.00005
    n_epochs = 7000
if experiment_data == 'simulation':
    Env_pre.lr = 0.0001
    n_epochs = 10000
if experiment_data == 'metabolomics':
    Env_pre.lr = 0.00005
    n_epochs = 17000

#

telapsed_2 = Env_pre.train(n_epochs)


#%%
##Grow
#input
##check for null values
i_losses = Env_pre.results_record.record['n_pre_layers'] == 2.0
losses = Env_pre.results_record.record['loss_critic'][i_losses]
ind_check = np.array([np.nan, np.nan])

if losses.gt(max_loss).sum() > 0: #check for null values
    ind_check[0] = losses.gt(max_loss).argmax()
if losses.lt(min_loss).sum() > 0:
    ind_check[1] = losses.lt(min_loss).argmax()

if np.isnan(ind_check).sum() == 2: #no values gt or lt limits
    ind_null = len(losses)
else:
    ind_null = int(ind_check[np.nanargmin(ind_check)]) + 1
    
losses = losses[:ind_null]
print('Null value at index {}, epoch {}'.format(ind_null, ind_null * 20))

nEpoch_pars, graph_loss = Env_pre.findApEl(offset = ind_null)

plot = (
    ggplot(Env_pre.results_record.record.iloc[:ind_null-1])
    + geom_line(color = 'red', mapping = aes(y = 'loss_critic', x = 'epoch'))
    + geom_line(color = 'blue', mapping = aes(y = 'loss_gen', x = 'epoch'))
    + geom_vline(xintercept = nEpoch_pars, size = 0.2)
    + labels.xlab('Epoch')
    + labels.ylab('Loss')
    + scales.ylim(-10, 15)
)

graph_loss.save(Env_pre.path_results+'/plot_loss_bestFit' + '_loop_2' + '.png')
plot.save(Env_pre.path_results+'/plot_loss' + '_loop_2' + '.png')
Env_pre.select_pars(str(nEpoch_pars))
Env_pre.generator.save_pars(Env_pre.path_pars, 'complete_loop_2')

Env_pre.results_record.save_results(Env_pre.PATH + '/Results')


Env_pre.generator.grow(200)
Env_pre.critic.grow(50)

to_device(Env_pre.generator, Env_pre.device)
to_device(Env_pre.critic, Env_pre.device)



#%%
##Third training loop
#input
Env_pre.iter_critic = 2
dropout_prob = 0.7

if experiment_data == 'microarray':
    Env_pre.lr = 0.00001 #0.00005
    n_epochs = 8000
if experiment_data == 'simulation':
    Env_pre.lr = 0.00001
    n_epochs = 8000
if experiment_data == 'metabolomics':
    Env_pre.lr = 0.0005
    n_epochs = 20000

#

Env_pre.generator.change_dropout(dropout_prob)
Env_pre.critic.change_dropout(dropout_prob)

telapsed_3 = Env_pre.train(n_epochs)


#%%
##Select final generator pars
#input
##check for null values
i_losses = Env_pre.results_record.record['n_pre_layers'] == 3.0
losses = Env_pre.results_record.record['loss_critic'][i_losses]
ind_check = np.array([np.nan, np.nan])

if losses.gt(max_loss).sum() > 0: #check for null values
    ind_check[0] = losses.gt(max_loss).argmax()
if losses.lt(min_loss).sum() > 0:
    ind_check[1] = losses.lt(min_loss).argmax()

if np.isnan(ind_check).sum() == 2: #no values gt or lt limits
    ind_null = len(losses)
else:
    ind_null = int(ind_check[np.nanargmin(ind_check)]) + 1
    
losses = losses[:ind_null]
print('Null value at index {}, epoch {}'.format(ind_null, ind_null * 20))

nEpoch_pars, graph_loss = Env_pre.findApEl(offset = ind_null)

plot = (
    ggplot(Env_pre.results_record.record.iloc[:ind_null-1])
    + geom_line(color = 'red', mapping = aes(y = 'loss_critic', x = 'epoch'))
    + geom_line(color = 'blue', mapping = aes(y = 'loss_gen', x = 'epoch'))
    + geom_vline(xintercept = nEpoch_pars, size = 0.2)
    + labels.xlab('Epoch')
    + labels.ylab('Loss')
    + scales.ylim(-10, 15)
)

graph_loss.save(Env_pre.path_results+'/plot_loss_bestFit' + '_loop_3' + '.png')
plot.save(Env_pre.path_results+'/plot_loss' + '_loop_3' + '.png')
Env_pre.select_pars(str(nEpoch_pars))
Env_pre.generator.save_pars(Env_pre.path_pars, 'complete_pre')

Env_pre.critic.save_pars(Env_pre.path_pars, 'complete_pre')

Env_pre.results_record.save_results(Env_pre.PATH + '/Results')



#%%
dat_telapsed = pd.DataFrame([telapsed_1, telapsed_2, telapsed_3])
dat_telapsed.to_csv(Env_pre.PATH + '/Results/telapsed.csv')