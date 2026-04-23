# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 ASXE  All Rights Reserved
#
# @Time    : 2024/8/9 下午4:17
# @Author  : ASXE

import json
import multiprocessing
import os
import platform
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import log


class DDProcessor:
    def __init__(self, get=True):
        self.get = get
        self.resource_path = self.get_resource_path()
        if self.resource_path is None:
            sys.exit()
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
    def get_resource_path():
        system = platform.system()
        if system == "Windows":
            import winreg

            try:
                reg_key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Docker Desktop"
                )
                install_path, _ = winreg.QueryValueEx(reg_key, "InstallLocation")  # 获取安装路径
                winreg.CloseKey(reg_key)

                return Path(f"{install_path}/frontend/resources")
            except FileNotFoundError:
                log.warn('未找到Docker Desktop')
                return None
        elif system == "Darwin":
            potential_paths = [
                Path("/Applications/Docker.app/Contents/MacOS/Docker Desktop.app/Contents/Resources"),
                Path("~/Applications/Docker.app/Contents/MacOS/Docker Desktop.app/Contents/Resources").expanduser(),
            ]
            for path in potential_paths:
                if path.exists():
                    return path
        else:
            log.error(f"unsupported system: {system}")
            return None

    def cp_asar(self, get):
        cwd = Path.cwd()
        try:
            asar_unpacked = Path.cwd() / "app.asar.unpacked"
            if get:
                if asar_unpacked.exists():
                    shutil.rmtree(asar_unpacked)
                shutil.copytree(self.resource_path / "app.asar.unpacked", asar_unpacked)
                shutil.copy(self.resource_path / "app.asar", cwd)
                shutil.copy(self.resource_path / "app.asar", cwd / "app-backup.asar")
            else:
                shutil.copy(cwd / "app.asar", self.resource_path)
        except Exception as e:
            log.error(f"文件复制时出错: {str(e)}")
            sys.exit()

    @staticmethod
    def extract_asar():
        os.system('npm install -g asar')
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
            if new_content != content:
                f.seek(0)
                f.write(new_content)
                f.truncate()
                return True
            else:
                return False

    def process_files(self, file_paths, search_pattern, replacement):
        cpu_count = multiprocessing.cpu_count()
        replaced = False
        with ThreadPoolExecutor(max_workers=cpu_count) as executor:
            futures = [executor.submit(self.process_file, file_path, search_pattern, replacement) for file_path in
                       file_paths]
            for future in futures:
                if future.result():
                    replaced = True
        return replaced
