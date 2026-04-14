set -ex

targe_repo="asxez/DockerDesktop-CN"

rm -rf tmp && mkdir -p dist tmp

# repo latest release
release=$(gh release view --repo "${targe_repo}" --json tagName --jq .tagName || echo "")
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

# install asar
if ! command -v "7zz" >/dev/null; then
  npm install -g asar
fi

# install requirements
pip install black

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

# unzip, extract, replace, pack
function ddcs() {
    pkg_name=$1
    # Windows-x86, Windows-arm, Mac-apple, Mac-intel, Debian-x86
    arch=$(echo "$pkg_name" | sed -nr 's/DockerDesktop-.+-(.+-.+)\..+/\1/p')

    if [ -e "app-${arch}.asar" ]; then
        return
    fi

    ./7z/7zz x "dist/${pkg_name}" -y -o"tmp/${arch}" -bso0 -bd || true
    if [[ $arch == Windows* ]]; then
        src="frontend/resources"
    elif [[ $arch == Mac* ]]; then
        src="Docker/Docker.app/Contents/MacOS/Docker Desktop.app/Contents/Resources"
    elif [[ $arch == Debian* ]]; then
        tar -xf "tmp/${arch}/data.tar" -C "tmp/${arch}"
        src="opt/docker-desktop/resources"
    else
       echo "unknown arch"
       exit 1
    fi
    rm -rf "tmp/app-${arch}.asar" "tmp/app-${arch}.asar.unpacked"
    mv "tmp/${arch}/${src}/app.asar" "tmp/app-${arch}.asar"
    mv "tmp/${arch}/${src}/app.asar.unpacked" "tmp/app-${arch}.asar.unpacked"

    asar extract "tmp/app-${arch}.asar" "tmp/app-${arch}"
    python ddcs.py --root_path "tmp/app-${arch}" > /dev/null
    asar pack "tmp/app-${arch}" "dist/app-${arch}.asar"

    asar extract "tmp/app-${arch}.asar" "tmp/app-${arch}"
    python ddcs.py --root_path "tmp/app-${arch}" --v2 > /dev/null
    asar pack "tmp/app-${arch}" "dist/app-${arch}-v2beta.asar"
}

ddcs "DockerDesktop-${version}-Windows-x86.exe"
ddcs "DockerDesktop-${version}-Windows-arm.exe"
ddcs "DockerDesktop-${version}-Mac-apple.dmg"
ddcs "DockerDesktop-${version}-Mac-intel.dmg"
ddcs "DockerDesktop-${version}-Debian-x86.deb"


notes="DockerDesktop ${version} 版本安装程序及汉化包.

注意: v2beta 包含更多的翻译, 但可能无法正常工作"

gh release create "${version}" --repo "${targe_repo}" --notes "$notes" ./dist/*
