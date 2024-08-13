# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 ASXE  All Rights Reserved
#
# @Time    : 2024/8/12 下午2:16
# @Author  : ASXE

import json
import multiprocessing
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from common import log


def run_as_admin():
    if not is_admin():
        os.execvp('sudo', ['sudo', 'python3'] + sys.argv)


def is_admin():
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def command_exists(command):
    try:
        subprocess.run([command], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False

class DDProcessor:
    """
    extract_asar函数和pack_asar函数存在较大的问题，但是勉强可以使用，有想法的可以提一下。
    """

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
    def get_install_path():
        potential_paths = [
            "/Applications/Docker.app/Contents/MacOS/Docker Desktop.app/Contents/Resources",
            os.path.expanduser("~/Applications/Docker.app/Contents/MacOS/Docker Desktop.app/Contents/Resources")
        ]
        for path in potential_paths:
            if os.path.exists(path):
                return path
        return None

    def cp_asar(self, get):
        dest = os.path.join(os.getcwd(), 'app.asar.unpacked')
        try:
            if get:
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(os.path.join(self.docker_install_path, 'app.asar.unpacked'), dest)
                shutil.copy2(os.path.join(self.docker_install_path, 'app.asar'), os.getcwd())
                shutil.copy2(os.path.join(self.docker_install_path, 'app.asar'),
                             os.path.join(os.getcwd(), 'app-backup.asar'))
            else:
                os.remove(os.path.join(self.docker_install_path, 'app.asar'))
                shutil.copy2(os.path.join(os.getcwd(), 'app.asar'),
                             os.path.join(self.docker_install_path))
        except Exception as e:
            log.error(f"文件复制时出错: {str(e)}")
            sys.exit(1)

    @staticmethod
    def extract_asar():
        env = os.environ.copy()
        env['PATH'] = '/usr/local/bin:' + env['PATH']
        if not command_exists('npx asar'):
            log.info('正在下载必要包...')
            os.system('npm install asar')
        try:
            result = subprocess.run(['npx', 'asar', 'extract', 'app.asar', 'app'], check=True, env=env)
            if result.returncode != 0:
                log.error(f"执行解包命令出错: {result}")
                sys.exit(1)
            else:
                log.info(f"解包成功")
        except Exception as e:
            log.error(f"解包过程出错: {str(e)}")
            sys.exit(1)

    @staticmethod
    def pack_asar():
        env = os.environ.copy()
        env['PATH'] = '/usr/local/bin:' + env['PATH']
        try:
            result = subprocess.run(['npx', 'asar', 'pack', 'app', 'app.asar'], check=True, env=env)
            if result.returncode != 0:
                log.error(f"执行打包命令出错: {result}")
                sys.exit(1)
            else:
                log.info(f"打包成功")
        except Exception as e:
            log.error(f"打包过程出错: {str(e)}")
            sys.exit(1)


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
    def process_file(file_path, search_pattern, replacement):
        """
        如果你看到了这里，那么你极有可能改进此处，若真如此，建议你不要使用内存映射的方式来实现。
        :param file_path:
        :param search_pattern:
        :param replacement:
        :return:
        """

        pattern = re.compile(search_pattern)

        with open(file_path, 'r+', encoding='utf-8') as f:
            content = f.read()
            if search_pattern in content:  # 检测是否存在匹配项
                log.info(f"文件{file_path}：{search_pattern} -> {replacement}")
                new_content = pattern.sub(replacement, content)
                if new_content != content:
                    f.seek(0)
                    f.write(new_content)
                    f.truncate()  # 如果新内容较短，则截断

    def process_files(self, file_paths, search_pattern, replacement):
        cpu_count = multiprocessing.cpu_count()
        with ThreadPoolExecutor(max_workers=cpu_count) as executor:
            futures = [executor.submit(self.process_file, file_path, search_pattern, replacement) for file_path in
                       file_paths]
            for future in futures:
                future.result()
