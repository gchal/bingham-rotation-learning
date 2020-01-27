import torch
import time, argparse
from datetime import datetime
import numpy as np
import sys
sys.path.insert(0,'..')
from loaders import FLADataset
from networks import *
from losses import *
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as transforms
import tqdm
from helpers_train_test import train_test_model


class ConvAutoencoder(torch.nn.Module):
    def __init__(self):
        super(ConvAutoencoder, self).__init__()
        ## encoder layers ##
        # conv layer (depth from 1 --> 16), 3x3 kernels
        self.conv1 = torch.nn.Conv2d(1, 16, 3, padding=1)  
        # conv layer (depth from 16 --> 4), 3x3 kernels
        self.conv2 = torch.nn.Conv2d(16, 4, 3, padding=1)
        # pooling layer to reduce x-y dims by two; kernel and stride of 2
        self.pool = torch.nn.MaxPool2d(2, 2)
        
        ## decoder layers ##
        ## a kernel of 2 and a stride of 2 will increase the spatial dims by 2
        self.t_conv1 = torch.nn.ConvTranspose2d(4, 16, 2, stride=2)
        self.t_conv2 = torch.nn.ConvTranspose2d(16, 1, 2, stride=2)


    def forward(self, x):
        ## encode ##
        # add hidden layers with relu activation function
        # and maxpooling after
        x = F.relu(self.conv1(x))
        x = self.pool(x)
        # add second hidden layer
        x = F.relu(self.conv2(x))
        x = self.pool(x)  # compressed representation
        
        ## decode ##
        # add transpose conv layers, with relu activation function
        x = F.relu(self.t_conv1(x))
        # output layer (with sigmoid for scaling from 0 to 1)
        x = F.sigmoid(self.t_conv2(x))
                
        return x


def main():
    parser = argparse.ArgumentParser(description='KITTI relative odometry experiment')
    parser.add_argument('--epochs', type=int, default=10)

    parser.add_argument('--batch_size_test', type=int, default=64)
    parser.add_argument('--batch_size_train', type=int, default=32)

    parser.add_argument('--cuda', action='store_true', default=False)
    parser.add_argument('--num_workers', type=int, default=4)
    parser.add_argument('--megalith', action='store_true', default=False)

    parser.add_argument('--lr', type=float, default=5e-4)


    args = parser.parse_args()
    print(args)

    #Float or Double?
    tensor_type = torch.float


    device = torch.device('cuda:0') if args.cuda else torch.device('cpu')
    tensor_type = torch.double if args.double else torch.float


    #Monolith
    if args.megalith:
        dataset_dir = '/media/datasets/'
    else:
        dataset_dir = '/media/m2-drive/datasets/'

    image_dir = dataset_dir+'fla/2020.01.14_rss2020_data/2017_05_10_10_18_40_fla-19/flea3'
    pose_dir = dataset_dir+'fla/2020.01.14_rss2020_data/2017_05_10_10_18_40_fla-19/pose'

    normalize = transforms.Normalize(mean=[0.45],
                                    std=[0.25])

    transform = transforms.Compose([
            torchvision.transforms.Resize(256),
            torchvision.transforms.CenterCrop(224),
            transforms.ToTensor(),
            normalize,
    ])
    dim_in = 2

    test_dataset = '../experiments/FLA/{}_test.csv'.format(args.scene)
    train_dataset = '../experiments/FLA/{}_train_reverse_False.csv'.format(args.scene)

    train_loader = DataLoader(FLADataset(train_dataset, image_dir=image_dir, pose_dir=pose_dir, transform=transform),
                            batch_size=args.batch_size_train, pin_memory=False,
                            shuffle=True, num_workers=args.num_workers, drop_last=False)

    valid_loader = DataLoader(FLADataset(test_dataset, image_dir=image_dir, pose_dir=pose_dir, transform=transform, eval_mode=True),
                            batch_size=args.batch_size_test, pin_memory=False,
                            shuffle=False, num_workers=args.num_workers, drop_last=False)

    
    model = ConvAutoencoder().to(device=device, dtype=tensor_type)
    loss_fn = torch.nn.MSELoss()

    optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=args.lr)
    
    device = next(model.parameters()).device
    tensor_type = torch.double if args.double else torch.float

    for e in range(args.epochs):
        start_time = time.time()

        #Train model
        model.train()
        train_loss = torch.tensor(0.)
        train_mean_err = torch.tensor(0.)
        num_train_batches = len(train_loader)

        pbar = tqdm.tqdm(total=num_train_batches)
        for _, (imgs, _) in enumerate(train_loader):
            #Move all data to appropriate device
            target = target.to(device=device, dtype=tensor_type)
            img = imgs[0].to(device=device, dtype=tensor_type)
            _, train_loss_k = train_autoenc(model, loss_fn, optimizer, img)
            
            train_loss += (1./num_train_batches)*train_loss_k
            pbar.update(1)
        
        pbar.close()
        elapsed_time = time.time() - start_time
        
        output_string = 'Epoch: {}/{}. Train: Loss {:.3E} / Error {:.3f} (deg) | Test: Loss {:.3E} / Error {:.3f} (deg). Epoch time: {:.3f} sec.'.format(e+1, args.epochs, train_loss, train_mean_err, test_loss, test_mean_err, elapsed_time)
        print(output_string)

#Generic training function
def train_autoenc(model, loss_fn, optimizer, img):

    # Reset gradient
    optimizer.zero_grad()

    # Forward
    img_out = model.forward(img)
    
    loss = loss_fn(img_out, img)
    # Backward
    loss.backward()

    # Update parameters
    optimizer.step()

    return (img_out, loss.item())


def test_autoenc(model, loss_fn, img):
    # Forward
    with torch.no_grad():
        img_out = model.forward(img)
        loss = loss_fn(img_out, img)
            
    return (img_out, loss.item())

if __name__=='__main__':
    main()