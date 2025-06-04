import os
import shutil
import json
from pathlib import Path
from hashlib import md5
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
from ..utils import is_excluded_path

def file_md5(path):
    hash_md5 = md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def get_file_stat(path):
    p = Path(path)
    stat = p.stat()
    return str(p), stat.st_mtime, stat.st_size

def get_file_info_with_md5(path):
    p = Path(path)
    stat = p.stat()
    return str(p), {
        'mtime': stat.st_mtime,
        'size': stat.st_size,
        'md5': file_md5(p)
    }

def load_snapshot(snapshot_path):
    if not Path(snapshot_path).exists():
        return {}
    with open(snapshot_path, 'r') as f:
        return json.load(f)

def save_snapshot(snapshot_path, data):
    with open(snapshot_path, 'w') as f:
        json.dump(data, f, indent=2)

def incremental_backup(source_dir, snapshot_path, exclude_dirs=None, workers=None):
    """
    增量备份核心函数。（AI生成的文档 自己懒得写:>）
    该函数通过对比当前源目录与上一次快照，找出本次变动（新增/修改/删除）的文件和目录。
    
    参数:
        source_dir (str): 源目录路径。
        snapshot_path (str): 快照文件路径。
        exclude_dirs (set or list, 可选): 需要排除的目录名集合。
        workers (int, 可选): 并发进程数，None为自动。

    返回:
        tuple: (changed_files, deleted_all)
            changed_files: 本次有变动（新增/修改）的文件路径列表
            deleted_all: 本次被删除的文件和目录路径列表

    实现思路：
    1. 首先遍历源目录，收集所有文件路径，排除exclude_dirs中指定的目录。
    2. 多进程方式收集所有文件的mtime和size信息（stat），与快照对比，未变化的直接复用快照信息。
    3. 对于mtime或size有变化的文件，再多进程计算md5，判断内容是否真正变动。
    4. 统计所有当前存在的文件和目录路径，形成current_paths集合。
    5. 对比快照，找出快照中存在但current_paths中不存在的文件和目录，判定为已删除。
    6. 返回本次变动的文件列表（changed_files）和被删除的文件/目录列表（deleted_all）。
    7. 最后保存新的快照到snapshot_path。

    """
    source = Path(source_dir)
    prev_snapshot = load_snapshot(snapshot_path)
    new_snapshot = {}
    changed_files = []
    current_paths = set()
    exclude_dirs = set(exclude_dirs) if exclude_dirs else set()
    # 先收集所有文件路径
    all_files = []
    for root, dirs, files in os.walk(source):
        rel_root = os.path.relpath(root, source).replace("\\", "/")
        dirs[:] = [d for d in dirs if not is_excluded_path((rel_root + "/" + d).lstrip("/"), exclude_dirs)]
        for file in files:
            rel_file = (rel_root + "/" + file).lstrip("/")
            if is_excluded_path(rel_file, exclude_dirs):
                continue
            all_files.append(str(Path(root) / file))
    # 第一步：多进程收集 stat
    stat_map = {}
    with tqdm(total=len(all_files), desc='初筛', unit='file') as pbar:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            future_to_path = {executor.submit(get_file_stat, f): f for f in all_files}
            for future in as_completed(future_to_path):
                path, mtime, size = future.result()
                # !暂时解决方案
                # 统一路径分隔符，忽略 \ 与 / 的区别
                norm_path = path.replace("\\", "/")
                stat_map[norm_path] = (mtime, size)
                pbar.update(1)
    # 第二步：筛选出需要算 md5 的文件
    need_md5 = []
    for path, (mtime, size) in stat_map.items():
        prev_info = prev_snapshot.get(path)
        if prev_info and prev_info.get('mtime') == mtime and prev_info.get('size') == size:
            # 直接复用快照
            new_snapshot[path] = prev_info
            current_paths.add(path)
        else:
            need_md5.append(path)
    # 第三步：多进程算 md5
    with tqdm(total=len(need_md5), desc='MD5校验', unit='file') as pbar:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            future_to_path = {executor.submit(get_file_info_with_md5, f): f for f in need_md5}
            for future in as_completed(future_to_path):
                path, info = future.result()
                new_snapshot[path] = info
                prev_info = prev_snapshot.get(path)
                if prev_info != info:
                    changed_files.append(path)
                current_paths.add(path)
                pbar.update(1)
    # 统计当前所有目录
    for root, dirs, files in os.walk(source):
        rel_root = os.path.relpath(root, source).replace("\\", "/")
        dirs[:] = [d for d in dirs if not is_excluded_path((rel_root + "/" + d).lstrip("/"), exclude_dirs)]
        for d in dirs:
            dir_path = str(Path(root) / d)
            current_paths.add(dir_path)
    # 检查被删除的文件和目录
    deleted_files = []
    deleted_dirs = []
    for old_path in prev_snapshot:
        if old_path not in current_paths:
            deleted_files.append(old_path)
    # 额外检查快照中存在但当前不存在的目录
    prev_dirs = set()
    for p in prev_snapshot:
        parent = str(Path(p).parent)
        while parent and parent not in prev_dirs:
            prev_dirs.add(parent)
            parent = str(Path(parent).parent)
    for d in prev_dirs:
        if d not in current_paths and d not in deleted_dirs:
            deleted_dirs.append(d)
    # 目录按路径长度从长到短排序，保证先删子目录
    deleted_dirs = sorted(deleted_dirs, key=lambda x: -len(x))
    # 过滤掉源目录本身
    deleted_dirs = [d for d in deleted_dirs if str(source) != d]
    deleted_files = [f for f in deleted_files if str(source) != f]
    deleted_all = deleted_files + deleted_dirs
    save_snapshot(snapshot_path, new_snapshot)
    return changed_files, deleted_all 