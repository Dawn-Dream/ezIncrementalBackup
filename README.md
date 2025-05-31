# ezIncrementalBackup

一个跨平台（主要支持Linux/Windows）的高效增量/全量备份工具，支持分卷压缩、WebDAV上传、快照管理、批量删除，优先提供CLI操作。

## 性能与环境注意事项
- **优先使用7z命令行压缩**：本工具会自动检测系统是否有7z命令行（如7z.exe或p7zip），如有则自动用多线程压缩，速度远高于py7zr。
- **如何安装7z**：
  - Windows：请安装[7-Zip](https://www.7-zip.org/)，并将7z.exe所在目录加入PATH环境变量。
  - Linux：可用 `sudo apt install p7zip-full` 安装。
- **硬盘建议**：强烈推荐使用SSD，机械硬盘在大量小文件场景下极慢。
- **分卷建议**：如无特殊需求，建议适当增大分卷大小（如1024MB或更大），减少分卷数量可显著提升速度。
- **py7zr仅作备选**：如未检测到7z命令，将自动回退到py7zr，速度会明显变慢。
- **压缩进度**：7z命令行压缩时无详细进度条，py7zr压缩时会显示文件级进度。

## 功能特性
- 全量/增量备份（自动快照）
- 可选压缩，支持分卷
- 支持本地和WebDAV备份目标
- 定时自动备份（结合cron）
- 快照历史管理与一键还原
- 批量删除（apply-delete）
- CLI配置与操作

## 安装依赖
推荐使用 pip 安装打包后的 whl 文件：
```bash
python setup.py sdist bdist_wheel
pip install dist/ezIncrementalBackup-0.1.0-py3-none-any.whl
```

## 配置
请参考 `config.yaml`，填写源目录、目标、压缩、分卷等参数。

```yaml
source_dir: ./test
backup_type: incremental  # full or incremental
compress: true
split_size_mb: 1024       # 分卷大小，单位MB
target:
  type: local             # local or webdav
  path: ./test-bk         # 本地路径
  url: https://webdav.example.com/backup  # WebDAV地址
  username: user
  password: pass
schedule: "0 2 * * *"     # cron表达式，凌晨2点自动备份
```

## 常用命令（新版，全部用 ezbackup 命令）

### 初始化配置
```bash
ezbackup init
```
### 新增：gui界面
```bash
python cli.py --gui
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

### 快照历史与还原
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

## 目录结构（新版标准包结构）
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
└── snapshot/
```

---
如有更多需求或问题，欢迎随时反馈！ 
