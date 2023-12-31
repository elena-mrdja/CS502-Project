from abc import abstractmethod

import numpy as np
import torch
import torch.nn as nn
import wandb
from torch.autograd import Variable

from utils.data_utils import pearson_corr


class MetaTemplate(nn.Module):
    def __init__(self, backbone, n_way, n_support, backbone_relation=None, change_way=True, is_rn=False):
        super(MetaTemplate, self).__init__()
        self.n_way = n_way
        self.n_support = n_support
        self.n_query = -1  # (change depends on input)
        self.feature = backbone
        self.relation_score = backbone_relation
        self.feat_dim = self.feature.final_feat_dim
        self.change_way = change_way  # some methods allow different_way classification during training and test
        self.is_rn = is_rn # parameter that tells whether method is RelationNet or not

        if torch.cuda.is_available():
            self.device = torch.device("cuda")
        else:
            self.device = torch.device("cpu")

    @abstractmethod
    def set_forward(self, x, is_feature=False):
        pass

    @abstractmethod
    def set_forward_loss(self, x):
        pass

    def forward(self, x):
        out = self.feature.forward(x)
        return out

    def parse_feature(self, x, is_feature):
        if isinstance(x, list):
            x = [Variable(obj.to(self.device)) for obj in x]
        else: x = Variable(x.to(self.device))
        if is_feature:
            z_all = x
        else:
            if isinstance(x, list):
                x = [obj.contiguous().view(self.n_way * (self.n_support + self.n_query), *obj.size()[2:]) for obj in x]
            else: x = x.contiguous().view(self.n_way * (self.n_support + self.n_query), *x.size()[2:])
            z_all = self.feature.forward(x)
            z_all = z_all.view(self.n_way, self.n_support + self.n_query, -1)
        z_support = z_all[:, :self.n_support]
        z_query = z_all[:, self.n_support:]

        return z_support, z_query

    def correct(self, x):
        scores = self.set_forward(x)
        y_query = np.repeat(range(self.n_way), self.n_query)

        topk_scores, topk_labels = scores.data.topk(1, 1, True, True)
        topk_ind = topk_labels.cpu().numpy()
        top1_correct = np.sum(topk_ind[:, 0] == y_query)
        return float(top1_correct), len(y_query)
    
    # Function implemented by Marija Zelic and Elena Mrdja
    # Serves for counting correctly classified samples
    def correct_rn(self, x):
        # Compute relation scores
        relation_scores = self.set_forward(x) # shape: n_way * n_query, n_way

        # Compute class prediction
        topk_labels = torch.argmax(relation_scores.data, dim=1)

        # Detach the variables
        topk_ind = topk_labels.cpu().numpy()

        # Create the category labels for the queries
        y_query = np.repeat(range(self.n_way), self.n_query)

        # Compute the number of elements that are correctly classified
        top1_correct = np.sum(topk_ind == y_query)
        return float(top1_correct), len(y_query)

    def correlation(self, x, y, type="pearson"):
        y_pred = self.set_forward(x, y).reshape(-1).to(self.device)
        y_query = y[:, self.n_support:].reshape(-1).to(self.device)

        if type == "pearson":
            # corr = pearsonr(y_pred, y_query)
            corr = pearson_corr(y_pred, y_query)
        else:
            # Raise an error, this type is not defined
            raise ValueError(f"Correlation type {type} not defined")

        return corr.cpu().detach().numpy()

    def train_loop(self, epoch, train_loader, optimizer):
        print_freq = 10

        avg_loss = 0
        for i, (x, _) in enumerate(train_loader):
            if isinstance(x, list):
                self.n_query = x[0].size(1) - self.n_support
                if self.change_way:
                    self.n_way = x[0].size(0)
            else: 
                self.n_query = x.size(1) - self.n_support
                if self.change_way:
                    self.n_way = x.size(0)
            optimizer.zero_grad()
            loss = self.set_forward_loss(x)
            loss.backward()
            optimizer.step()
            avg_loss = avg_loss + loss.item()

            if i % print_freq == 0:
                # print(optimizer.state_dict()['param_groups'][0]['lr'])
                print('Epoch {:d} | Batch {:d}/{:d} | Loss {:f}'.format(epoch, i, len(train_loader),
                                                                        avg_loss / float(i + 1)))
                #wandb.log({"loss": avg_loss / float(i + 1)})

    def test_loop(self, test_loader, record=None, return_std=False):
        correct = 0
        count = 0
        acc_all = []

        iter_num = len(test_loader)
        for i, (x, _) in enumerate(test_loader):
            if isinstance(x, list):
                self.n_query = x[0].size(1) - self.n_support
                if self.change_way:
                    self.n_way = x[0].size(0)
            else: 
                self.n_query = x.size(1) - self.n_support
                if self.change_way:
                    self.n_way = x.size(0)
                # Additional check-up in the test loop to whether to apply correct or correct_rn  
                if self.is_rn == False:
                    correct_this, count_this = self.correct(x)
                else:
                    correct_this, count_this = self.correct_rn(x)
            acc_all.append(correct_this / count_this * 100)

        acc_all = np.asarray(acc_all)
        acc_mean = np.mean(acc_all)
        acc_std = np.std(acc_all)
        print('%d Test Acc = %4.2f%% +- %4.2f%%' % (iter_num, acc_mean, 1.96 * acc_std / np.sqrt(iter_num)))

        if return_std:
            return acc_mean, acc_std
        else:
            return acc_mean

    def set_forward_adaptation(self, x,
                               is_feature=True):  # further adaptation, default is fixing feature and train a new softmax clasifier
        assert is_feature == True, 'Feature is fixed in further adaptation'
        z_support, z_query = self.parse_feature(x, is_feature)

        z_support = z_support.contiguous().view(self.n_way * self.n_support, -1)
        z_query = z_query.contiguous().view(self.n_way * self.n_query, -1)

        y_support = torch.from_numpy(np.repeat(range(self.n_way), self.n_support))
        y_support = Variable(y_support.cuda())

        linear_clf = nn.Linear(self.feat_dim, self.n_way)
        linear_clf = linear_clf.cuda()

        set_optimizer = torch.optim.SGD(linear_clf.parameters(), lr=0.01, momentum=0.9, dampening=0.9,
                                        weight_decay=0.001)

        loss_function = nn.CrossEntropyLoss()
        loss_function = loss_function.cuda()

        batch_size = 4
        support_size = self.n_way * self.n_support
        for epoch in range(100):
            rand_id = np.random.permutation(support_size)
            for i in range(0, support_size, batch_size):
                set_optimizer.zero_grad()
                selected_id = torch.from_numpy(rand_id[i: min(i + batch_size, support_size)]).cuda()
                z_batch = z_support[selected_id]
                y_batch = y_support[selected_id]
                scores = linear_clf(z_batch)
                loss = loss_function(scores, y_batch)
                loss.backward()
                set_optimizer.step()

        scores = linear_clf(z_query)
        return scores
