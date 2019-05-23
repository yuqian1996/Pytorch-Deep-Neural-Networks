# -*- coding: utf-8 -*-
import torch
import sys
sys.path.append('..')
from core.module import Module
from core.pre_module import Pre_Module
from torch.nn.parameter import Parameter
from torch.nn import functional as F
from torch.nn import init

class RBM(torch.nn.Module):
    def __init__(self,w,b,cnt,**kwargs):
        default = {'cd_k': 1, 
                   'unit_type': ['Gaussian','Gaussian'],
                   'lr': 1e-3,
                   'dvc': ''}
        for key in default.keys():
            if key in kwargs:
                setattr(self, key, kwargs[key])
            else:
                setattr(self, key, default[key])
        
        super().__init__()
        self.name = 'RBM-{}'.format(cnt+1)
        self.wh = w
        self.bh = b
        self.wv = w.t()
        self.bv = Parameter(torch.Tensor(w.size(1)))
        init.constant_(self.bv, 0)
        
        #print_module:
        print()
        #print_parameter:
        print("{}'s Parameters(".format(self.name))
        for para in self.state_dict():print('  {}'.format(para))
        print(')')
    
    def transfrom(self, x, direction):
        if direction == 'v2h':
            i = 0
            z = F.linear(x, self.wh, self.bh)
        else:
            i = 1
            z = F.linear(x, self.wv, self.bv)
        if self.unit_type[i] == 'Binary':
            p = F.sigmoid(z)
            s = (torch.rand(p.size())< p).float().to(self.dvc)
            return p, s
        elif self.unit_type[i] == 'Gaussian':
            u = z
            s = u
            return u, s
    
    def feature(self, x):
        _, out = self.transfrom(x,'v2h')
        return out
    
    def forward(self, x):
        v0 = x
        ph0, h0 = self.transfrom(v0,'v2h')
        pvk, vk = self.transfrom(h0,'h2v')
        for k in range(self.cd_k-1):
            phk, hk = self.transfrom(vk,'v2h')
            pvk, vk = self.transfrom(hk,'h2v')
        phk, hk = self.transfrom(vk,'v2h')
        vk = pvk
        hk = phk
        return v0, h0, vk, hk
    
    def update(self, v0, h0, vk, hk):
        v0, h0, vk, hk = v0.data, h0.data, vk.data, hk.data
        positive = torch.bmm(h0.unsqueeze(-1),v0.unsqueeze(1))
        negative = torch.bmm(hk.unsqueeze(-1),vk.unsqueeze(1))
        
        delta_w = positive - negative
        delta_b = h0 - hk
        delta_a = v0 - vk
        
        self.wh += torch.mean(delta_w,0) * self.lr
        self.bh += torch.mean(delta_b,0) * self.lr
        self.bv += torch.mean(delta_a,0) * self.lr
        
        l1_w, l1_b, l1_a = torch.mean(torch.abs(delta_w)), torch.mean(torch.abs(delta_b)), torch.mean(torch.abs(delta_a))
        return l1_w, l1_b, l1_a
    
    def batch_training(self, epoch, *args):
        if epoch == 1:
            print('\nTraining '+self.name+ ' in {}:'.format(self.dvc))
        with torch.no_grad():
            for batch_idx, (data, _) in enumerate(self.train_loader):
                data = data.to(self.dvc)
                v0,h0,vk,hk = self.forward(data, *args)
                l1_w, l1_b, l1_a = self.update(v0,h0,vk,hk)
                if (batch_idx+1) % 10 == 0 or (batch_idx+1) == len(self.train_loader):
                    msg_str = 'Epoch: {} - {}/{} | l1_w = {:.4f}, l1_b = {:.4f}, l1_a = {:.4f}'.format(
                            epoch, batch_idx+1, len(self.train_loader), l1_w, l1_b, l1_a)
                    sys.stdout.write('\r'+ msg_str)
                    sys.stdout.flush()
        
class DBN(Module, Pre_Module):  
    def __init__(self, **kwargs):
        self.name = 'DBN'
        kwargs['dvc'] = torch.device('cpu')
        self.kwargs = kwargs
        Module.__init__(self, **kwargs)
        self.Sequential()
        self.opt()
        self.Stacked()

    def forward(self, x):
        x = self.feature(x)
        x = self.output(x)
        return x
    
    def add_pre_module(self, w, b, cnt):
        rbm = RBM(w,b,cnt,**self.kwargs)
        return rbm

if __name__ == '__main__':
    
    parameter = {'struct': [784,400,100,10],
                 'hidden_func': ['Gaussian', 'Affine'],
                 'output_func': 'Affine',
                 'dropout': 0.0,
                 'task': 'cls',
                 'flatten': True}
    
    model = DBN(**parameter)
    
    model.load_mnist('../data', 128)
    
    model.pre_train(3, 128)
    for epoch in range(1, 3 + 1):
        model.batch_training(epoch)
        model.test()