# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 ASXE  All Rights Reserved
#
# @Time    : 2024/8/9 下午4:17
# @Author  : ASXE

import ctypes
import json
import multiprocessing
import os
import shutil
import sys
import winreg
from concurrent.futures import ThreadPoolExecutor

from common import log


def run_as_admin():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


class DDProcessor:
    def __init__(self, get=True):
        self.get = get
        self.docker_install_path = self.get_install_path() if self.get_install_path() is not None else sys.exit()
        if self.get:
            log.info('正在备份文件...')
            self.cp_asar(self.get)
            log.info('开始解包...')
            self.extract_asar()
        else:
            log.info('开始打包...')
            self.pack_asar()
            log.info('正在替换文件...')
            self.cp_asar(self.get)
            log.info('汉化完成')

    @staticmethod
    def get_install_path(name='Docker Desktop'):
        try:
            reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                     rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{name}")
            install_path, _ = winreg.QueryValueEx(reg_key, "InstallLocation") # 获取安装路径
            winreg.CloseKey(reg_key)
            return install_path
        except FileNotFoundError:
            return None

    def cp_asar(self, get):
        dest = os.path.join(os.getcwd(), 'app.asar.unpacked')
        try:
            if get:
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(f'{self.docker_install_path}/frontend/resources/app.asar.unpacked', dest)
                shutil.copy(f'{self.docker_install_path}/frontend/resources/app.asar', os.getcwd())
                shutil.copy(f'{self.docker_install_path}/frontend/resources/app.asar',
                            os.path.join(os.getcwd(), 'app-backup.asar'))
            else:
                os.remove(f'{self.docker_install_path}/frontend/resources/app.asar')
                shutil.copy(f'{os.getcwd()}/app.asar', f'{self.docker_install_path}/frontend/resources')
        except Exception as e:
            log.error(f"文件复制时出错: {str(e)}")
            sys.exit()

    @staticmethod
    def extract_asar():
        flag = os.system('asar extract app.asar app')
        if flag == 1:
            log.error('执行解包命令出错，即将退出')
            sys.exit()
        else:
            log.info('解包成功')

    @staticmethod
    def pack_asar():
        flag = os.system('asar pack app app.asar')
        if flag == 1:
            log.error('执行打包命令出错，即将退出')
            sys.exit()
        else:
            log.info('打包成功')


class FileProcessor:
    def __init__(self, root_path, config_path):
        self.root_path = root_path
        self.config_path = config_path

    def recursive_listdir(self):
        file_paths = []
        for root, _, files in os.walk(self.root_path):
            for file in files:
                if file.endswith('.js') or file.endswith('.cjs'):
                    file_paths.append(os.path.join(root, file))
        return file_paths

    def get_transformations(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            transformations = json.loads(f.read())['all']
        for transformation in transformations:
            yield transformation

    @staticmethod
    def process_file(file_path, search, replacement):
        """
        如果你看到了这里，那么你极有可能改进此处，若真如此，建议你不要使用内存映射的方式来实现。
        :param file_path: 处理文件
        :param search: 原始内容
        :param replacement: 替换内容
        :return:
        """
        with open(file_path, 'r+', encoding='utf-8') as f:
            content = f.read()
            new_content = content.replace(search, replacement)
            if new_content != content:  # 检测是否存在匹配项
                f.seek(0)
                f.write(new_content)
                f.truncate()  # 如果新内容较短，则截断
                return True
            else:
                return False

    def process_files(self, file_paths, search_pattern, replacement):
        cpu_count = multiprocessing.cpu_count()
        with ThreadPoolExecutor(max_workers=cpu_count) as executor:
            futures = [executor.submit(self.process_file, file_path, search_pattern, replacement) for file_path in
                       file_paths]
            for future in futures:
                if future.result():
                    return True
        return False
