import os
import pickle

import numpy

import shutil
import sys
import logging


# 获取文件所在文件夹的路径
def get_file_dir_path(file_path):
    dir_path = os.path.dirname(file_path)
    # print("file_name = ", file_name)
    return dir_path


# 获取文件所在文件夹的名称
def get_file_dir_name(file_path):
    dir_path = get_file_dir_path(file_path)
    dir_name = os.path.basename(dir_path)
    # print("file_name = ", file_name)
    return dir_name


# 根据文件路径获取文件名（不包含扩展名）
def get_pure_file_name_from_path(file_path):
    file_name = get_file_name_from_path(file_path)
    rindex = file_name.rindex(".")
    pure_file_name = file_name[:rindex]
    # print("file_name = ", file_name)
    return pure_file_name


def get_file_name_from_path(file_path):
    file_name = os.path.basename(file_path)
    # print("file_name = ", file_name)
    return file_name


# 在文件名之后，“.”之前插入字符串
def insert_str_in_file_name_end(file_name, str):
    rindex = file_name.rindex(".")
    list_string = list(file_name)
    list_string.insert(rindex, str)
    result_str = "".join(list_string)
    return result_str


# 遍历获取文件夹下的所有文件,所有文件绝对路径在一个列表中返回
def get_all_files_in_dir(dir_name, file_type=None):
    file_list = []
    for filepath, dirnames, filenames in os.walk(dir_name):
        for filename in filenames:
            if file_type is None:
                file_list.append(os.path.join(filepath, filename))
            elif filename.endswith(file_type):
                file_list.append(os.path.join(filepath, filename))
    return file_list


# 遍历获取文件夹下的所有文件,所有文件绝对路径以父文件夹的组织结构分层返回。os.walk 版本
# def get_all_grouped_files_in_dir(dir_name):
#     file_group_list = []
#     for (filepath, dirnames, filenames) in os.walk(dir_name):
#         file_list = []
#         for filename in filenames:
#             file_list.append(os.path.join(filepath, filename))
#         if len(file_list) > 0:
#             file_group_list.append(file_list)
#     return file_group_list

# 遍历获取文件夹下的所有文件路径,所有文件绝对路径以父文件夹的组织结构分层返回。os.walk 版本
def get_all_grouped_file_path_in_dir(dir_name):
    file_group_list = []
    if os.path.isfile(dir_name):
        return dir_name
    elif os.path.isdir(dir_name):
        for file in os.listdir(dir_name):
            new_file = os.path.join(dir_name, file)
            file_group_list.append(get_all_grouped_file_path_in_dir(new_file))
    else:
        raise Exception("路径不存在")
    return file_group_list


#
# # 读取模型
# def read_model():
#     if os.path.exists(constant.model_save_path):
#         f = open(constant.model_save_path, 'rb')
#         elm = pickle.load(f)
#         f.close()
#         return elm
#     return None
#
#
# # 保存模型
# def save_model(model):
#     f = open(constant.model_save_path, 'wb')
#     pickle.dump(model, f)
#     f.close()


# 为某一目标文件夹下的所有文件根据文件名创建自己的文件夹，并移动进文件夹中
def create_dir_for_every_file(target_dir_name):
    file_paths = get_all_files_in_dir(target_dir_name, None)
    file_names = []
    for file_path in file_paths:
        file_name = get_pure_file_name_from_path(file_path)
        parent_dir = target_dir_name + "//" + file_name
        os.makedirs(parent_dir)
        try:
            shutil.move(file_path, parent_dir)
        except Exception as e:
            print("移动文件失败，原因：", e)


def create_dir(dir_path, clear_dir_files=False):
    if os.path.exists(dir_path):
        if clear_dir_files:
            shutil.rmtree(dir_path, True)
            os.makedirs(dir_path)
    else:
        os.makedirs(dir_path)


#
# def save_pr_csv_data(labels, results, precision, recall, threshold, file_name_suffix=""):
#     dir_path = constant.cache_dir + constant.pr_data_dir
#     create_dir(dir_path)
#     numpy.savetxt(dir_path + 'labels_{}.csv'.format(file_name_suffix), labels)
#     numpy.savetxt(dir_path + 'results_{}.csv'.format(file_name_suffix), results)
#     numpy.savetxt(dir_path + 'precision_{}.csv'.format(file_name_suffix), precision)
#     numpy.savetxt(dir_path + 'recall_{}.csv'.format(file_name_suffix), recall)
#     numpy.savetxt(dir_path + 'threshold_{}.csv'.format(file_name_suffix), threshold)


def copy_files_to_dir(dir_path, *files):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    for file in files:
        file_name = get_file_name_from_path(file)
        shutil.copyfile(file, os.path.join(dir_path, file_name))


# 把文件根据所在文件夹的名称重命名
def rename_file_in_dir(dir_name, suffix=None):
    if os.path.isfile(dir_name):
        file_path = dir_name
        parent_dir_name = get_file_dir_name(file_path)
        file_name = get_file_name_from_path(file_path)
        new_path = file_path
        if suffix is not None:
            new_path = insert_str_in_file_name_end(new_path, "_{}".format(suffix))
        new_path = insert_str_in_file_name_end(new_path, "_{}".format(parent_dir_name))
        print("rename {} to {} ".format(file_path, new_path))
        os.rename(file_path, new_path)
        pass
    elif os.path.isdir(dir_name):
        for file in os.listdir(dir_name):
            file_path = os.path.join(dir_name, file)
            rename_file_in_dir(file_path, suffix)
    else:
        raise Exception("路径不存在")



# 把一个文件夹下的所有文件根据文件名复制到另一个文件夹下的对应文件夹中。就是把同类的文件（比如“美少女_xxx.jpg”系列的文件全都归类到“美少女”文件夹）归类整理
def copy_files_to_same_kind_dir(source_dir, target_dir):
    files_in_dir = get_all_files_in_dir(source_dir, None)
    files_num = len(files_in_dir)
    for i, file_path in enumerate(files_in_dir):
        if i % 10 == 0:
            print("{} in {}".format(i, files_num))
        pure_file_name = get_pure_file_name_from_path(file_path)
        file_name = get_file_name_from_path(file_path)
        split = pure_file_name.split("_")
        same_kind_name = split[0]
        same_kind_dir = os.path.join(target_dir, same_kind_name)
        if not os.path.exists(same_kind_dir):
            raise Exception("此种文件的文件夹不存在")
        target_file_path = os.path.join(same_kind_dir, file_name)
        # print("file_path = {},target_file_path = {}".format(file_path, target_file_path))
        shutil.copyfile(file_path, target_file_path)


# 替换字符串指定位置字符
def replace_char(string, char, index):
    string = list(string)
    string[index] = char
    return ''.join(string)


def read_pkl_file(file_path):
    if not os.path.exists(file_path):
        raise RuntimeError("文件不存在")
    f = open(file_path, 'rb')
    content = pickle.load(f)
    dir_path = get_file_dir_path(file_path)
    f = open(os.path.join(dir_path, 'pkl_file_text.txt'), 'w')
    for n in content:
        print(n)
        f.write(str(n) + '\n')
    f.close()


class ConsoleLogger(object):
    def __init__(self, filename='default.log'):
        self.terminal = sys.stdout
        self.log = open(filename, 'w')
        sys.stdout = self

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        pass


# sys.stderr = Logger('a.log_file', sys.stderr)

def set_logger(log_path, mode='a'):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # Logging to a file
        file_handler = logging.FileHandler(log_path, mode=mode)
        file_handler.setFormatter(logging.Formatter('%(asctime)s: %(message)s', '%Y-%m-%d %H:%M:%S'))
        logger.addHandler(file_handler)

        # Logging to console
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(stream_handler)
