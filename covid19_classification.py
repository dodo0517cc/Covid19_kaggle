# -*- coding: utf-8 -*-
"""covid19-classification.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1OvhT5bWCebguu47-5TqBk4-2o-J4_K64
"""

! pip install efficientnet_pytorch

!pip install timm

import sys
import torch
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import torchvision.transforms as transforms
from PIL import Image
from torch import nn, optim
from torch.utils.data import Dataset, DataLoader
from efficientnet_pytorch import EfficientNet
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
import skimage
import timm
from tqdm import tqdm
from skimage import data, exposure, img_as_float
import os

import albumentations as A
from albumentations.pytorch import ToTensorV2
import cv2

class covid_Dataset(Dataset):

    def __init__(self,data,train=True,transform=None):
        self.df = data
        self.gender = ['M','F']
        self.train = train
        self.transform = transform
    def __getitem__(self,index):

        _, patient_id, study, box_count, category, sex, body_part, rows, columns, box, labels = self.df.iloc[index].values
        img = cv2.imread('/kaggle/input/image256/train/'+patient_id+'.jpg')
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img
#         fig, ax = plt.subplots(1, 1, figsize=(8, 4))
#         plt.title(patient_id)
#         ax.imshow(img)
#         img = img_as_float(img)
        image_tensor = self.transform(image=img)
#         fig2, ax2 = plt.subplots(1, 1, figsize=(8, 4))
#         plt.title(patient_id)
#         ax2.imshow(torch.squeeze(image_tensor['image'][1:2]),cmap='gray')
#         sys.exit()
        gender_data = [0]*len(self.gender)
        gender_data[ self.gender.index(sex) ] = 1
        gender_tensor = torch.tensor(gender_data)
        
        label_tensor = torch.tensor(labels)
        # -------------- check transform of images --------------
        #transforms.ToPILImage()(image_tensor['image']).convert('L').save('./'+patient_id+'.jpg')
        return image_tensor['image'],gender_tensor,label_tensor

    def pad_batch(self,batch):
        # collate_fn for Dataloader, pad sequence to same length and get mask tensor
        if batch[0][1] is not None:
            (image_tensor,gender_tensor,label_tensor) = zip(*batch)
            images = torch.stack(image_tensor)
            gender = torch.stack(gender_tensor)
            labels = torch.stack(label_tensor)
        else:
            (image_tensor,gender_tensor) = zip(*batch)
            images = torch.stack(image_tensor)
            gender = torch.stack(gender_tensor)
        return images,gender,labels
    
    def __len__(self):
        return len(self.df)

class efficient_model(nn.Module):
    def __init__(self):
        super(efficient_model, self).__init__()   
        model_efficient = timm.create_model('tf_efficientnet_b4', pretrained=False)
        self.efficient = model_efficient
        self.feature = model_efficient.classifier.in_features
        self.efficient.classifier = nn.Sequential(nn.Linear(self.feature,4),
                                )
#         print(self.efficient)
    def forward(self, x ,gender):
        logits = self.efficient(x)
        node_2 = x.view(x.size(0),-1)
#         gender = gender.reshape(logits.shape[0],-1)
#         merge = torch.cat((logits,gender),dim=1)
#         merge = merge.float()
#         merge = self.fc(merge)
        merge = logits
        return node_2,merge

def make_weights_for_balanced_classes(stage, nclasses):                        
    count = [0] * nclasses                                                      
    for item in stage:                                                         
        count[item] += 1                                                    
    weight_per_class = [0.] * nclasses
    N = sum(count)                                                  
    for i in range(nclasses):                                                   
        weight_per_class[i] = N/float(count[i])  
    print(weight_per_class)
    weight = [0] * len(stage)
    for idx, val in enumerate(stage):                                          
        weight[idx] = weight_per_class[val] 
    print(count)
    return weight

def auc_curve(fpr,tpr,roc_auc,i):
    plt.title('Receiver Operating Characteristic'+'Class: '+i)
    plt.plot(fpr, tpr, 'b', label = 'AUC = %0.2f' % roc_auc)
    plt.legend(loc = 'lower right')
    plt.plot([0, 1], [0, 1],'r--')
    plt.xlim([0, 1])
    plt.ylim([0, 1])
    plt.ylabel('True Positive Rate')
    plt.xlabel('False Positive Rate')
    plt.show()

def draw_chart(chart_data,outfile_name):
    # -------------- draw loss image --------------
    # -------------- new one figure and set resolution --------------
    plt.figure(figsize=(4.0, 2.0))
    plt.rcParams['savefig.dpi'] = 200
    plt.rcParams['figure.dpi'] = 200
    # -------------- plot data in image --------------
    plt.plot(chart_data['epoch'],chart_data['train_loss'],label='train_loss')
    plt.plot(chart_data['epoch'],chart_data['val_loss'],label='val_loss')
    # -------------- draw underline --------------
    plt.grid(True,axis="y",ls='--')
    # -------------- draw legent --------------
    plt.legend(loc= 'best')
    # -------------- show lable --------------
    plt.xlabel('epoch',fontsize=5)
 
    # plt.close('all')
    plt.show()
    # --------------

    plt.figure(figsize=(4.0, 2.0))
    plt.rcParams['savefig.dpi'] = 200
    plt.rcParams['figure.dpi'] = 200
    plt.plot(chart_data['epoch'],chart_data['val_acc'],label='val_acc')
    plt.plot(chart_data['epoch'],chart_data['train_acc'],label='train_acc')
    plt.grid(True,axis="y",ls='--')
    plt.legend(loc= 'best')
    plt.xlabel('epoch',fontsize=5)
    # plt.close('all')
    plt.show()
# --------------

def plot_confusion_matrix(cm, savename, title='Confusion Matrix'):

    plt.figure(figsize=(12, 8), dpi=100)
    np.set_printoptions(precision=2)
    classes = [0,1,2,3]
    ind_array = np.arange(4)
    x, y = np.meshgrid(ind_array, ind_array)
    for x_val, y_val in zip(x.flatten(), y.flatten()):
        c = cm[y_val][x_val]
        if c > 0.001:
            plt.text(x_val, y_val, "%0.2f" % (c,), color='red', fontsize=15, va='center', ha='center')
    
    plt.imshow(cm, interpolation='nearest', cmap=plt.cm.binary)
    plt.title(title)
    plt.colorbar()
    xlocations = np.array(range(4))
    plt.xticks(xlocations, classes)
    plt.yticks(xlocations, classes)
    plt.ylabel('Actual label')
    plt.xlabel('Predict label')
    
    # offset the tick
    tick_marks = np.array(range(4)) + 0.5
    plt.gca().set_xticks(tick_marks, minor=True)
    plt.gca().set_yticks(tick_marks, minor=True)
    plt.gca().xaxis.set_ticks_position('none')
    plt.gca().yaxis.set_ticks_position('none')
    plt.grid(True, which='minor', linestyle='-')
    plt.gcf().subplots_adjust(bottom=0.15)
    
    # show confusion matrix
    plt.savefig(savename, format='png')
    plt.show()

def flatten(t):
    return [item for sublist in t for item in sublist]

from sklearn.metrics import confusion_matrix
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.metrics import roc_curve, auc

def get_acc(loader,model,epoch):
#     with torch.no_grad():
    model.eval()
    val_loss = 0
    count = 0
    TP = 0
    FP = 0
    TN = 0
    FN = 0
    lab = []
    top = []
    au = []
    fp = []
    tp = []
    for step_, (batch) in enumerate(loader):
        images,gender,labels= [t.to(device) for t in batch]
        node_2, logits = model(images.float(),gender)
        topv, topi = logits.topk(1) 
        cm = confusion_matrix(labels.tolist(),topi.tolist(),labels=[0,1,2,3])
        for i in labels.tolist():
            lab.append(i)
        for i in topi.tolist():
            top.append(i)
        logits_ = torch.nn.functional.softmax(logits,dim=1)
        labels_ = label_binarize(np.array(labels.cpu()),classes=[0,1,2,3])
        
        for i in range(4):
            fpr, tpr, thr = roc_curve(labels_[:, i],np.array(logits_.tolist())[:, i])
            fp.append(fpr)
            tp.append(tpr)
            au.append(auc(fpr,tpr))
        FP += cm.sum(axis=0) - np.diag(cm)  
        FN += cm.sum(axis=1) - np.diag(cm)
        TP += np.diag(cm)
        TN += cm.sum() - (FP + FN + TP)
        count += cm.sum()
        #specificity
        speci = TN/(TN+FP)     
        loss_test = criterion(logits,labels)
        val_loss += loss_test.item() #take out the loss number
    recall = recall_score(lab,top, average='macro',zero_division=0)
    val_loss = val_loss / (step_+1)
    acc = np.sum(TP) / count
    cm = confusion_matrix(lab,top,labels=[0,1,2,3])
    print("val_auc: ",np.mean(au))
    return acc,val_loss,recall,cm,fp,tp

from sklearn.preprocessing import label_binarize
from sklearn.metrics import roc_curve, roc_auc_score, auc, plot_roc_curve
if __name__ == '__main__':
    # print(torch.cuda.get_device_name(0))
    # -------------- hyper parameter --------------
    batch_size = 32
    learning_rate = 0.001
    model_name = 'efficient_model'
    # ------------------------------------------
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # -------------- split data --------------
    df = pd.read_csv("/kaggle/input/covid-dataset/COVID19_data_.csv")
    train_pos,val_pos = train_test_split(df,train_size=0.8,random_state=42) 
    
    # -------------- unbalanced problem --------------
    stage = []
    for i in train_pos.iloc[:,10]:
        stage.append(i)
    weights_ = make_weights_for_balanced_classes(stage,4)
    weights = torch.DoubleTensor(weights_)
    sampler = torch.utils.data.sampler.WeightedRandomSampler(weights,len(weights), replacement=True) 

    stage_val = []
    for i in val_pos.iloc[:,10]:
        stage_val.append(i)
    weights_val_ = make_weights_for_balanced_classes(stage_val,4)
    weights_val = torch.DoubleTensor(weights_val_)
    val_sampler = torch.utils.data.sampler.WeightedRandomSampler(weights_val,len(weights_val), replacement=True)
    
    # ------------------------------------------
    train_transform = A.Compose([
       A.Resize(256,256),
       A.CenterCrop(224,224),
       A.augmentations.transforms.HorizontalFlip(p=0.5),
#        A.augmentations.transforms.VerticalFlip(p=0.5),
       A.ShiftScaleRotate(shift_limit=0.05, scale_limit=0.05, rotate_limit=20, p=0.5),
       A.OneOf([
           A.augmentations.transforms.Blur(),
           A.augmentations.transforms.GlassBlur(),
           A.augmentations.transforms.GaussianBlur(),
           A.augmentations.transforms.GaussNoise(),
           A.augmentations.transforms.RandomGamma(),
           A.augmentations.transforms.InvertImg(),
           A.augmentations.transforms.RandomFog()
       ], p=0.3),
#        A.CoarseDropout(p=0.5),
#        A.Cutout(p=0.5),
       ToTensorV2(),
    ])
    val_transform = A.Compose(
    [   A.Resize(256,256),
        A.CenterCrop(224,224),
#         A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225], max_pixel_value=255.0, p=1.0),
        ToTensorV2(),
    ])
    # -------------- prepare training and testing data --------------
    train_set = covid_Dataset(train_pos,train=True,transform=train_transform)
    test_set = covid_Dataset(val_pos,train=False,transform = val_transform)
    
    train_loader = DataLoader(train_set,sampler=sampler,batch_size=batch_size,drop_last=True)
    test_loader = DataLoader(test_set,sampler=val_sampler,batch_size=batch_size,drop_last=True)
    model = efficient_model()
#     model.load_state_dict(torch.load('/kaggle/input/efficient-model/'+model_name+'-2.pkl'))
    model = model.to(device)

# -------------- create optimizer and loss function --------------
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate,weight_decay=1e-3)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.1, 
                                   patience=3, min_lr=1e-5, verbose=False)
    criterion = nn.CrossEntropyLoss()

# -------------- init data for image --------------
    chart_data={"train_loss":[],"val_acc":[],"train_acc":[],"val_loss":[],"train_recall":[],"epoch":[],"f1":[],"f1_val":[]}
    max_acc,_,f1_val,cm_val,fp_val,tp_val = get_acc(tqdm(test_loader),model,-1)
    for epoch in range(70):
        train_loss = 0
        count = 0
        TP = 0
        FP = 0
        TN = 0
        FN = 0
        lab = []
        top = []
        au = []
        fp = []
        tp = []
        model.train()
        optimizer.zero_grad()
        for step, (batch) in enumerate(tqdm(train_loader)):
            images,gender,labels= [t.to(device) for t in batch]
            node_2, logits = model(images.float(),gender)
            topv, topi = logits.topk(1) 
            #for predic, label in zip(topi.tolist(),labels.tolist()):
            cm = confusion_matrix(labels.tolist(),topi.tolist(),labels=[0,1,2,3])
            for i in labels.tolist():
                lab.append(i)
            for i in topi.tolist():
                top.append(i)
            logits_ = torch.nn.functional.softmax(logits,dim=1)
            labels_ = label_binarize(np.array(labels.cpu()),classes=[0,1,2,3])
            for i in range(4):
                fpr, tpr, thr = roc_curve(labels_[:, i],np.array(logits_.tolist())[:, i])
                fp.append(fpr)
                tp.append(tpr)
                au.append(auc(fpr,tpr))
            FP += cm.sum(axis=0) - np.diag(cm)  
            FN += cm.sum(axis=1) - np.diag(cm)
            TP += np.diag(cm)
            TN += cm.sum() - (FP + FN + TP)
            count += cm.sum()
            #specificity
            speci = TN/(TN+FP)      
            model.zero_grad()
            loss = criterion(logits,labels)
            train_loss += loss.item() #take out the loss number
            loss.backward()
            optimizer.step()
        recall = recall_score(lab,top,average='macro',zero_division=0)
        acc = np.sum(TP) / count

        # -------------- get test data's acc --------------
        v_acc,val_loss,val_recall,val_cm,val_fp,val_tp = get_acc(test_loader,model,epoch)
        scheduler.step(val_loss)
        if v_acc > max_acc :
            max_acc = v_acc
            torch.save(model.state_dict(), './'+model_name+'.pkl')
            
        #--------------- confusion matrix-------------------
        cm = confusion_matrix(lab,top,labels=[0,1,2,3])
        print(cm)
        print(val_cm)
        
        #----------------------------------------------------
        print("auc: ",np.mean(au))
        print('Epoch: ' , str(epoch) , \
              '\ttrain_loss: '+str(round(train_loss/(step+1),4)),\
              '\ttrain_acc: '+str(round(acc,4)),\
              '\trecall: '+str(round(recall,4)),\
#               '\tspecificity: '+str(round(np.mean(speci),4)),\
              '\tval_loss: '+str(round(val_loss,4)),\
              '\tval_acc: '+str(round(v_acc,4)) ,\
              '\tval_recall: '+str(round(val_recall,4)) ,\
        )
        chart_data['epoch'].append(epoch)
        chart_data['train_loss'].append(train_loss/(step+1))
        chart_data['val_loss'].append(val_loss)
        chart_data['train_acc'].append(acc)
        chart_data['val_acc'].append(v_acc)

draw_chart(chart_data,model_name)

plot_confusion_matrix(val_cm,'val')

plot_confusion_matrix(cm,'train')
