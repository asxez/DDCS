# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 ASXE  All Rights Reserved 
#
# @Time    : 2024/8/10 上午11:24
# @Author  : ASXE

import time


def error(message):
    print(f"\033[91m\033[3m{time.strftime('%Y-%m-%d %H:%M:%S')} : {message}\033[0m")


def info(message):
    print(f"\033[92m\033[3m{time.strftime('%Y-%m-%d %H:%M:%S')} : {message}\033[0m")
