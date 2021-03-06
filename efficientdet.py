import sys
import torch
import json
import numpy as np
import pandas as pd
from pandas import Series
import matplotlib.pyplot as plt
import torchvision.transforms as transforms
from PIL import Image
from torch import nn, optim
from torch.utils.data import Dataset, DataLoader,ConcatDataset
from sklearn.model_selection import train_test_split
import skimage
from skimage import data, exposure, img_as_float
import torchvision
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor, FasterRCNN
from torchvision.models.detection.backbone_utils import resnet_fpn_backbone
import os
from tqdm import tqdm
from sklearn.model_selection import KFold,GroupKFold
from torch.utils.data.sampler import SequentialSampler, RandomSampler

import albumentations as A
from albumentations.pytorch import ToTensorV2
import cv2

class covid_Dataset(Dataset):

    def __init__(self,df,data,train=True,transform=None):
        self.df = data
        self.original_data = df
        self.gender = ['M','F']
        self.train = train
        self.image_ids = self.df['id'].unique()
        self.transform = transform
#         self.image_ids = image_ids
    def __getitem__(self,index):

        patient_id,study,box_count,category,sex,body_part,rows,columns,_,_,_,_,xmin,ymin,xmax,ymax,label = self.df.iloc[index].values
#         img = Image.open('/kaggle/input/image256/train/'+patient_id+'.jpg')
        img = cv2.imread('/kaggle/input/image256/train/'+self.image_ids[index]+'.jpg')
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)
        img = img/255.0
        shape = img.shape
        
        records = self.original_data[self.original_data['id'] == self.image_ids[index]] 
        boxes = records[['rxmin', 'rymin', 'rxmax', 'rymax']].values
        box = []
        for i in boxes:
            rxmin = [i[0]/shape[1]]
            rymin = [i[1]/shape[0]]
            rxmax = [i[2]/shape[1]]
            rymax = [i[3]/shape[0]]
            box.append(rxmin+rymin+rxmax+rymax)
        boxes = []
        for i in box:
            i = np.clip(i,0,1.0)
            temp = A.convert_bbox_from_albumentations(i, 'pascal_voc', img.shape[0], img.shape[1]) 
            boxes.append(temp)

        labels = np.ones((len(box), ))
        
        target = {}
        target['boxes'] = torch.tensor(boxes)
        target['labels']=torch.from_numpy(labels).type(torch.int64)
        target['image_id'] = torch.tensor([index])
        
        if self.transform:            
            image_transforms = {
                                'image': img,
                                'bboxes': target['boxes'],
                                'labels': labels
                                 }
            image_transforms = self.transform(**image_transforms)
            if len(image_transforms['bboxes']) > 0:
                image = image_transforms['image']
                target['boxes'] = torch.stack(tuple(map(torch.tensor, zip(*image_transforms['bboxes'])))).permute(1, 0)
                target['boxes'][:,[0,1,2,3]] = target['boxes'][:,[1,0,3,2]] #yxyx
        return image, target

        # -------------- check transform of images --------------
        #transforms.ToPILImage()(image_tensor['image']).convert('L').save('./'+patient_id+'.jpg')
    
    def __len__(self):
        return len(self.image_ids)

class FasterRCNNDetector(torch.nn.Module):
    def __init__(self, pretrained=False, **kwargs):
        super(FasterRCNNDetector, self).__init__()
        # load pre-trained model incl. head
        self.model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=pretrained, pretrained_backbone=pretrained)
        # get number of input features for the classifier custom head
        in_features = self.model.roi_heads.box_predictor.cls_score.in_features
        # replace the pre-trained head with a new one
        self.model.roi_heads.box_predictor = FastRCNNPredictor(in_features, 4)
        
    def forward(self, images, targets=None):
        return self.model(images, targets)

!pip install --no-deps '../input/timm-package/timm-0.1.26-py3-none-any.whl' > /dev/null
!pip install --no-deps '../input/pycocotools/pycocotools-2.0-cp37-cp37m-linux_x86_64.whl' > /dev/null

import sys
sys.path.insert(0, "../input/timmefficienctdetpytorchstable/archive")
sys.path.insert(0, "../input/omegaconf")
import torch.nn.functional as F
import traceback
from torch import optim
from effdet import *
from effdet.efficientdet import HeadNet
from effdet import get_efficientdet_config, EfficientDet, DetBenchTrain
from effdet.anchors import Anchors, AnchorLabeler, generate_detections, MAX_DETECTION_POINTS
from effdet.loss import DetectionLoss

class EfficientDetTrainer(torch.nn.Module):
    
    def __init__(self, model, config, device):
        
        super(EfficientDetTrainer, self).__init__()
        self.model = model
        self.config = config
        self.my_anchors = Anchors(
                config.min_level, config.max_level,
                config.num_scales, config.aspect_ratios,
                config.anchor_scale, config.image_size, device)
        self.a = AnchorLabeler(self.my_anchors, 1, match_threshold=0.5)
        self.loss_fn = DetectionLoss(config)     
            
    def forward(self,x,boxes,clses):
        class_out_, box_out_ = self.model(x)
        class_out, box_out, indices, classes = _post_process(self.config, class_out_, box_out_)
        cls_targets = []
        box_targets = []
        num_positives = []
        batch_detections = []  
        for i in range(x.shape[0]):
            detections = generate_detections(
                class_out[i], box_out[i], self.my_anchors.boxes, indices[i], classes[i], torch.Tensor(np.ones(1)).to(device))
            batch_detections.append(detections)
            gt_class_out, gt_box_out, num_positive = self.a.label_anchors(boxes[i], clses[i])
            cls_targets.append(gt_class_out)
            box_targets.append(gt_box_out)
            num_positives.append(num_positive)
        loss, class_loss, box_loss = self.loss_fn(class_out_, box_out_, cls_targets, box_targets, num_positives)
        return loss,torch.stack(batch_detections, dim=0)

def get_efficientDet():
    
    config = get_efficientdet_config('tf_efficientdet_d1')
    net = EfficientDet(config, pretrained_backbone=False)
    config.num_classes = 1
    config.image_size = 256
    net.class_net = HeadNet(config, num_outputs=config.num_classes, norm_kwargs=dict(eps=.001, momentum=.01))
    return net, config

model, config = get_efficientDet()

def _post_process(config, cls_outputs, box_outputs):
    """Selects top-k predictions.

    Post-proc code adapted from Tensorflow version at: https://github.com/google/automl/tree/master/efficientdet
    and optimized for PyTorch.

    Args:
        config: a parameter dictionary that includes `min_level`, `max_level`,  `batch_size`, and `num_classes`.

        cls_outputs: an OrderDict with keys representing levels and values
            representing logits in [batch_size, height, width, num_anchors].

        box_outputs: an OrderDict with keys representing levels and values
            representing box regression targets in [batch_size, height, width, num_anchors * 4].
    """

    batch_size = cls_outputs[0].shape[0]
    cls_outputs_all = torch.cat([
        cls_outputs[level].permute(0, 2, 3, 1).reshape([batch_size, -1, config.num_classes])
        for level in range(config.num_levels)], 1)
    
    box_outputs_all = torch.cat([
        box_outputs[level].permute(0, 2, 3, 1).reshape([batch_size, -1, 4])
        for level in range(config.num_levels)], 1)

    _, cls_topk_indices_all = torch.topk(cls_outputs_all.reshape(batch_size, -1), dim=1, k=MAX_DETECTION_POINTS)
    indices_all = cls_topk_indices_all / config.num_classes
    classes_all = cls_topk_indices_all % config.num_classes

    indices_all = indices_all.type(torch.long)

    box_outputs_all_after_topk = torch.gather(
        box_outputs_all, 1, indices_all.unsqueeze(2).expand(-1, -1, 4))

    cls_outputs_all_after_topk = torch.gather(
        cls_outputs_all, 1, indices_all.unsqueeze(2).expand(-1, -1, config.num_classes))

    cls_outputs_all_after_topk = torch.gather(
        cls_outputs_all_after_topk, 2, classes_all.unsqueeze(2))

    return cls_outputs_all_after_topk, box_outputs_all_after_topk, indices_all, classes_all

    
def post_process_outputs(output, width, height):
    for z in range(0,len(output)):
        #Returns Values as xywh. Sort this out
        output[z][:,0] = output[z][:,0] * width[z]/256
        output[z][:,1] = output[z][:,1] * height[z]/256 
        output[z][:,2] = output[z][:,2] * width[z]/256 
        output[z][:,3] = output[z][:,3] * height[z]/256
        output[z,:,3] = output[z,:,3] + output[z,:,1]
        output[z,:,2] = output[z,:,2] + output[z,:,0]
    return output

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

def label(df):
    label = []
    for i in df['category']:
        if i=='Negative':
            label.append(0)
        elif i =='Typical':
            label.append(1)
        elif i == 'Indeterminate':
            label.append(2)
        else:
            label.append(3)
    return label

def draw_bbox(image, box, label, color):   
    alpha = 0.4
    alpha_font = 0.6
    thickness = 4
    font_size = 2.0
    font_weight = 2
    overlay_bbox = image.copy()
    overlay_text = image.copy()
    output = image.copy()

    text_width, text_height = cv2.getTextSize(label.upper(), cv2.FONT_HERSHEY_SIMPLEX, font_size, font_weight)[0]
    cv2.rectangle(overlay_bbox, (box[0], box[1]), (box[2], box[3]),
                color, -1)
    cv2.addWeighted(overlay_bbox, alpha, output, 1 - alpha, 0, output)
    cv2.rectangle(overlay_text, (box[0], box[1]-18-text_height), (box[0]+text_width+8, box[1]),
                (0, 0, 0), -1)
    cv2.addWeighted(overlay_text, alpha_font, output, 1 - alpha_font, 0, output)
    cv2.rectangle(output, (box[0], box[1]), (box[2], box[3]),
                    color, thickness)
    cv2.putText(output, label.upper(), (box[0], box[1]-12),
            cv2.FONT_HERSHEY_SIMPLEX, font_size, (255, 255, 255), font_weight, cv2.LINE_AA)
    return output

!pip3 install ensemble_boxes

from ensemble_boxes import *
def run_wbf(bbox,predictions, image_index, image_size=256, iou_thr=0.14, skip_box_thr=0.13, weights=None):
    boxes = [(prediction[image_index]['boxes']/(image_size-1)).tolist()  for prediction in predictions]
    scores = [prediction[image_index]['scores'].tolist()  for prediction in predictions]
    labels = [np.ones(prediction[image_index]['scores'].shape[0]).tolist() for prediction in predictions]
    boxes, scores, labels = nms(boxes, scores, labels, weights=None, iou_thr=iou_thr)
    boxes = boxes*(image_size-1)
    for score,box in zip(scores,boxes):
        box = np.insert(box,0,str(image_index))
        box = np.insert(box,1,score)
        bbox.append(list(box))
    return boxes, scores, labels

from collections import Counter
def mean_average_precision(pred_bboxes,true_boxes,iou_threshold=0.1,num_classes=1):
    
    #pred_bboxes(list): [[train_idx,class_pred,prob_score,x1,y1,x2,y2], ...]
    
    average_precisions=[]
    epsilon=1e-6
    
    for c in range(num_classes):
        detections=[]
        ground_truths=[]
        
        for detection in pred_bboxes:
            detections.append(detection)
        
        for true_box in true_boxes:
            ground_truths.append(true_box)


        amount_bboxes=Counter(gt[0] for gt in ground_truths)
        amount = {}
        for key,val in amount_bboxes.items():
            amount[key]=torch.zeros(val,dtype=torch.float64)
        #amount_bboxes={0:torch.tensor([0,0,0]),1:torch.tensor([0,0,0,0,0])}
        detections.sort(key=lambda x:x[1],reverse=True)
        
        #initialize TP,FP
        TP=torch.zeros(len(detections))
        FP=torch.zeros(len(detections))
        

        total_true_bboxes=len(ground_truths)
        
        if total_true_bboxes == 0:
            continue

        for detection_idx,detection in enumerate(detections):
            ground_truth_img=[bbox for bbox in ground_truths if bbox[0]==detection[0]]
            num_gts=len(ground_truth_img)
            
            best_iou=0
            best_gt_idx = 0
            for idx,gt in enumerate(ground_truth_img):
                iou=insert_over_union(torch.tensor(detection[2:]),torch.tensor(gt[1:]))
                if iou >best_iou:
                    best_iou=iou
                    best_gt_idx=idx
            if best_iou>iou_threshold:
                detection[0] = torch.tensor(detection[0],dtype=torch.int32)
                if amount[int(detection[0])][best_gt_idx]==0:
                    TP[detection_idx]=1
                    amount[int(detection[0])][best_gt_idx]=1
                else:
                    FP[detection_idx]=1
            else:
                FP[detection_idx]=1
                
        TP_cumsum=torch.cumsum(TP,dim=0)
        FP_cumsum=torch.cumsum(FP,dim=0)
        
        recalls=TP_cumsum/(total_true_bboxes+epsilon)
        precisions=torch.divide(TP_cumsum,(TP_cumsum+FP_cumsum+epsilon))
        
        precisions=torch.cat((torch.tensor([1]),precisions))
        recalls=torch.cat((torch.tensor([0]),recalls))
        #use trapz to calculate AP
        average_precisions.append(torch.trapz(precisions,recalls))
        
    return sum(average_precisions)/len(average_precisions) 
 
def insert_over_union(boxes_preds,boxes_labels):
    
    box1_x1=boxes_preds[...,0:1]
    box1_y1=boxes_preds[...,1:2]
    box1_x2=boxes_preds[...,2:3]
    box1_y2=boxes_preds[...,3:4]#shape:[N,1]
    
    box2_x1=boxes_labels[...,0:1]
    box2_y1=boxes_labels[...,1:2]
    box2_x2=boxes_labels[...,2:3]
    box2_y2=boxes_labels[...,3:4]
    
    x1=torch.max(box1_x1,box2_x1)
    y1=torch.max(box1_y1,box2_y1)
    x2=torch.min(box1_x2,box2_x2)
    y2=torch.min(box1_y2,box2_y2)
    
    
    #count
    intersection=(x2-x1).clamp(0)*(y2-y1).clamp(0)
    
    box1_area=abs((box1_x2-box1_x1)*(box1_y1-box1_y2))
    box2_area=abs((box2_x2-box2_x1)*(box2_y1-box2_y2))
    
    return intersection/(box1_area+box2_area-intersection+1e-6)

def validation(loader,model,epoch):
    loss = 0.0
    predictions = []
    ap_1 = []
    ap_2 = []
    ap_3 = []
    ap_5 = []
    with torch.no_grad():
        model.eval()
        for step_, (batch) in enumerate(loader):
            images = list(image.to(device) for image in batch[0])
            targets = [{k: v.to(device) for k, v in t.items()} for t in batch[1]]

            boxes = [t['boxes'].float() for t in targets]
            classes = [t['labels'].float() for t in targets]
            inputs = torch.stack(images)
            loss_dict,output = trainer(inputs,boxes,classes)
            loss += loss_dict.item()
            
            bbox = []
            true_bbox = []
            for i in range(4):

                boxes = output[i].detach().cpu().numpy()[:,:4] 
                scores = output[i].detach().cpu().numpy()[:,4]
                indexes = np.where(scores > 0.25)[0]
                boxes = boxes[indexes]
                
                boxes[:, 2] = boxes[:, 2] + boxes[:, 0]
                boxes[:, 3] = boxes[:, 3] + boxes[:, 1]
                
                predictions.append({
                    'boxes': boxes,
                    'scores': scores[indexes],
                })

                sample = images[i].permute(1,2,0).cpu().numpy()
#                 boxes, scores, labels = run_wbf(bbox,[predictions], image_index=i)
                boxes = boxes.astype(np.int32).clip(min=0, max=255)
                for score,box in zip(scores[indexes],boxes):
                    box = np.insert(box,0,str(i))
                    box = np.insert(box,1,score)
                    bbox.append(list(box))
                #--------true boxes--------
                draw_bboxes = targets[i]['boxes'].cpu().numpy().astype(np.int32)
                targets[i]['boxes'][:,[0,1,2,3]] = targets[i]['boxes'][:,[1,0,3,2]]
                boxes_ = targets[i]['boxes'].cpu().numpy().astype(np.int32)

                for box in boxes_:
                    box = np.insert(box,0,str(i))
                    true_bbox.append(list(box))
                #--------draw boxes---------
                if step_ % 2 == 1:
                    print(boxes_)
                    print('--------------')
                    print(boxes)
                    print(scores[indexes])
                    numpy_image = batch[0][i].permute(1,2,0).cpu().numpy()
                    fig2, (ax1,ax2) = plt.subplots(1, 2,figsize=(16, 8))

                    for box in draw_bboxes:
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        cv2.rectangle(numpy_image, (box[1], box[0]), (box[3],  box[2]), (0, 255, 0), 2)
                        
                    ax1.imshow(numpy_image,cmap='gray');

                    for box,score in zip(boxes,scores[indexes]):
                        cv2.rectangle(sample, (box[0], box[1]), (box[2], box[3]), (1,0, 0), 2)
                        cv2.putText(sample,str(score), (box[0], box[1]), font, 0.5, (1, 1, 1), 1)
                    ax2.set_axis_off()
                    ax2.imshow(sample)
                    plt.show()
            ap_1.append(mean_average_precision(torch.tensor(bbox),true_bbox))
            ap_2.append(mean_average_precision(torch.tensor(bbox),true_bbox,0.2))
            ap_3.append(mean_average_precision(torch.tensor(bbox),true_bbox,0.3))
       #--------map----------------
#         print('=======================')
#         print(bbox)
#         ap_1.append(mean_average_precision(torch.tensor(bbox),torch.tensor(true_bbox)))
#         ap_2.append(mean_average_precision(torch.tensor(bbox),torch.tensor(boxes_),iou_threshold=0.2))
#         ap_3.append(mean_average_precision(torch.tensor(bbox),torch.tensor(boxes_),iou_threshold=0.3))
#         ap_5.append(mean_average_precision(torch.tensor(bbox),torch.tensor(boxes_),iou_threshold=0.5)) 
        print('=================================================')            
        print("mAP_0.1: ",np.mean(ap_1))
        print("mAP_0.2: ",np.mean(ap_2))
        print("mAP_0.3: ",np.mean(ap_3))
        print("mAP_0.5: ",np.mean(ap_5))
    return loss/(step_+1),output

if __name__ == '__main__':
    # print(torch.cuda.get_device_name(0))
    # -------------- hyper parameter --------------
    batch_size = 16
    learning_rate = 0.001
    model_name = 'efficientdet_model'
    # ------------------------------------------
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # -------------- split data --------------
    df = pd.read_csv("/kaggle/input/covid19-dataset/covid19.csv")
    df2 = pd.read_csv("/kaggle/input/covid-dataset/COVID19_data_.csv")
    df['label'] = label(df)
    opacity = df["rxmax"]>0.3
    df = df[opacity]
    df.index = Series(range(len(df)))
    # ------------------------------------------
    train_transform = A.Compose(
    [   A.Resize(256,256),
#         A.RandomSizedCrop([224,224],256,256),
        A.HorizontalFlip(p=0.5),
#         A.RandomRotate90(always_apply=False, p=0.5),
        A.OneOf([
        A.HueSaturationValue(hue_shift_limit=0.2, sat_shift_limit= 0.2, 
                             val_shift_limit=0.2, p=0.7 ),
        A.RandomBrightnessContrast(brightness_limit=0.2, 
                                   contrast_limit=0.2, p=0.7),
        ],p=0.9),
        A.Cutout(num_holes=8, max_h_size=16, max_w_size=16, fill_value=0, p=0.5),
#         A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225], max_pixel_value=255.0, p=1.0),
        ToTensorV2(),
    ],bbox_params=A.BboxParams(format= 'pascal_voc', min_area=0, min_visibility=0, label_fields= ['labels']))
    val_transform = A.Compose(
    [   A.Resize(256,256),
#         A.RandomSizedCrop([224,224],256,256),
        ToTensorV2(),
    ],bbox_params=A.BboxParams(format= 'pascal_voc', min_area=0, min_visibility=0, label_fields= ['labels']))
    
    # -------------- prepare training and testing data --------------
    # -------------- 5fold --------------
    results = {}
    kf = KFold(n_splits=5,random_state=42,shuffle=True)
    kfold = GroupKFold(n_splits=5)
    kfold.get_n_splits(df,np.array([range(len(df))]), np.array(df['id']))
    for fold, (train_ids, test_ids) in enumerate(kf.split(df)):
        print('--------------------------------')
        print(f'FOLD {fold}')
        print('--------------------------------')
        print(train_ids)
        print(test_ids)
        train_pos = df.loc[train_ids,]
        val_pos = df.loc[test_ids,]
        train_set = covid_Dataset(df,train_pos,train=True,transform=train_transform)
        test_set = covid_Dataset(df,val_pos,train=False,transform = val_transform)
        train_loader = DataLoader(train_set,batch_size=batch_size,collate_fn=lambda x:list(zip(*x)),drop_last=True)
        test_loader = DataLoader(test_set,batch_size=4,collate_fn=lambda x:list(zip(*x)),drop_last=True,shuffle=True)

        # -------------- model --------------
        model = model.to(device)
        trainer = EfficientDetTrainer(model, config, device)

        # -------------- create optimizer and loss function --------------
        optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate,weight_decay=1e-3)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.1, 
                                           patience=3, threshold=0.0001, threshold_mode='rel', 
                                           cooldown=0, min_lr=0, eps=1e-08, verbose=False)
        # -------------- init data for image --------------
        chart_data={"train_loss":[],"val_acc":[],"train_acc":[],"val_loss":[],"train_recall":[],"epoch":[],"f1":[],"f1_val":[]}
        best_loss = 99999
        for epoch in range(10):
            model.train()
            current_loss = 0.0
            batch_loss = 0.0
            IOU = 0
            predictions = []
            loss_ = []
            for step, (batch) in enumerate(tqdm(train_loader)):
                images = list(image.to(device) for image in batch[0])
                targets = [{k: v.to(device) for k, v in t.items()} for t in batch[1]]
                boxes = [t['boxes'].float() for t in targets]
                classes = [t['labels'].float() for t in targets]
                inputs = torch.stack(images)
                loss_dict,output = trainer(inputs,boxes,classes)
                batch_loss += loss_dict.item()
                current_loss += loss_dict.item()

#                 bbox = []
#                 for i in range(batch_size):
#                     boxes = output[i].detach().cpu().numpy()[:,:4] 
#                     scores = output[i].detach().cpu().numpy()[:,4]
#                     indexes = np.where(scores > 0.1)[0]
#                     boxes = boxes[indexes]
#                     boxes[:, 2] = boxes[:, 2] + boxes[:, 0]
#                     boxes[:, 3] = boxes[:, 3] + boxes[:, 1]
#                     predictions.append({
#                         'boxes': boxes[indexes],
#                         'scores': scores[indexes],
#                     })
# #                     boxes, scores, labels = run_wbf(bbox,[predictions], image_index=i)
#                     boxes = boxes.astype(np.int32).clip(min=0, max=255)
#                     #--------true boxes--------
#                     targets[i]['boxes'][:,[0,1,2,3]] = targets[i]['boxes'][:,[1,0,3,2]]
#                     boxes_ = targets[i]['boxes'].cpu().numpy().astype(np.int32)
#                     for j in range(len(boxes_)):   
#                         loss = Ciou_loss(torch.tensor(boxes.tolist()),torch.tensor([boxes_[j]]))
#                         loss_.append(loss)
#                 a = torch.tensor(np.mean(loss_),device=device,requires_grad=True)
#                 batch_loss += a.item()
#                 current_loss += a.item()
                loss_dict.backward()
                optimizer.step()
                optimizer.zero_grad()
                if step % 100 == 99:
                    print('Loss after mini-batch %5d: %.3f' %
                          (step + 1, current_loss / 100))
                    current_loss = 0.0            
            # -------------- validation --------------
            epoch_loss,box_targets = validation(tqdm(test_loader),trainer,-1)
            scheduler.step(epoch_loss)
            print(learning_rate)
            print('=================================================')
            
            # -------------- draw predictions --------------
#             for i in range(batch_size):

#                 boxes = targets[i]['boxes'].cpu().numpy().astype(np.int32)
#                 print(boxes)
#                 numpy_image = batch[0][i].permute(1,2,0).cpu().numpy()
#                 fig2, (ax1,ax2) = plt.subplots(1, 2,figsize=(16, 8))

#                 for box in boxes:
#                     cv2.rectangle(numpy_image, (box[1], box[0]), (box[3],  box[2]), (0, 255, 0), 2)

#                 ax1.imshow(numpy_image,cmap='gray');

#                 boxes = output[i].detach().cpu().numpy()[:,:4]    
#                 scores = output[i].detach().cpu().numpy()[:,4]
#                 indexes = np.where(scores > 0.15)[0]
#                 boxes = boxes[indexes]
#                 boxes[:, 2] = boxes[:, 2] + boxes[:, 0]
#                 boxes[:, 3] = boxes[:, 3] + boxes[:, 1]
#                 predictions.append({
#                     'boxes': boxes[indexes],
#                     'scores': scores[indexes],
#                 })

#                 sample = images[i].permute(1,2,0).cpu().numpy()

#                 boxes, scores, labels = run_wbf([predictions], image_index=i)
#                 boxes = boxes.astype(np.int32).clip(min=0, max=255)


#                 for box in boxes:
#                     cv2.rectangle(sample, (box[0], box[1]), (box[2], box[3]), (1,0, 0), 2)

#                 ax2.set_axis_off()
#                 ax2.imshow(sample)
#                 plt.show()
            
            # -------------- store weights --------------
            if epoch_loss < best_loss:
                best_loss = epoch_loss
                torch.save(model.state_dict(), './weights-fold'+str(fold)+'.pth')

            # -------------------------------------------   
            print("Epoch: ",epoch)
            print("Loss_Train = {:.4f} ".format(batch_loss/(step+1)))
            print("Loss_Test = {:.4f} ".format(epoch_loss))
            chart_data['epoch'].append(epoch)
            chart_data['train_loss'].append(batch_loss/(step+1))
            chart_data['val_loss'].append(epoch_loss)
        draw_chart(chart_data,"1")