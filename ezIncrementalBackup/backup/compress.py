import os
import shutil
import py7zr
from pathlib import Path
import math
import subprocess
from tqdm import tqdm

def is_7z_available():
    """检测系统是否有 7z 命令行工具"""
    from shutil import which
    return which("7z") is not None

def compress_with_split(source_dir, archive_path, split_size_mb=1024):
    """
    使用7z命令行（如有）或py7zr对source_dir进行分卷压缩，分卷大小为split_size_mb。
    """
    source = Path(source_dir)
    archive = Path(archive_path)
    split_size = f"-v{split_size_mb}m"
    if is_7z_available():
        cmd = [
            "7z", "a", "-t7z", "-m0=lzma2", "-mx=3", "-mmt=on", split_size,
            str(archive), str(source)
        ]
        print(f"[7z] 正在压缩: {' '.join(cmd)}")
        result = subprocess.run(cmd)  # 直接输出到终端
        if result.returncode != 0:
            raise RuntimeError("7z 压缩失败")
        parts = sorted(archive.parent.glob(f"{archive.name}.part*"))
        if not parts:
            parts = [archive]
        return [str(p) for p in parts]
    else:
        # 回退到 py7zr
        print("[py7zr] 未检测到7z命令，使用py7zr压缩，速度较慢...")
        split_size_bytes = int(split_size_mb) * 1024 * 1024
        with py7zr.SevenZipFile(archive, 'w', filters=[{'id': py7zr.FILTER_LZMA2}]) as archive_file:
            archive_file.writeall(str(source), arcname='.')
        file_size = archive.stat().st_size
        if file_size > split_size_bytes:
            with open(archive, 'rb') as f:
                idx = 0
                while True:
                    chunk = f.read(split_size_bytes)
                    if not chunk:
                        break
                    part_path = archive.parent / f"{archive.name}.part{idx+1}"
                    with open(part_path, 'wb') as pf:
                        pf.write(chunk)
                    idx += 1
            archive.unlink()  # 删除原始大包
            return [str(archive.parent / f"{archive.name}.part{i+1}") for i in range(idx)]
        else:
            return [str(archive)]

def compress_files_with_split(file_list, archive_path, split_size_mb=1024, base_dir=None):
    """
    压缩指定文件列表，优先用7z命令行，否则用py7zr。file_list为文件路径列表，base_dir为相对路径基准目录。
    """
    archive = Path(archive_path)
    split_size = f"-v{split_size_mb}m"
    if is_7z_available():
        filelist_path = archive.parent / "_filelist.txt"
        with open(filelist_path, 'w', encoding='utf-8') as f:
            for file_path in file_list:
                rel_path = os.path.relpath(file_path, base_dir) if base_dir else file_path
                f.write(f"{rel_path}\n")
        cmd = [
            "7z", "a", "-t7z", "-m0=lzma2", "-mx=3", "-mmt=on", split_size,
            str(archive), f"@{filelist_path}", "-spf2"
        ]
        print(f"[7z] 正在压缩: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=base_dir if base_dir else None)  # 直接输出到终端
        filelist_path.unlink(missing_ok=True)
        if result.returncode != 0:
            raise RuntimeError("7z 压缩失败")
        parts = sorted(archive.parent.glob(f"{archive.name}.part*"))
        if not parts:
            parts = [archive]
        return [str(p) for p in parts]
    else:
        print("[py7zr] 未检测到7z命令，使用py7zr压缩，速度较慢...")
        split_size_bytes = int(split_size_mb) * 1024 * 1024
        with py7zr.SevenZipFile(archive, 'w', filters=[{'id': py7zr.FILTER_LZMA2}]) as archive_file:
            for file_path in tqdm(file_list, desc='压缩进度', unit='file'):
                file_path = Path(file_path)
                arcname = os.path.relpath(file_path, base_dir) if base_dir else file_path.name
                archive_file.write(str(file_path), arcname=arcname)
        file_size = archive.stat().st_size
        if file_size > split_size_bytes:
            with open(archive, 'rb') as f:
                idx = 0
                while True:
                    chunk = f.read(split_size_bytes)
                    if not chunk:
                        break
                    part_path = archive.parent / f"{archive.name}.part{idx+1}"
                    with open(part_path, 'wb') as pf:
                        pf.write(chunk)
                    idx += 1
            archive.unlink()
            return [str(archive.parent / f"{archive.name}.part{i+1}") for i in range(idx)]
        else:
            return [str(archive)] 