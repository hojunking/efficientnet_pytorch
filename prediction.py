import torch
import sys
from torch import nn
import os
import random
import numpy as np
import pandas as pd

from torchvision import transforms
from torch.utils.data import Dataset,DataLoader
import sklearn
from sklearn.metrics import log_loss
from sklearn.metrics import confusion_matrix
import timm
import cv2
from sklearn.preprocessing import LabelEncoder
import torch.distributed as dist
import torch.multiprocessing as mp
from apex.parallel import DistributedDataParallel as DDP
import albumentations as A
from albumentations.pytorch import ToTensorV2
from tqdm import tqdm
import warnings

###################################################################



warnings.filterwarnings(action='ignore') 
###### Multi GPU init
os.environ["CUDA_VISIBLE_DEVICES"] = '0, 1' #본인이 사용하고 싶은 GPU 넘버를 써주면 됨
os.environ['MASTER_ADDR'] = 'localhost'
os.environ['MASTER_PORT'] = '53097'         # 좀 큰 숫자로 맞추면 됨 작은 숫자는 에러발생!

#device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# init!
torch.distributed.init_process_group(backend='nccl', init_method="env://", rank =0, world_size=1)  # rank should be 0 ~ world_size-1

CFG = {
    'model': 'tf_efficientnet_b4_ns',
    'img_size': 380,
    'bs': 16,
    'seed': 0,
    'device': 'cuda:0',
    'img_dir': 'test_data/',
    'num_workers': 0
}


def seed_everything(seed):
    random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = True

def get_img(path):
    im_bgr = cv2.imread(path)
    im_rgb = im_bgr[:, :, ::-1]
    #print(im_rgb)
    return im_rgb
    
    
class get_transformed_img(Dataset):
    def __init__(
        self, df, data_root, transforms=None):
        
        super().__init__()
        self.df = df.reset_index(drop=True).copy()
        self.transforms = transforms
        self.data_root = data_root
    
    def __len__(self):
        return self.df.shape[0]
    
    def __getitem__(self, index: int):
          
        path = "{}/{}".format(self.data_root, self.df.iloc[index]['image_id'])
        #path = "{}/{}".format(self.data_root[index], self.df.iloc[index]['image_id'])
        img  = get_img(path)
        
        if self.transforms:
            img = self.transforms(image=img)['image']
            
        return img    
    

def get_inference_transforms():
     return A.Compose([
#            A.Resize(CFG['img_size']+200, CFG['img_size']+500),
#            A.CenterCrop(always_apply=True,p=1.0, height=CFG['img_size'], width=CFG['img_size']),
            A.RandomResizedCrop(
            height=CFG['img_size'], 
            width=CFG['img_size'], 
            scale=(4.80, 9.90),
            ratio=(0.90, 1.10),
            always_apply=True
            ),
#            A.Transpose(p=0.5),
#            A.HorizontalFlip(p=0.5),
            A.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225], max_pixel_value=255.0, p=1.0),
            ToTensorV2(p=1.0),
        ], p=1.)

##### get model
class ColonImgClassifier(nn.Module):
    def __init__(self, model_arch, n_class=2, pretrained=False):
        super().__init__()
        self.model = timm.create_model(model_arch, pretrained=pretrained, num_classes=n_class)
        try :
            n_features = self.model.classifier.in_features
            self.model.classifier = nn.Linear(n_features, n_class)

        except :
            
            try : 
                n_features = self.model.fc.in_features
                self.model.fc = nn.Linear(n_features, n_class)
            
            except :
                try:
                    n_features = self.model.head.fc.in_channels
                    self.model.head.fc = nn.Conv2d(n_features,n_class,kernel_size=(1, 1), stride=(1, 1))
            
                except:
                    n_features = self.model.head.in_features
                    self.model.head = nn.Linear(n_features, n_class)
            
    def forward(self, x):
        x = self.model(x)
        return x

########################## inference #############################
##########################           #############################
def inference(model, data_loader, device):
    model.eval()
    image_preds_all = []
    
    pbar = tqdm(enumerate(data_loader), total=len(data_loader))
    for step, (imgs) in pbar:
        imgs = imgs.to(device).float()

        image_preds = model(imgs)   #output = model(input)
        image_preds_all += [torch.softmax(image_preds, 1).detach().cpu().numpy()]
    
    image_preds_all = np.concatenate(image_preds_all, axis=0)
    return image_preds_all




########################## main ##################################
##########################      ##################################
#model_dir = 'tf_efficientnet_b4_ns_ALL/tf_efficientnet_b4_ns_2'
model_dir = 'models/1214'




if __name__ == '__main__':
    seed_everything(CFG['seed'])
    
    arguments = sys.argv
    del arguments[0]
    
    #img_name = arguments
    img_name = ['모닝_2017.jpg',
 'K3_2021.jpg',
 'K9_2020.jpg',
 '아반떼_2017.jpg',
 'EQ900_2018.jpg',
 '그랜저_2019.jpg',
 'G70_2017.jpg',
 '니로_2017.jpg',
 '아반떼_2019.01.jpg',
 '카니발_2019.jpg',
 'K3_2017.jpg',
 'K3_2020.jpg',
 'K9_2019.jpg',
 'K5_2017.jpg',
 '스토닉_2018.jpg',
 'K5_2019.jpg',
 '투싼_2018.jpg',
 '아반떼_2019.jpg',
 '셀토스_2021.jpg',
 '레이_2020.jpg',
 '팰리세이드_2021.jpg',
 '싼타페_2018.jpg',
 'G70_2019.jpg',
 '스타렉스_2018.jpg',
 '스팅어_2019.jpg',
 '아반떼_2021.jpg',
 '쏘나타_2018.jpg',
 '스타렉스_2019.jpg',
 'G80_2021.jpg',
 '싼타페_2019.jpg',
 'K7_2018.jpg',
 '쏘렌토_2017.jpg',
 '쏘나타_2017.jpg',
 '모닝_2018.jpg',
 '그랜저.2018.jpg',
 '투싼_2020.jpg',
 '쏘나타_2021.jpg',
 '그랜저_2017.jpg',
 '니로_2018.jpg',
 '포터2_2017.jpg']
    #print(img_name)
    img_dir = CFG['img_dir']
    #path = img_dir + img_name
    
    
    
    infer = pd.DataFrame(columns = ['image_id'])
    infer['image_id'] = img_name
    
    ############## for test accuracy #####################
    infer['label'] = [i.replace('_','/').split('.',1)[0] for i in img_name]
    
    
    ################## get img ###########################
    pred_ds = get_transformed_img(infer, img_dir, transforms=get_inference_transforms())
    pred_loader = torch.utils.data.DataLoader(
        pred_ds, 
        batch_size=CFG['bs'],
        num_workers=CFG['num_workers'],
        shuffle=False,
        pin_memory=True
    )
    
    ################## model init ########################
    device = torch.device(CFG['device'])
    model = ColonImgClassifier(CFG['model'], 95).to(device)
    if torch.cuda.device_count() > 1:
        model = nn.DataParallel(model)
    
    model.to(device)
    model = DDP(model)
    
    
    ################## get inference #####################
    predictions = []
    model.load_state_dict(torch.load(model_dir))
    with torch.no_grad():
        predictions += [inference(model, pred_loader, device)]


    #tst_preds = inference_one_epoch(model, tst_loader, device)
    predictions = np.mean(predictions, axis=0) 
    #print(f'mean of tst_preds = {predictions}')
    
    # top_3 = predictions[0].argsort()[-3:][::-1]
    # print(f'top_3 : {top_3}')
    


# encoded_labels = ['BMW/3시리즈/2017', 'BMW/3시리즈/2018', 'BMW/5시리즈/2017', 'BMW/5시리즈/2018',
#        '기아/K3/2017', '기아/K3/2018', '기아/K3/2019', '기아/K3/2020',
#        '기아/K3/2021', '기아/K5/2017', '기아/K5/2018', '기아/K5/2019',
#        '기아/K5/2020', '기아/K7/2017', '기아/K7/2018', '기아/K7/2019',
#        '기아/K7/2020', '기아/K9/2019', '기아/K9/2020', '기아/K9/2021',
#        '기아/니로/2017', '기아/니로/2018', '기아/니로/2019', '기아/니로/2020',
#        '기아/레이/2017', '기아/레이/2018', '기아/레이/2019', '기아/레이/2020',
#        '기아/모닝/2017', '기아/모닝/2018', '기아/모닝/2019', '기아/모닝/2020',
#        '기아/모닝/2021', '기아/모하비/2017', '기아/모하비/2018', '기아/봉고3/2017',
#        '기아/셀토스/2021', '기아/스토닉/2018', '기아/스토닉/2019', '기아/스팅어/2018',
#        '기아/스팅어/2019', '기아/스팅어/2020', '기아/스포티지/2017', '기아/스포티지/2018',
#        '기아/스포티지/2019', '기아/쏘렌토/2017', '기아/쏘렌토/2018', '기아/쏘렌토/2019',
#        '기아/쏘렌토/2020', '기아/쏘렌토/2021', '기아/카니발/2017', '기아/카니발/2018',
#        '기아/카니발/2019', '기아/카니발/2020', '랜드로버/레인지로버/2017', '르노삼성/QM3/2017',
#        '르노삼성/QM6/2017', '르노삼성/QM6/2018', '르노삼성/QM6/2019', '르노삼성/QM6/2020',
#        '르노삼성/SM3/2018', '르노삼성/SM5/2017', '르노삼성/SM6/2017', '르노삼성/SM6/2018',
#        '르노삼성/SM6/2019', '벤츠/C-Class/2017', '벤츠/E-Class/2017',
#        '벤츠/E-Class/2018', '벤츠/E-Class/2019', '벤츠/E-Class/2020',
#        '벤츠/S-Class/2017', '벤츠/S-Class/2018', '쉐보레/말리부/2017',
#        '쉐보레/말리부/2018', '쉐보레/스파크/2017', '쉐보레/스파크/2018', '쉐보레/스파크/2019',
#        '쉐보레/스파크/2020', '쉐보레/올란도/2018', '쉐보레/크루즈/2017', '쌍용/G4렉스턴/2018',
#        '쌍용/렉스턴스포츠/2019', '쌍용/티볼리/2017', '쌍용/티볼리/2018', '쌍용/티볼리/2019',
#        '아우디/A6/2017', '제네시스/EQ900/2017', '제네시스/EQ900/2018',
#        '제네시스/G70/2017', '제네시스/G70/2018', '제네시스/G70/2019', '제네시스/G80/2017',
#        '제네시스/G80/2018', '제네시스/G80/2019', '제네시스/G80/2021', '제네시스/G90/2019',
#        '포드/익스플로러/2017', '포드/익스플로러/2018', '폭스바겐/티구안/2017', '현대/그랜저/2017',
#        '현대/그랜저/2018', '현대/그랜저/2019', '현대/그랜저/2020', '현대/그랜저/2021',
#        '현대/베뉴/2020', '현대/스타렉스/2017', '현대/스타렉스/2018', '현대/스타렉스/2019',
#        '현대/스타렉스/2020', '현대/싼타페/2017', '현대/싼타페/2018', '현대/싼타페/2019',
#        '현대/싼타페/2020', '현대/쏘나타/2017', '현대/쏘나타/2018', '현대/쏘나타/2019',
#        '현대/쏘나타/2020', '현대/쏘나타/2021', '현대/아반떼/2017', '현대/아반떼/2018',
#        '현대/아반떼/2019', '현대/아반떼/2020', '현대/아반떼/2021', '현대/코나/2018',
#        '현대/코나/2019', '현대/코나/2020', '현대/투싼/2017', '현대/투싼/2018',
#        '현대/투싼/2019', '현대/투싼/2020', '현대/팰리세이드/2019', '현대/팰리세이드/2020',
#        '현대/팰리세이드/2021', '현대/포터2/2017']

encoded_labels = ['기아/K3/2017', '기아/K3/2018', '기아/K3/2019', '기아/K3/2020',
       '기아/K3/2021', '기아/K5/2017', '기아/K5/2018', '기아/K5/2019',
       '기아/K5/2020', '기아/K7/2017', '기아/K7/2018', '기아/K7/2019',
       '기아/K7/2020', '기아/K9/2019', '기아/K9/2020', '기아/K9/2021',
       '기아/니로/2017', '기아/니로/2018', '기아/니로/2019', '기아/니로/2020',
       '기아/레이/2017', '기아/레이/2018', '기아/레이/2019', '기아/레이/2020',
       '기아/모닝/2017', '기아/모닝/2018', '기아/모닝/2019', '기아/모닝/2020',
       '기아/모닝/2021', '기아/모하비/2017', '기아/모하비/2018', '기아/봉고3/2017',
       '기아/셀토스/2021', '기아/스토닉/2018', '기아/스토닉/2019', '기아/스팅어/2018',
       '기아/스팅어/2019', '기아/스팅어/2020', '기아/스포티지/2017', '기아/스포티지/2018',
       '기아/스포티지/2019', '기아/쏘렌토/2017', '기아/쏘렌토/2018', '기아/쏘렌토/2019',
       '기아/쏘렌토/2020', '기아/쏘렌토/2021', '기아/카니발/2017', '기아/카니발/2018',
       '기아/카니발/2019', '기아/카니발/2020', '제네시스/EQ900/2017', '제네시스/EQ900/2018',
       '제네시스/G70/2017', '제네시스/G70/2018', '제네시스/G70/2019', '제네시스/G80/2017',
       '제네시스/G80/2018', '제네시스/G80/2019', '제네시스/G80/2021', '제네시스/G90/2019',
       '현대/그랜저/2017', '현대/그랜저/2018', '현대/그랜저/2019', '현대/그랜저/2020',
       '현대/그랜저/2021', '현대/베뉴/2020', '현대/스타렉스/2017', '현대/스타렉스/2018',
       '현대/스타렉스/2019', '현대/스타렉스/2020', '현대/싼타페/2017', '현대/싼타페/2018',
       '현대/싼타페/2019', '현대/싼타페/2020', '현대/쏘나타/2017', '현대/쏘나타/2018',
       '현대/쏘나타/2019', '현대/쏘나타/2020', '현대/쏘나타/2021', '현대/아반떼/2017',
       '현대/아반떼/2018', '현대/아반떼/2019', '현대/아반떼/2020', '현대/아반떼/2021',
       '현대/코나/2018', '현대/코나/2019', '현대/코나/2020', '현대/투싼/2017',
       '현대/투싼/2018', '현대/투싼/2019', '현대/투싼/2020', '현대/팰리세이드/2019',
       '현대/팰리세이드/2020', '현대/팰리세이드/2021', '현대/포터2/2017']

# 라벨인코더 선언 및 Fitting
le = LabelEncoder()
le.fit(encoded_labels)

pred_count = 0

for i,pre in enumerate(predictions):
    top_3 = pre.argsort()[-3:][::-1]
    pred = le.inverse_transform(top_3)
    pred = [p.split('/',1)[1] for p in pred]
    
    if any (infer['label'][i].split('/',1) == pre_val.split('/',1) for pre_val in pred):
        pred_count = pred_count +1
       # print('0')
    label = infer['label'][i]
    print(f'label:[{label}]  top3: {pred}')

print(f'accuracy = {pred_count / len(infer)}')
# top_3 = pre.argsort()[-3:][::-1]
#     print(len(top_3))
#     print(len(infer))
#     infer['pred'] = le.inverse_transform(top_3)
    
#     infer['pred'] = [t_pred.split('/',1)[1] for t_pred in infer['pred']]
#     print(infer['pred'])
    
#     print(f'top3:{infer.label} : {infer.pred}')
#     print(f'accuracy = {np.sum(infer.label == infer.pred) / len(infer)}')


# prediction = le.inverse_transform(top_3)
# print(prediction)

del model
torch.cuda.empty_cache()
# print(torch.cuda.memory_allocated())
# print(torch.cuda.memory_reserved())


dist.destroy_process_group()
#bashCommand = "nvidia-smi | grep 'python' | awk '{ print $5 }' | xargs -n1 kill -9"
#os.system(bashCommand)