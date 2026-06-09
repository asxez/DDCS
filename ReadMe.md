# DDCS

DDCS，全称Docker Desktop Chinese Script，即Docker汉化脚本。

master 分支目前支持 Windows / Mac。

<big>**你可以在这个仓库找到各个版本的汉化包：【 https://github.com/asxez/DockerDesktop-CN 】**</big>

Release 中的汉化包为 `app-*.zip`：
- Windows 包含 `app.asar`、`app.asar.unpacked` 和已同步完整性校验的 `Docker Desktop.exe`。
- macOS / Linux 包含 `app.asar` 和 `app.asar.unpacked`。

## 环境需求
- Python >= 3.10
- Node.JS >= 22


## 使用方法
下载源码，管理员权限启动终端并进入到源码根目录，使用以下命令安装依赖。

```bash
pip install -r requirements.txt
npm install
```

使用以下命令进行汉化。

```bash
python ddcs.py
```

注意：
- Windows 请务必使用管理员权限启动终端。
- Docker Desktop 4.74.0 及以上版本会校验 `app.asar` 完整性。Windows 会在 `Docker Desktop.exe` 中记录 asar header hash，macOS 4.76.0 会在 `Docker Desktop.app/Contents/Info.plist` 的 `ElectronAsarIntegrity` 中记录该 hash。脚本会在替换 `app.asar` 后同步更新这些校验信息；如果没有管理员权限，脚本会提前报错，Docker Desktop 将无法正常启动。
- 如需使用旧版 `config.json` 精确替换逻辑，可运行 `python ddcs.py --legacy`。

## 自动提取

通过正则和简单的代码分析, 自动提取出 Docker Desktop 页面中出现的文本,
并保存到 [extract_config.py](./lib/extract_config.py).

### 对于使用者

目前 `ddcs.py` 默认使用自动提取替换逻辑，直接运行：

```bash
python ddcs.py
```

### 对于翻译者 & 开发者

#### Docker Desktop 4.74.0+ 完整性校验

4.74.0 起，Windows 版 Docker Desktop 会在 `Docker Desktop.exe` 中记录 `resources\app.asar` 的完整性信息；macOS 4.76.0 会在内层 `Docker Desktop.app/Contents/Info.plist` 的 `ElectronAsarIntegrity` 中记录 `Resources/app.asar` 的完整性信息。这里的 hash 是 `app.asar` header JSON 的 SHA256，不是整个 `app.asar` 文件的 SHA256。修改或重新打包 `app.asar` 后，必须同步更新该 hash，否则 Electron 会报 `Integrity check failed for asar archive` 并拒绝启动。

1. 运行自动提取 (仅在 Docker Desktop 发布新版本后需要)

    ```shell
    # 默认情况下与 ddcs.py 一致, 自动寻找本机 Docker Desktop app.asar 并解包
    python ddcs_extract.py
    ```
   或
    ```shell
    # path 参数为手动解包 asar 之后的路径 
    python ddcs_extract.py --path xxx
    ```
2. 进行翻译

   在 [extract_config.py](./lib/extract_config.py) 中的 config 是一个列表, 类型是 [Config](./lib/define.py), 即
   `[Config(src=英文, dst=中文, deleted_at=None), ...]`. 运行自动提取后,
   新增的 config 项目中:
    - src: 为英文文本
    - dst: 为空字符串 `""` 的中文文本
    - deleted_at: 如果旧配置项在当前版本没有提取到, 则会将其 deleted_at 设置为当前版本号

   请在 [extract_config.py](./lib/extract_config.py) 搜索空字符串并进行翻译.

   **注意事项**:
    - 英文文本可能为包含 js 变量的模板字符串, 如 `Images (${c.images.count})`, 翻译后的中文应当保留变量, 即
      `镜像（${c.images.count}）`
    - 英文文本可能为包含替换字段(`{0},{1},etc.`)的格式化字符串,如 `Select {0} in the {1} column to see it running.`,
      翻译后的中文应当保留替换字段, 即`在 {1} 列选择 {0} 以查看其运行情况`. 如果替换字段遗漏, 在替换阶段也会有警告日志输出.
    - 对于不需要翻译的项目, **请不要删除**, 而是将中文值设为 `None`, 如 `("Python", None)`
    - 对于没有自动提取的文本, 请添加到 [extract_config_manually.py](./lib/extract_config_manually.py) 中

    提取示例:
    ```diff
    config: List[Config] = [
    - Config(src="outdated text", dst="过时文本"),
    + Config(src="outdated text", dst="过时文本", deleted_at="4.50.0"),
    + Config(src="new text in {0}", dst="", deleted_at=None),
    + Config(src="Python", dst="", deleted_at=None),
    ]
    ```
    我们进行翻译
    ```diff
    config: List[Config] = [
    - Config(src="outdated text", dst="过时文本"),
    + Config(src="outdated text", dst="过时文本", deleted_at="4.50.0"),
    + Config(src="new text in {0}", dst="{0} 中的新文本", deleted_at=None), # 保持模板变量 
    + Config(src="Python", dst=None, deleted_at=None), # 专业词汇不需要翻译 
    ]

3. 验证翻译

    ```bash
    python ddcs.py
    ```
   替换后启动 Docker Desktop, 验证各个页面. 因为自动提取显然不可能足够精准, 因此可能会:
    - 遗漏部分内容. 表现: 某些地方仍为英文; 解决方法: 添加到 extract_config_manually.py 或者优化 extract.py
    - 错误提取. 表现: Docker Desktop 页面出现报错; 解决方法: 根据报错定位错误文本并修复 (大多出现在
      extract_config_manually 中, 如漏掉引号等)

## 更多问题？
有问题的可以扫码加群咨询。
![](images/1.jpg)


## Stars
如果你觉得本仓库对你有用，或者你对本仓库感兴趣，欢迎Star。
