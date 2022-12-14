#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function

import torch
import torch.nn as nn
import torch.optim as optim

import numpy as np
import torchvision
from torchvision import datasets, models, transforms

import copy
import os
import shutil


class PenalizedSgd(optim.SGD):
    def __init__(self, params, reg_params, used_omega_weight, max_omega_weight, lr=0.001, momentum=0, dampening=0,
                 weight_decay=0, nesterov=False):
        super(PenalizedSgd, self).__init__(params, lr, momentum, dampening, weight_decay, nesterov)
        # 由于现在每一层有自己单独的 reg_lambda ，此处不再使用
        # self.reg_lambda = reg_lambda
        self.used_omega_weight = used_omega_weight
        self.max_omega_weight = max_omega_weight
        self.reg_params = reg_params

    def __setstate__(self, state):
        super(PenalizedSgd, self).__setstate__(state)

    def step(self, closure=None):

        loss = None
        use_gpu = torch.cuda.is_available()

        if closure is not None:
            loss = closure()
        used_omega_weight = self.used_omega_weight
        max_omega_weight = self.max_omega_weight
        reg_params = self.reg_params

        for group in self.param_groups:
            weight_decay = group['weight_decay']
            momentum = group['momentum']
            dampening = group['dampening']
            nesterov = group['nesterov']

            for p in group['params']:

                if p.grad is None:
                    continue

                d_p = p.grad.data
                d_p_with_penalty = d_p
                param_diff = None
                init_val = None
                if p in reg_params:
                    param_dict = reg_params[p]

                    omega_list = param_dict['omega_list']
                    used_omega = 0
                    omega_list_length = len(omega_list)
                    max_omega = None
                    for i, ome in enumerate(omega_list):
                        #     used_omega = ome * (omega_list_length - i) + used_omega
                        if max_omega is None:
                            max_omega = torch.zeros_like(ome)
                        max_omega = torch.max(max_omega, ome)
                        # 由于网络在训练中已经考虑了omega的影响，此处叠加omega，越早计算得到的omega占的权重应该越小
                        used_omega = ome * (i + 1) / omega_list_length + used_omega
                        # if self.flag < 1:
                        #     print("in LocalSgd ,ome_{} = {}".format(i, ome[:1, :, :]))
                        #     print("in LocalSgd ,max_omega_{} = {}".format(i, max_omega[:1, :, :]))

                    used_omega = used_omega / omega_list_length
                    # used_omega_weight_sigmoid = torch.sigmoid(model.used_omega_weight)
                    used_omega = used_omega * used_omega_weight + max_omega * max_omega_weight

                    init_val = param_dict['init_val']
                    reg_lambda = param_dict['lambda']
                    # curr_param_value_copy = p.data.clone()
                    curr_param_value_copy = p
                    if use_gpu:
                        curr_param_value_copy = curr_param_value_copy.cuda()
                        init_val = init_val.cuda()
                        used_omega = used_omega.cuda()

                    # get the difference
                    param_diff = curr_param_value_copy - init_val

                    # get the gradient for the penalty term for change in the weights of the parameters
                    # local_grad = torch.mul(param_diff, 2 * self.reg_lambda * omega)
                    # 使用每一层独立的reg_lambda替换整体设置的reg_lambda
                    # local_grad = torch.mul(param_diff, 2 * reg_lambda * omega)
                    local_grad = torch.mul(param_diff, 2 * reg_lambda * used_omega)
                    # print("omega = {} ,local_grad = {}".format(omega, local_grad))
                    # print("omega.min() = {} ,omega.max() = {} ,omega.mean() = {}"
                    #       .format(omega.min(), omega.max(), omega.mean()))
                    # print(
                    #     "local_grad.min() = {} ,local_grad.max() = {} ,local_grad.mean() = {}"
                    #         .format(local_grad.min(), local_grad.max(), local_grad.mean()))
                    # del param_diff
                    # del init_val
                    # del curr_param_value_copy

                    d_p_with_penalty = d_p + local_grad
                    # print("dp = {}".format(d_p))
                    # print("d_p.min() = {},d_p.max() = {} ,d_p.mean() = {}".format(d_p.min(), d_p.max(), d_p.mean()))
                    del d_p
                    del local_grad

                    if weight_decay != 0:
                        # d_p.add_(weight_decay, p.data)
                        d_p_with_penalty.add_(other=p.data, alpha=weight_decay)

                    if momentum != 0:
                        param_state = self.state[p]
                        if 'momentum_buffer' not in param_state:
                            buf = param_state['momentum_buffer'] = torch.clone(d_p_with_penalty).detach()
                        else:
                            buf = param_state['momentum_buffer']
                            # buf.mul_(momentum).add_(1 - dampening, d_p)
                            buf.mul_(momentum).add_(other=d_p_with_penalty, alpha=1 - dampening)
                        if nesterov:
                            d_p_with_penalty = d_p_with_penalty.add(momentum, buf)
                        else:
                            d_p_with_penalty = buf

                    p.data.add_(other=d_p_with_penalty, alpha=-group['lr'])
                    # p.data.add_(-group['lr'], d_p)
                    # 不是第一次更新（param_diff全0），不是第一个任务（local_grad全0）
                    # if param_diff is not None and local_grad is not None and local_grad.any().item() and param_diff.any().item():
                    #     d_p_group_lr = d_p_with_penalty * -group['lr']
                    #     # 比较他们的绝对值大小
                    #     compare = torch.gt(d_p_group_lr.abs(), param_diff.abs())
                    #     # 相乘之后与0比较，用来判断他们本来是不是异号
                    #     mul_result = torch.mul(d_p_group_lr, param_diff)
                    #     negative_compare = torch.lt(mul_result, torch.zeros_like(param_diff))
                    #     # dp 与 param_diff是异号的，并且dp的绝对值大小更大
                    #     compare_and_contrary = negative_compare & compare
                    #     # 惩罚项过大，对p的改变产生了“矫枉过正”的效果，直接让p回到 curr_param_value_copy 的大小
                    #     if compare_and_contrary.any().item():
                    #         # print("penalty is too large ({})\n compare with param_diff ({})\ncompare {}".format(
                    #         #     d_p_group_lr,
                    #         #     param_diff, compare))
                    #         p.data[compare_and_contrary] = curr_param_value_copy[compare_and_contrary]
                    del d_p_with_penalty
        return loss


class OmegaUpdate(optim.SGD):

    def __init__(self, params, lr=0.001, momentum=0, dampening=0, weight_decay=0, nesterov=False,
                 use_curvature_gradients_method=False):
        super(OmegaUpdate, self).__init__(params, lr, momentum, dampening, weight_decay, nesterov)
        self.use_curvature_gradients_method = use_curvature_gradients_method

    def __setstate__(self, state):
        super(OmegaUpdate, self).__setstate__(state)

    def step(self, reg_params, batch_index, batch_size, dataloader_len, use_gpu, derivative_order, closure=None):
        loss = None
        use_curvature_gradients_method = self.use_curvature_gradients_method
        if closure is not None:
            loss = closure()

        for group in self.param_groups:
            for p in group['params']:
                if p.grad is None:
                    continue

                if p in reg_params:
                    # The absolute value of the grad_data that is to be added to first_derivative
                    grad_data_copy = p.grad.data.clone()
                    grad_data_copy_abs = grad_data_copy.abs()

                    param_dict = reg_params[p]
                    if derivative_order == 1:
                        first_derivative = param_dict['first_derivative']
                        first_derivative = first_derivative.to(torch.device("cuda:0" if use_gpu else "cpu"))

                        current_size = (batch_index + 1) * batch_size
                        prev_size = batch_index * batch_size
                        step_size = 1 / float(current_size)

                        # Incremental update for the first_derivative
                        # sum up the magnitude of the gradient
                        new_first_derivative = ((first_derivative.mul(prev_size)).add(grad_data_copy_abs)).div(
                            current_size)
                        new_first_derivative = new_first_derivative.cpu()
                        param_dict['first_derivative'] = new_first_derivative

                        if batch_index == dataloader_len - 1:
                            first_derivative_list = param_dict['first_derivative_list']
                            first_derivative_list.append(new_first_derivative)
                            if not use_curvature_gradients_method:
                                omega = new_first_derivative.abs().cpu()
                                omega_list = param_dict['omega_list']
                                omega_list.append(omega)
                                print("max omega = {} ,min omega = {} ,omega mean = {}"
                                      .format(omega.max(), omega.min(), omega.mean()))
                                param_dict['omega_list'] = omega_list
                            else:
                                # pytorch的梯度是自动累加的，求完一阶导数后要清空tensor的grad，否则二阶导数的值会在一阶导数的基础上相加
                                p.grad.data.zero_()

                        # if batch_index % 10 == 0:
                        # print("in index {} ,param {}'s old first_derivative is {}\nnew first_derivative is {}"
                        #       .format(batch_index, p, first_derivative, new_first_derivative))
                        reg_params[p] = param_dict
                    elif derivative_order == 2 and use_curvature_gradients_method:
                        second_derivative = param_dict['second_derivative']
                        second_derivative = second_derivative.to(torch.device("cuda:0" if use_gpu else "cpu"))
                        current_size = (batch_index + 1) * batch_size
                        prev_size = batch_index * batch_size
                        step_size = 1 / float(current_size)
                        new_second_derivative = ((second_derivative.mul(prev_size)).add(grad_data_copy_abs)).div(
                            current_size)
                        param_dict['second_derivative'] = new_second_derivative
                        if batch_index == dataloader_len - 1:
                            # calculate curvature
                            new_second_derivative = new_second_derivative.abs()
                            first_derivative = param_dict['first_derivative']
                            first_derivative = first_derivative.cpu()
                            bottom = (1 + first_derivative ** 2) ** (3.0 / 2)
                            curvature = new_second_derivative / bottom
                            omega_list = param_dict['omega_list']
                            omega = first_derivative.abs() * (torch.log10(curvature + 1) + 1)
                            # print("first_derivative = {} ,new_second_derivative = {} ,curvature = {} ,omega = {}"
                            #       .format(first_derivative, new_second_derivative, curvature, omega))
                            print("max first_derivative = {} ,min first_derivative = {}"
                                  .format(first_derivative.max(), first_derivative.min()))
                            print("max new_second_derivative = {} ,min new_second_derivative = {}"
                                  .format(new_second_derivative.max(), new_second_derivative.min()))
                            print("max curvature = {} ,min curvature = {}"
                                  .format(curvature.max(), curvature.min()))
                            print("max omega = {} ,min omega = {} ,omega mean = {}"
                                  .format(omega.max(), omega.min(), omega.mean()))
                            omega_list.append(omega)
                            param_dict['omega_list'] = omega_list
                        reg_params[p] = param_dict
                    else:
                        raise RuntimeError("derivative_order ={} undefined".format(derivative_order))

        return loss


class OmegaVectorUpdate(optim.SGD):

    def __init__(self, params, lr=0.001, momentum=0, dampening=0, weight_decay=0, nesterov=False):
        super(OmegaVectorUpdate, self).__init__(params, lr, momentum, dampening, weight_decay, nesterov)

    def __setstate__(self, state):
        super(OmegaVectorUpdate, self).__setstate__(state)

    def step(self, reg_params, finality, batch_index, batch_size, use_gpu, closure=None):
        loss = None

        device = torch.device("cuda:0" if use_gpu else "cpu")

        if closure is not None:
            loss = closure()

        for group in self.param_groups:
            weight_decay = group['weight_decay']
            momentum = group['momentum']
            dampening = group['dampening']
            nesterov = group['nesterov']

            for p in group['params']:
                if p.grad is None:
                    continue

                if p in reg_params:

                    grad_data = p.grad.data

                    # The absolute value of the grad_data that is to be added to omega
                    grad_data_copy = p.grad.data.clone()
                    grad_data_copy = grad_data_copy.abs()

                    param_dict = reg_params[p]

                    if not finality:

                        if 'temp_grad' in reg_params.keys():
                            temp_grad = param_dict['temp_grad']

                        else:
                            temp_grad = torch.FloatTensor(p.data.size()).zero_()
                            temp_grad = temp_grad.to(device)

                        temp_grad = temp_grad + grad_data_copy
                        param_dict['temp_grad'] = temp_grad

                        # del temp_data
                    else:

                        # temp_grad variable
                        temp_grad = param_dict['temp_grad']
                        temp_grad = temp_grad + grad_data_copy

                        # omega variable
                        omega = param_dict['omega']
                        omega.to(device)

                        current_size = (batch_index + 1) * batch_size
                        step_size = 1 / float(current_size)

                        # Incremental update for the omega
                        omega = omega + step_size * (temp_grad - batch_size * (omega))

                        param_dict['omega'] = omega

                        reg_params[p] = param_dict

                        del omega
                        del param_dict

                    del grad_data
                    del grad_data_copy

        return loss
