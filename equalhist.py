import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from skimage import data, exposure, img_as_float
import skimage
import matplotlib as mpl

def display_image_in_actual_size(img):
    dpi = mpl.rcParams['figure.dpi']
    height, width = img.shape

    # What size does the figure need to be in inches to fit the image?
    figsize = width / float(dpi), height / float(dpi)

    # Create a figure of the right size with one axes that takes up the full figure
    fig = plt.figure(figsize=figsize)
    ax = fig.add_axes([0, 0, 1, 1])

    # Hide spines, ticks, etc.
    ax.axis('off')

    # Display the image.
    ax.imshow(img, cmap='gray')
    plt.savefig('/Users/dodo/Desktop/COVID19/test_equalhist/'+i+ '.jpg')
    # plt.show()

df = pd.read_csv("/Users/dodo/Desktop/COVID19/name.csv")
for i in df['image']:
    img = Image.open('/Users/dodo/Desktop/COVID19/test/'+str(i))
    img = img_as_float(img)
#     plt.subplot(121)
#     plt.imshow(img,cmap='gray')
    img = skimage.exposure.equalize_hist(img)
    display_image_in_actual_size(img)


# def myHistEq(img):
#     hist,bins = np.histogram(img.ravel(),256,[0,255])
#     #print("hist=\n",hist) //testing
#     #print("bins=\n",bins) //testing
    
#     pdf = hist/img.size #hist = 出現次數。出現次數/總像素點 = 概率 (pdf)
#     #print("pdf=\n",pdf) //testing
    
#     cdf = pdf.cumsum() # 將每一個灰度級的概率利用cumsum()累加，變成書中寫的「累積概率」(cdf)。
#     #print("cdf=\n",cdf) //testing 
    
#     equ_value = np.around(cdf * 255).astype('uint8') #將cdf的結果，乘以255 (255 = 灰度範圍的最大值) ，再四捨五入，得出「均衡化值(新的灰度級)」。
#     #print("equ_value=\n",equ_value) //testing
#     result = equ_value[img]
#     return result

# import cv2
# #start of plt.figure()
# plt.figure(figsize=(20,30))

# #(plt_1) Original Image - RGB    (plt_2) Empty
# # plt.subplot(5,2,1) 
# img_bgr = cv2.imread("/Users/dodo/Desktop/COVID19/train/0a0cbc610620.jpg",cv2.IMREAD_COLOR) #OpenCV default get the BGR Format                         

# #(plt_3) Original Image - Gray 
# img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)   #Convert BGR to Gray
# mydst = myHistEq(img_gray)   #這是我們自己設計的 Histogram Equalization 函數  defined on (line#1 - line#15)
# cvdst = cv2.equalizeHist(img_gray) #cv2.equalizeHist()是 OpevCV 內建的 Histogram Equalization 函數
# sse = np.sum((mydst-cvdst)**2)

# # plt.subplot(5,2,4)
# # plt.title("Histrogram - (Gray) Original Image")
# # plt.hist(img_gray.ravel(),bins=256,range=(0,255))

# # #(plt_6) After Processing Image - Gray
# # plt.subplot(5,2,6)
# plt.title("After Equalization Histrogram - Gray (mydst)")
# plt.hist(mydst.ravel(),bins=256,range=(0,255),color='b')


# # #(plt_8)
# # plt.subplot(5,2,8)
# # plt.title("After Equalization Histrogram - Gray (cvdst)")
# # plt.hist(cvdst.ravel(),bins=256,range=(0,255),color='r')

# # #(plt_9)
# # plt.subplot(5,2,9)
# # plt.hist(mydst.ravel(),bins=256,range=(0,255),color='b')
# # plt.hist(cvdst.ravel(),bins=256,range=(0,255),color='g')

# # plt.title("Overlapping Contrast\n Sum Of Squared Error: "+ str(sse))

# plt.show()
# # plt.close()
# # #end of plt.figure()