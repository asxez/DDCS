# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 ASXE  All Rights Reserved 
#
# @Time    : 2024/8/9 下午4:17
# @Author  : ASXE

import time

from common import log
from lib.processor import DDProcessor, FileProcessor


def cost_time(func):
    def fun(*args, **kwargs):
        t = time.perf_counter()
        result = func(*args, **kwargs)
        log.info(f"共耗时：{time.perf_counter() - t:.8f}s")
        return result

    return fun


@cost_time
def run(root_path, config_path):
    log.info('脚本已启动...')
    time.sleep(1)

    DDProcessor(True)

    fp = FileProcessor(root_path, config_path)
    file_paths = fp.recursive_listdir()
    log.info('汉化开始')
    for transformation in fp.get_transformations():
        search = transformation['src']
        replacement = transformation['dest']
        replaced = fp.process_files(file_paths, search, replacement)
        if not replaced:
            log.warn(search)

    DDProcessor(False)


if __name__ == "__main__":
    root_path = './app/build/'
    config_path = './config.json'
    run(root_path, config_path)
