#!/usr/bin/env bash
set -ex

target_repo="asxez/DockerDesktop-CN"
root_dir=$(pwd)
asar_bin="./node_modules/.bin/asar"

rm -rf tmp && mkdir -p dist tmp

# repo latest release
release=$(gh release view --repo "${target_repo}" --json tagName --jq .tagName || echo "")
# docker desktop latest version
wget -q -O tmp/release-notes.md https://github.com/docker/docs/raw/refs/heads/main/content/manuals/desktop/release-notes.md
# e.g. 4.39.0
version=$(grep -oPm 1 '{{<\s(?!release-date).*?all=true.*?version="\K[^"]+' tmp/release-notes.md)
if [ "${release}" == "${version}" ]; then
    echo "We already have the latest version"
    exit 0
fi

# install 7z
if [ ! -e "./7z/7zz" ]; then
  mkdir -p 7z
  wget -q -O 7z/7z.tar.xz https://github.com/ip7z/7zip/releases/download/26.00/7z2600-linux-x64.tar.xz
  tar -xf 7z/7z.tar.xz -C 7z
fi

# install requirements
npm install
pip install -r requirements.txt

# download dd
build_path=$(grep -oPm 1 '{{<\s(?!release-date).*?all=true.*?build_path="\K[^"]+' tmp/release-notes.md)
if [ ! -e "dist/DockerDesktop-${version}-Windows-x86.exe" ]; then
    wget -q -O "dist/DockerDesktop-${version}-Windows-x86.exe" "https://desktop.docker.com/win/main/amd64${build_path}Docker%20Desktop%20Installer.exe"
fi
if [ ! -e "dist/DockerDesktop-${version}-Windows-arm.exe" ]; then
    wget -q -O "dist/DockerDesktop-${version}-Windows-arm.exe" "https://desktop.docker.com/win/main/arm64${build_path}Docker%20Desktop%20Installer.exe"
fi
if [ ! -e "dist/DockerDesktop-${version}-Mac-apple.dmg" ]; then
    wget -q -O "dist/DockerDesktop-${version}-Mac-apple.dmg" "https://desktop.docker.com/mac/main/arm64${build_path}Docker.dmg"
fi
if [ ! -e "dist/DockerDesktop-${version}-Mac-intel.dmg" ]; then
    wget -q -O "dist/DockerDesktop-${version}-Mac-intel.dmg" "https://desktop.docker.com/mac/main/amd64${build_path}Docker.dmg"
fi
if [ ! -e "dist/DockerDesktop-${version}-Debian-x86.deb" ]; then
    wget -q -O "dist/DockerDesktop-${version}-Debian-x86.deb" "https://desktop.docker.com/linux/main/amd64${build_path}docker-desktop-amd64.deb"
fi

function asar_header_hash() {
    node -e 'const disk=require("asar/lib/disk"); const crypto=require("crypto"); const header=disk.readArchiveHeaderSync(process.argv[1]).header; process.stdout.write(crypto.createHash("sha256").update(JSON.stringify(header)).digest("hex"));' "$1"
}

function patch_windows_integrity() {
    local asar_path=$1
    local exe_path=$2
    local new_hash
    new_hash=$(asar_header_hash "${asar_path}")

    python - "${exe_path}" "${new_hash}" <<'PY'
import re
import sys
from pathlib import Path

exe_path = Path(sys.argv[1])
new_hash = sys.argv[2].encode("ascii")
pattern = re.compile(rb'("file":"resources\\\\app\.asar","alg":"SHA256","value":")([0-9a-fA-F]{64})(")')
data = exe_path.read_bytes()
matches = list(pattern.finditer(data))
if not matches:
    print(f"warning: app.asar integrity metadata not found in {exe_path}", file=sys.stderr)
    sys.exit(0)

backup_path = exe_path.with_name(exe_path.name + ".bak")
if not backup_path.exists():
    backup_path.write_bytes(data)

with exe_path.open("r+b") as writer:
    for match in matches:
        writer.seek(match.start(2))
        writer.write(new_hash)
PY
}

function pack_asar() {
    local source_dir=$1
    local original_unpacked=$2
    local output_asar=$3
    local unpack_pattern=""

    if [ -d "${original_unpacked}" ]; then
        unpack_pattern=$(cd "${original_unpacked}" && find . -type f | sed "s#^\./#${source_dir}/#" | paste -sd, -)
    fi

    if [ -n "${unpack_pattern}" ]; then
        if [[ "${unpack_pattern}" == *,* ]]; then
            unpack_pattern="{${unpack_pattern}}"
        fi
        "${asar_bin}" pack "${source_dir}" "${output_asar}" --unpack "${unpack_pattern}"
    else
        "${asar_bin}" pack "${source_dir}" "${output_asar}"
    fi
}

# unzip, extract, replace, pack
function ddcs() {
    pkg_name=$1
    # Windows-x86, Windows-arm, Mac-apple, Mac-intel, Debian-x86
    arch=$(echo "$pkg_name" | sed -nr 's/DockerDesktop-.+-(.+-.+)\..+/\1/p')

    rm -f "dist/app-${arch}.zip"
    rm -rf "tmp/${arch}" "tmp/app-${arch}" "tmp/app-${arch}.asar" "tmp/app-${arch}.asar.unpacked" "tmp/package-${arch}"
    ./7z/7zz x "dist/${pkg_name}" -y -o"tmp/${arch}" -bso0 -bd || true
    if [[ $arch == Windows* ]]; then
        src="frontend/resources"
        exe_path="tmp/${arch}/frontend/Docker Desktop.exe"
    elif [[ $arch == Mac* ]]; then
        src="Docker/Docker.app/Contents/MacOS/Docker Desktop.app/Contents/Resources"
        exe_path=""
    elif [[ $arch == Debian* ]]; then
        tar -xf "tmp/${arch}/data.tar" -C "tmp/${arch}"
        src="opt/docker-desktop/resources"
        exe_path=""
    else
       echo "unknown arch"
       exit 1
    fi
    mv "tmp/${arch}/${src}/app.asar" "tmp/app-${arch}.asar"
    if [ -d "tmp/${arch}/${src}/app.asar.unpacked" ]; then
        mv "tmp/${arch}/${src}/app.asar.unpacked" "tmp/app-${arch}.asar.unpacked"
    fi

    "${asar_bin}" extract "tmp/app-${arch}.asar" "tmp/app-${arch}"
    python ddcs.py --root_path "tmp/app-${arch}" > /dev/null

    mkdir -p "tmp/package-${arch}"
    pack_asar "tmp/app-${arch}" "tmp/app-${arch}.asar.unpacked" "tmp/package-${arch}/app.asar"
    if [[ $arch == Windows* ]]; then
        patch_windows_integrity "tmp/package-${arch}/app.asar" "${exe_path}"
        cp "${exe_path}" "tmp/package-${arch}/Docker Desktop.exe"
    fi

    (
        cd "tmp/package-${arch}"
        "${root_dir}/7z/7zz" a -tzip "${root_dir}/dist/app-${arch}.zip" . -bso0 -bd
    )
}

ddcs "DockerDesktop-${version}-Windows-x86.exe"
ddcs "DockerDesktop-${version}-Windows-arm.exe"
ddcs "DockerDesktop-${version}-Mac-apple.dmg"
ddcs "DockerDesktop-${version}-Mac-intel.dmg"
ddcs "DockerDesktop-${version}-Debian-x86.deb"


notes="DockerDesktop ${version} 版本安装程序及汉化包.

汉化包为 app-*.zip，包含 app.asar 和 app.asar.unpacked。
Windows 汉化包额外包含已同步 app.asar header hash 的 Docker Desktop.exe，用于 Docker Desktop 4.74.0+ 的完整性校验。"

gh release create "${version}" --repo "${target_repo}" --notes "$notes" ./dist/*
