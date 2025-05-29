import os
import shutil
from pathlib import Path

def full_backup(source_dir, target_dir):
    """
    执行全量备份，将source_dir下所有文件复制到target_dir。
    """
    source = Path(source_dir)
    target = Path(target_dir)
    if not source.exists():
        raise FileNotFoundError(f"源目录不存在: {source}")
    target.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(source):
        rel_path = os.path.relpath(root, source)
        dest_dir = target / rel_path
        dest_dir.mkdir(parents=True, exist_ok=True)
        for file in files:
            src_file = Path(root) / file
            dst_file = dest_dir / file
            shutil.copy2(src_file, dst_file) 