# Covid19_kaggle

https://www.kaggle.com/competitions/siim-covid19-detection/overview

## Objective

Identifying and localizing COVID-19 abnormalities on chest radiographs

For each test image：predict a bounding box and class for all findings

For each test study：make a determination within the following labels (Negative for Pneumonia/Typical Appearance/Indeterminate Appearance/Atypical) Appearance

## Classification

### Data preprocessing

1. Resize, CenterCrop

2. Augmentation

Before / After

<img width="300" alt="image" src="https://user-images.githubusercontent.com/77607182/178152795-5aa34627-e761-4467-940b-b137aacac20c.png"><img width="150" alt="image" src="https://user-images.githubusercontent.com/77607182/178152801-3c45791c-533b-4459-bdc6-17a23be7c314.png">

3. Deal with unbalanced data: weighted sampler

### Model: EfficientNet(2019)

### Highest AUC in 5 fold: 0.745

## Object detection

### Data preprocessing

1. Histogram equalization

2. Resize images

3. Drop the images with no true boxxes

4. Augmentation

Before / After
<img width="300" alt="image" src="https://user-images.githubusercontent.com/77607182/178152769-2276f86c-efa3-47c0-8cce-217f698a3594.png"><img width="150" alt="image" src="https://user-images.githubusercontent.com/77607182/178152777-65e14188-1496-45fa-96e6-cdf52f491ab3.png">

### Model: EfficientDet (2019)

Original / Prediction

<img width="400" alt="image" src="https://user-images.githubusercontent.com/77607182/178152870-e1f0ed75-d5bd-427e-80f8-0fc61595712b.png">
<img width="400" alt="image" src="https://user-images.githubusercontent.com/77607182/178152875-82b5208f-28b9-4f60-ae1c-45bbbc9ceefa.png">
<img width="400" alt="image" src="https://user-images.githubusercontent.com/77607182/178152879-7bfb574c-af82-4467-afe4-cff5acfbbba5.png">

### Highest map@0.5 in 5 fold: 0.65
