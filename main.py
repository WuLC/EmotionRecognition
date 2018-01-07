# -*- coding: utf-8 -*-
# Created on Tue Jan 02 2018 11:2:1
# Author: WuLC
# EMail: liangchaowu5@gmail.com

import os
import time
import torch
import fire
import ipdb
from tqdm import tqdm
from torch.utils.data import DataLoader
from torch.autograd import Variable
from torchnet import meter

import models
from data.dataset import FaceExpression
from configuration import config
from utils.visualize import Visualizer

def train(**kwargs):
    # config.parse(kwargs)
    vis = Visualizer(config.env)

    # step1: configure model
    model = models.AlexNet(num_classees = config.num_classes)
    if config.pretrained_model_path:
        model.load(config.pretrained_model_path)
    if config.use_gpu and torch.cuda.is_available(): 
        model.cuda()

    # step2: data
    train_data = FaceExpression(config.train_data_root, train=True)
    val_data = FaceExpression(config.train_data_root, train=False)
    test_data = FaceExpression(config.test_data_root, test=True)
    train_dataloader = DataLoader(train_data, config.batch_size,
                        shuffle=True,num_workers=config.num_workers)
    val_dataloader = DataLoader(val_data, config.batch_size,
                        shuffle=False,num_workers=config.num_workers)
    test_dataloader = DataLoader(test_data, config.batch_size,
                        shuffle=False,num_workers=config.num_workers)
    # step3: criterion and optimizer
    criterion = torch.nn.CrossEntropyLoss()
    lr = config.lr
    #optimizer = torch.optim.Adam(model.parameters(), lr = lr, weight_decay = config.weight_decay)
    optimizer=torch.optim.SGD(model.parameters(), lr = lr, weight_decay = config.weight_decay)
        
    # step4: meters
    loss_meter = meter.AverageValueMeter()
    confusion_matrix = meter.ConfusionMeter(config.num_classes)
    previous_loss = 1e100

    # train
    train_accuracy, val_accuracy = 0, 0
    for epoch in range(config.max_epoch):
        if epoch != 0:
            print('{0} epoch, loss {1}, train accuracy {2:4f}, val accuracy {3:4f}'.format(epoch, loss_meter.value()[0], train_accuracy, val_accuracy))
        loss_meter.reset()
        confusion_matrix.reset()

        #for i, (data,label) in tqdm(enumerate(train_dataloader), total=len(train_data)):
        for i, (data,label) in enumerate(train_dataloader):
            #print(data.shape)
            #print(label.shape)
            input = Variable(data)
            target = Variable(label)
            if config.use_gpu and torch.cuda.is_available():
                input = input.cuda()
                target = target.cuda()

            optimizer.zero_grad()
            score = model(input)
            loss = criterion(score, target)
            loss.backward()
            optimizer.step()
            
            # meters update and visualize
            loss_meter.add(loss.data[0])
            confusion_matrix.add(score.data, target.data)

            if i % config.print_freq==config.print_freq-1:
                vis.plot('loss', loss_meter.value()[0])
                
                # 进入debug模式
                if os.path.exists(config.debug_file):
                    ipdb.set_trace()
        # model.save()

        # validate and visualize
        train_cm_values = confusion_matrix.value()
        train_accuracy = sum([train_cm_values[i][i] for i in range(config.num_classes)]) / train_cm_values.sum()
        val_cm, val_accuracy = val(model, test_dataloader)
        vis.plot('val_accuracy', val_accuracy)
        content = '''*******epoch:{epoch} , lr:{lr}, loss:{loss}
                    train_cm:{train_cm}
                    val_cm:{val_cm}\n
                  '''.format(epoch = epoch,
                             loss = loss_meter.value()[0],
                             val_cm = str(val_cm.value()),
                             train_cm=str(confusion_matrix.value()),
                             lr=lr)
        vis.log(content)
        
        # update learning rate
        if loss_meter.value()[0] > previous_loss:          
            lr = lr * config.lr_decay
            # 第二种降低学习率的方法:不会有moment等信息的丢失
            for param_group in optimizer.param_groups:
                param_group['lr'] = lr
        previous_loss = loss_meter.value()[0]

def val(model, dataloader):
    '''
    计算模型在验证集上的准确率等信息
    '''
    model.eval()
    #print('==============start evaluating====================')
    confusion_matrix = meter.ConfusionMeter(config.num_classes)
    for ii, data in enumerate(dataloader):
        input, label = data
        val_input = Variable(input, volatile=True)
        val_label = Variable(label.type(torch.LongTensor), volatile=True)
        if config.use_gpu:
            val_input = val_input.cuda()
            val_label = val_label.cuda()
        score = model(val_input)
        confusion_matrix.add(score.data.squeeze(), label.type(torch.LongTensor))

    model.train()
    cm_value = confusion_matrix.value()
    accuracy = sum([cm_value[i][i] for i in range(config.num_classes)]) / (cm_value.sum())
    return confusion_matrix, accuracy


def help():
    '''
    打印帮助的信息： python file.py help
    '''
    
    print('''
    usage : python file.py <function> [--args=value]
    <function> := train | test | help
    example: 
            python {0} train --env='env0701' --lr=0.01
            python {0} test --dataset='path/to/dataset/root/'
            python {0} help
    avaiable args:'''.format(__file__))

    from inspect import getsource
    source = (getsource(config.__class__))
    print(source)

if __name__=='__main__':
    fire.Fire()