import torch
import torch.nn as nn
from torch import autograd
import os
from PIL import Image
import cv2
from torch.nn import functional as F
import sys
sys.path.append("/home/lpy/paper/experiment/")
from model.SELayer import SElayer
import numpy as np
import math
from model.Res2block import Res2block

class downDouble3dConv(nn.Module):
    def __init__(self, in_ch, out_ch):
        super(downDouble3dConv, self).__init__()
        self.conv = nn.Sequential(
            Res2block(in_ch),
            # nn.Conv3d(in_ch, in_ch, 3, padding=1),
            nn.BatchNorm3d(in_ch),
            nn.ReLU(inplace=False),
            nn.Conv3d(in_ch, out_ch, 3, padding=1),
            nn.BatchNorm3d(out_ch),
            nn.ReLU(inplace=False)
        )
    def forward(self, input):
        return self.conv(input)
 
class upDouble3dConv(nn.Module):
    def __init__(self, in_ch, out_ch, padding = 1):
        super(upDouble3dConv, self).__init__()
        self.conv = nn.Sequential(
            nn.Conv3d(in_ch, out_ch, 3, padding = padding),
            nn.BatchNorm3d(out_ch),
            nn.ReLU(inplace=False),
            # nn.Conv3d(out_ch, out_ch, 3, padding = padding),
            Res2block(out_ch),
            nn.BatchNorm3d(out_ch),
            nn.ReLU(inplace=False)
        )
 
    def forward(self, input):
        return self.conv(input)

class AMEA_res2block(nn.Module): # 参数量从17.7降到14.28
    def __init__(self, in_ch, out_ch):
        super(AMEA_res2block, self).__init__()
        self.conv0 = nn.Sequential(
            nn.Conv3d(in_ch, 32, 3, padding = 1),    
            Res2block(32),
            nn.ReLU(inplace=False),
            nn.Conv3d(32, 64, 3, padding = 1),  
            nn.ReLU(inplace=False)
        )

        self.pool1 = nn.MaxPool3d((1, 2, 2), (1, 2, 2)) # (kernel_size, stride)
        self.conv1 = downDouble3dConv(64, 128)
        self.pool2 = nn.MaxPool3d((1,2,2), (1,2,2))
        self.conv2 = downDouble3dConv(128, 256)
        self.pool3 = nn.MaxPool3d((1,2,2), (1,2,2))
        
        
        self.bridge = downDouble3dConv(256, 512)
        self.up1 = nn.ConvTranspose3d(512, 512, (1,2,2), stride = (1,2,2))
        
        self.conv4 = upDouble3dConv(768, 256)
        self.up2 = nn.ConvTranspose3d(256, 256, (1,2,2), stride=(1,2,2))
        
        self.conv5 = upDouble3dConv(384, 128)
        self.up3 = nn.ConvTranspose3d(128, 128, (1,2,2), stride=(1,2,2)) ##
        self.conv6 = upDouble3dConv(192, 64)

        self.conv7 = nn.Conv3d(64, out_ch, 3, padding = 1)
        self.BN3d = nn.BatchNorm3d(out_ch)

    def forward(self, input):
        # encoder
        c0 = self.conv0(input) 
        p1 = self.pool1(c0)
        c1 = self.conv1(p1) 
        p2 = self.pool2(c1)# 64 64 
        c2 = self.conv2(p2)
        p3 = self.pool3(c2)
        c3 = self.bridge(p3)
        
        # decoder
        up_1 = self.up1(c3)
        merge5 = torch.cat((up_1, c2), dim = 1)
        c4 = self.conv4(merge5)
        up_2 = self.up2(c4) 
        merge6 = torch.cat([up_2, c1], dim = 1) #32
    
        c5 = self.conv5(merge6)
        up_3 = self.up3(c5)
        merge7 = torch.cat([up_3, c0], dim = 1) #64
        c6 = self.conv6(merge7)
        
        c7 = self.conv7(c6)
        out = self.BN3d(c7)
        return out

if __name__ == "__main__":
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = AMEA_res2block(1, 1).cuda()
    model = nn.DataParallel(model,device_ids=[0])
    params = sum(param.numel() for param in model.parameters())
    input = torch.randn(1, 1, 19, 256, 256) # BCDHW 
    input = input.to(device)
    out = model(input) 
    print("output.shape:", out.shape) # 4, 1, 8, 256, 256
