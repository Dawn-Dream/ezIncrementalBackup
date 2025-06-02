# ezIncrementalBackup

一个跨平台（主要支持Linux/Windows）的高效增量/全量备份工具，支持分卷压缩、WebDAV上传、快照管理、批量删除，优先提供CLI操作，也支持交互式GUI向导。

---

## 快速开始

### 安装
推荐直接使用 pip 安装（无需源码）：
```bash
pip install ezIncrementalBackup
ezbackup init
```

如需开发或本地安装：
```bash
python setup.py sdist bdist_wheel
pip install dist/ezIncrementalBackup-*.whl
```

### 依赖环境
- Python 3.7 及以上
- 推荐安装 [7-Zip](https://www.7-zip.org/) 并将 7z.exe 加入 PATH（Linux: `sudo apt install p7zip-full`）
- 依赖包：click、py7zr、webdavclient3、PyYAML、tqdm、questionary

---

## 功能特性
- 全量/增量备份（自动快照，智能检测变动）
- 支持分卷压缩（优先调用7z命令行，多线程高效，自动回退py7zr）
- 支持本地和WebDAV远程备份目标
- 快照历史管理与一键还原
- 批量删除（apply-delete，自动清理源目录）
- CLI命令行与交互式GUI向导（`python -m ezIncrementalBackup.cli --gui`）
- 支持定时任务（结合cron/计划任务）
- 灵活排除目录/文件，支持多级排除

---

## 性能与环境建议
- **优先使用7z命令行压缩**：自动检测7z，速度远高于py7zr
- **硬盘建议**：强烈推荐SSD，机械硬盘在大量小文件场景下极慢
- **分卷建议**：建议适当增大分卷大小（如1024MB或更大），减少分卷数量可显著提升速度
- **py7zr仅作备选**：如未检测到7z命令，将自动回退到py7zr，速度会明显变慢
- **压缩进度**：7z命令行压缩时无详细进度条，py7zr压缩时会显示文件级进度

---

## 配置方法
请参考 `config.yaml`，填写源目录、目标、压缩、分卷等参数：
```yaml
source_dir: ./test
backup_type: incremental  # full 或 incremental
compress: true
split_size_mb: 1024       # 分卷大小，单位MB
exclude_dirs:
  - .git
  - node_modules
  - __pycache__
target:
  type: local             # local 或 webdav
  path: ./test-bk         # 本地路径
  url: https://webdav.example.com/backup  # WebDAV地址
  username: user
  password: pass
schedule: "0 2 * * *"     # cron表达式，凌晨2点自动备份
```
- `exclude_dirs` 支持多级目录排除，规则为：路径等于或以其为前缀即排除。

---

## 常用命令

### 初始化配置
```bash
ezbackup init
```

### 启动交互式GUI向导
```bash
ezbackup --gui
```
```bash
python -m ezIncrementalBackup.cli --gui
```
或
```bash
python ezIncrementalBackup/cli.py --gui
```

### 全量备份
```bash
ezbackup backup --type full --compress --split-size 1024
```

### 增量备份（推荐日常使用）
```bash
ezbackup backup --type incremental --compress --split-size 1024
```
- 首次增量备份会自动生成全量包和快照
- 后续只生成增量包和快照

### 快照历史与一键还原
- 每次备份后，`snapshot/` 目录下会自动生成快照副本
- 一键还原到某个快照对应的文件状态：
  ```bash
  ezbackup restore-all snapshot/snapshot_20250529_213019.json --to-source
  ```
  - 自动清空源目录并还原到快照时刻的状态

### 还原单个包
```bash
ezbackup restore full_20250529_213019.7z --target-dir ./restore_dir
ezbackup restore incremental_20250529_213540.7z --target-dir ./restore_dir
```

### 还原快照基准（不还原文件，仅影响下次增量基准）
```bash
ezbackup restore-snapshot snapshot/snapshot_20250529_213019.json
```

### 批量删除（根据删除清单自动删除源目录下的文件和目录）
```bash
ezbackup apply-delete deleted_20250529_214055.txt
```

### 其他命令
- 查看/编辑配置：`ezbackup config`
- 查看快照列表：`ezbackup show-snapshot`
- 上传分卷到WebDAV：`ezbackup upload`
- 清空源目录：`ezbackup clean-source`
- 删除快照：`ezbackup delete-snapshot <快照文件>`

---

## 推荐用法
1. **首次全量备份**：
   ```bash
   ezbackup backup --type full --compress --split-size 1024
   ```
2. **日常增量备份**：
   ```bash
   ezbackup backup --type incremental --compress --split-size 1024
   ```
3. **定时任务**：结合cron或计划任务定时执行备份命令
4. **一键还原**：
   ```bash
   ezbackup restore-all snapshot/snapshot_20250529_213019.json --to-source
   ```
5. **批量删除**：
   ```bash
   ezbackup apply-delete deleted_20250529_214055.txt
   ```

---

## 目录结构
```
ezIncrementalBackup/
├── ezIncrementalBackup/
│   ├── __init__.py
│   ├── cli.py
│   ├── cli_wizard.py
│   └── backup/
│       ├── __init__.py
│       ├── full.py
│       ├── incremental.py
│       ├── compress.py
│       └── webdav.py
├── setup.py
├── requirements.txt
├── README.md
├── LICENSE
├── config.yaml
└── snapshot/
```

---

## 开源协议
本项目基于 MIT License 开源，欢迎自由使用和二次开发。

---

## 常见问题 FAQ
- **Q: 7z命令行未检测到怎么办？**
  A: 请确保7z.exe已安装并加入PATH，Linux请用`sudo apt install p7zip-full`。
- **Q: WebDAV上传失败？**
  A: 请检查网络、WebDAV地址、用户名密码配置。
- **Q: 如何排除某些目录？**
  A: 在config.yaml的exclude_dirs中添加目录名或相对路径，支持多级。
- **Q: py7zr压缩很慢？**
  A: 推荐安装7z命令行，py7zr仅作备选。
- **Q: 如何用GUI操作？**
  A: 运行`python -m ezIncrementalBackup.cli --gui`，按提示操作。

---
如有更多需求或问题，欢迎随时反馈！
