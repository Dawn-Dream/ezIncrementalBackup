import os
import shutil
from pathlib import Path
from ..utils import is_excluded_path

def full_backup(source_dir, target_dir, exclude_dirs=None):
    """
    执行全量备份，将source_dir下所有文件复制到target_dir。
    exclude_dirs: 需要排除的目录（多级目录支持）
    """
    source = Path(source_dir)
    target = Path(target_dir)
    if not source.exists():
        raise FileNotFoundError(f"源目录不存在: {source}")
    target.mkdir(parents=True, exist_ok=True)
    exclude_dirs = set(exclude_dirs) if exclude_dirs else set()
    for root, dirs, files in os.walk(source):
        rel_root = os.path.relpath(root, source).replace("\\", "/")
        # 递归过滤目录
        dirs[:] = [d for d in dirs if not is_excluded_path((rel_root + "/" + d).lstrip("/"), exclude_dirs)]
        dest_dir = target / rel_root
        dest_dir.mkdir(parents=True, exist_ok=True)
        for file in files:
            rel_file = (rel_root + "/" + file).lstrip("/")
            if is_excluded_path(rel_file, exclude_dirs):
                continue
            src_file = Path(root) / file
            dst_file = dest_dir / file
            shutil.copy2(src_file, dst_file) 