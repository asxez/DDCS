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
import re
import shutil
import subprocess
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
                self.remove_work_path(cwd / "app")
                if asar_unpacked.exists():
                    shutil.rmtree(asar_unpacked)
                resource_unpacked = self.resource_path / "app.asar.unpacked"
                if resource_unpacked.exists():
                    shutil.copytree(resource_unpacked, asar_unpacked)
                shutil.copy(self.resource_path / "app.asar", cwd)
                shutil.copy(self.resource_path / "app.asar", cwd / "app-backup.asar")
            else:
                executable_path = self.resource_path.parent / "Docker Desktop.exe"
                self.check_asar_integrity_writable(cwd / "app.asar", executable_path)
                shutil.copy(cwd / "app.asar", self.resource_path)
                local_unpacked = cwd / "app.asar.unpacked"
                target_unpacked = self.resource_path / "app.asar.unpacked"
                if local_unpacked.exists():
                    if target_unpacked.exists():
                        shutil.rmtree(target_unpacked)
                    shutil.copytree(local_unpacked, target_unpacked)
                self.update_asar_integrity(cwd / "app.asar", executable_path)
        except Exception as e:
            log.error(f"文件复制时出错: {str(e)}")
            sys.exit()

    @staticmethod
    def remove_work_path(path: Path):
        cwd = Path.cwd().resolve()
        target = path.resolve()
        if target.parent != cwd:
            raise ValueError(f"拒绝删除工作目录外的路径: {target}")
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()

    @staticmethod
    def extract_asar():
        asar_command = DDProcessor.get_asar_command()
        if asar_command is None:
            subprocess.run(["npm", "install", "-g", "asar"], check=True)
            asar_command = DDProcessor.get_asar_command()
        if asar_command is None:
            log.error('未找到 asar 命令，即将退出')
            sys.exit()

        result = subprocess.run([asar_command, "extract", "app.asar", "app"])
        if result.returncode != 0:
            log.error('执行解包命令出错，即将退出')
            sys.exit()
        else:
            log.info('解包成功')

    @staticmethod
    def pack_asar():
        asar_command = DDProcessor.get_asar_command()
        if asar_command is None:
            log.error('未找到 asar 命令，即将退出')
            sys.exit()

        command = [asar_command, "pack", "app", "app.asar"]
        unpack_pattern = DDProcessor.get_unpack_pattern(
            Path("app-backup.asar"), Path("app"), asar_command, Path("app.asar.unpacked")
        )
        if unpack_pattern:
            command.extend(["--unpack", unpack_pattern])
            DDProcessor.remove_work_path(Path("app.asar.unpacked"))

        result = subprocess.run(command)
        if result.returncode != 0:
            log.error('执行打包命令出错，即将退出')
            sys.exit()
        else:
            log.info('打包成功')

    @staticmethod
    def get_asar_command():
        local_bin = Path.cwd() / "node_modules" / ".bin"
        candidates = (
            [local_bin / "asar.cmd", local_bin / "asar", "asar.cmd", "asar"]
            if platform.system() == "Windows"
            else [local_bin / "asar", "asar"]
        )
        for candidate in candidates:
            command = str(candidate)
            if isinstance(candidate, Path) and candidate.exists():
                return command
            resolved = shutil.which(command)
            if resolved:
                return resolved
        return None

    @staticmethod
    def update_asar_integrity(asar_path: Path, executable_path: Path):
        if platform.system() != "Windows":
            return
        if not executable_path.exists():
            log.warn(f"未找到 Docker Desktop 可执行文件，跳过 asar 完整性更新: {executable_path}")
            return

        new_hash = DDProcessor.get_asar_integrity_hash(asar_path).encode("ascii")
        integrity_pattern = re.compile(
            rb'("file":"resources\\\\app\.asar","alg":"SHA256","value":")([0-9a-fA-F]{64})(")'
        )
        data = executable_path.read_bytes()
        old_hashes = {match.group(2).decode("ascii").lower() for match in integrity_pattern.finditer(data)}
        if not old_hashes:
            log.warn("未找到 app.asar 完整性校验信息，跳过更新")
            return

        matches = list(integrity_pattern.finditer(data))
        if all(match.group(2).lower() == new_hash for match in matches):
            log.info("asar 完整性校验已是最新")
            return

        try:
            with executable_path.open("r+b"):
                pass
        except PermissionError as e:
            raise PermissionError(f"没有权限更新 asar 完整性校验，请使用管理员权限运行脚本: {executable_path}") from e

        backup_path = executable_path.with_name(executable_path.name + ".bak")
        if not backup_path.exists():
            try:
                shutil.copy2(executable_path, backup_path)
            except PermissionError:
                backup_path = Path.cwd() / (executable_path.name + ".bak")
                if not backup_path.exists():
                    shutil.copy2(executable_path, backup_path)
                log.warn(f"安装目录不可写，已将 Docker Desktop.exe 备份到: {backup_path}")
        with executable_path.open("r+b") as writer:
            for match in matches:
                writer.seek(match.start(2))
                writer.write(new_hash)
        old_hash_text = ", ".join(sorted(old_hashes))
        log.info(f"已更新 asar 完整性校验: {old_hash_text} -> {new_hash.decode('ascii')}")

    @staticmethod
    def check_asar_integrity_writable(asar_path: Path, executable_path: Path):
        if platform.system() != "Windows" or not executable_path.exists():
            return

        new_hash = DDProcessor.get_asar_integrity_hash(asar_path).encode("ascii")
        integrity_pattern = re.compile(
            rb'("file":"resources\\\\app\.asar","alg":"SHA256","value":")([0-9a-fA-F]{64})(")'
        )
        matches = list(integrity_pattern.finditer(executable_path.read_bytes()))
        if not matches or all(match.group(2).lower() == new_hash for match in matches):
            return

        try:
            with executable_path.open("r+b"):
                pass
        except PermissionError as e:
            raise PermissionError(f"没有权限更新 asar 完整性校验，请使用管理员权限运行脚本: {executable_path}") from e

    @staticmethod
    def get_asar_integrity_hash(asar_path: Path):
        asar_command = DDProcessor.get_asar_command()
        if asar_command is None:
            raise RuntimeError("未找到 asar 命令，无法计算 asar 完整性校验")

        script = (
            "const disk=require('asar/lib/disk');"
            "const crypto=require('crypto');"
            "const header=disk.readArchiveHeaderSync(process.argv[1]).header;"
            "process.stdout.write(crypto.createHash('sha256').update(JSON.stringify(header)).digest('hex'));"
        )
        result = subprocess.run(
            ["node", "-e", script, str(asar_path)], capture_output=True, check=True, text=True
        )
        return result.stdout.strip()

    @staticmethod
    def get_unpack_pattern(archive: Path, source_path: Path, asar_command: str, unpacked_path: Path):
        unpacked_paths = []
        if unpacked_path.exists():
            for item in unpacked_path.rglob("*"):
                if item.is_file():
                    unpacked_paths.append(str(item.relative_to(unpacked_path)))
        elif archive.exists():
            try:
                result = subprocess.run(
                    [asar_command, "list", str(archive), "--is-pack"],
                    capture_output=True,
                    check=True,
                    text=True,
                )
            except Exception as e:
                log.warn(f"读取原始 asar unpacked 清单失败，将尝试从 app.asar.unpacked 恢复: {str(e)}")
            else:
                for line in result.stdout.splitlines():
                    state, _, raw_path = line.partition(":")
                    if state.strip() == "unpack":
                        unpacked_paths.append(raw_path)

        unpacked_files = []
        seen = set()
        for raw_path in unpacked_paths:
            rel_path = raw_path.strip().lstrip("\\/").replace("\\", "/")
            if not rel_path or rel_path in seen:
                continue
            seen.add(rel_path)

            source_file = source_path / Path(*rel_path.split("/"))
            unpacked_file = unpacked_path / Path(*rel_path.split("/"))
            if not source_file.is_file() and unpacked_file.is_file():
                source_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(unpacked_file, source_file)
            if source_file.is_file():
                unpacked_files.append(f"{source_path.name}/{rel_path}")

        if not unpacked_files:
            return None
        log.info(f"保留原始 asar unpacked 文件: {len(unpacked_files)} 个")
        unpack_pattern = ",".join(unpacked_files)
        return "{" + unpack_pattern + "}" if "," in unpack_pattern else unpack_pattern


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
