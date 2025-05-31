# ezIncrementalBackup

一个跨平台（主要支持Linux/Windows）的高效增量/全量备份工具，支持分卷压缩、WebDAV上传、快照管理、批量删除，优先提供CLI操作。

## 功能特性
- 全量/增量备份（自动快照）
- 可选压缩，支持分卷
- 支持本地和WebDAV备份目标
- 定时自动备份（结合cron）
- 快照历史管理与一键还原
- 批量删除（apply-delete）
- CLI配置与操作

## 安装依赖
```bash
pip install -r requirements.txt
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

## 常用命令

### 初始化配置
```bash
python cli.py init
```
### 新增：gui界面
```bash
python cli.py --gui
```
### 全量备份
```bash
python cli.py backup --type full --compress --split-size 1024
```

### 增量备份（推荐日常使用）
```bash
python cli.py backup --type incremental --compress --split-size 1024
```
- 首次增量备份会自动生成全量包和快照
- 后续只生成增量包和快照

### 快照历史与还原
- 每次备份后，`snapshot/` 目录下会自动生成快照副本
- 一键还原到某个快照对应的文件状态：
  ```bash
  python cli.py restore-all snapshot/snapshot_20250529_213019.json --to-source
  ```
  - 自动清空源目录并还原到快照时刻的状态

### 还原单个包
```bash
python cli.py restore full_20250529_213019.7z --target-dir ./restore_dir
python cli.py restore incremental_20250529_213540.7z --target-dir ./restore_dir
```

### 还原快照基准（不还原文件，仅影响下次增量基准）
```bash
python cli.py restore-snapshot snapshot/snapshot_20250529_213019.json
```

### 批量删除（根据删除清单自动删除源目录下的文件和目录）
```bash
python cli.py apply-delete deleted_20250529_214055.txt
```

## 推荐用法
1. **首次全量备份**：
   ```bash
   python cli.py backup --type full --compress --split-size 1024
   ```
2. **日常增量备份**：
   ```bash
   python cli.py backup --type incremental --compress --split-size 1024
   ```
3. **定时任务**：结合cron或计划任务定时执行备份命令
4. **一键还原**：
   ```bash
   python cli.py restore-all snapshot/snapshot_20250529_213019.json --to-source
   ```
5. **批量删除**：
   ```bash
   python cli.py apply-delete deleted_20250529_214055.txt
   ```

## 常见问题
- **为什么增量包里有deleted_xxx.txt？**
  > 这是自动记录本次被删除的文件和目录，便于还原和同步。
- **如何彻底同步目录？**
  > 用 restore-all --to-source 或 apply-delete 命令，自动清空/同步源目录。
- **如何只还原快照基准？**
  > 用 restore-snapshot 命令。
- **如何只清空源目录？**
  > 可用 restore-all --to-source 或自定义 clean-source 命令。

## 目录结构
```
ezIncrementalBackup/
├── backup/
│   ├── full.py
│   ├── incremental.py
│   ├── compress.py
│   └── webdav.py
├── cli.py
├── config.yaml
├── requirements.txt
├── README.md
└── snapshot/
```

---
如有更多需求或问题，欢迎随时反馈！ 
