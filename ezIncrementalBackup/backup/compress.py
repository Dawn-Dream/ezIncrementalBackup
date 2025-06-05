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


def compress_files_with_split(file_list, archive_path, split_size_mb=1024, base_dir=None , workers=1):
    """
    压缩指定文件列表，优先用7z命令行，否则用py7zr。
    file_list: 需要压缩的文件路径列表
    archive_path: 压缩包输出路径
    split_size_mb: 分卷大小（单位MB），默认1024
    base_dir: 相对路径基准目录，压缩包内文件路径以此为基准
    workers: 压缩线程数，默认1
    """
    archive = Path(archive_path).resolve()
    split_size = f"-v{split_size_mb}m"
    if is_7z_available():
        # 生成 filelist.txt 的绝对路径，避免 7z 找不到
        filelist_path = (archive.parent / "_filelist.txt").resolve()
        with open(filelist_path, 'w', encoding='utf-8') as f:
            for file_path in file_list:
                # 归一化为相对路径（以 base_dir 为基准），7z 支持 / 分隔符
                rel_path = os.path.relpath(file_path, base_dir) if base_dir else file_path
                f.write(f"{Path(rel_path).as_posix()}\n")
        # 7z 命令用 filelist.txt 的绝对路径，防止找不到
        cmd = [
            "7z", "a", "-t7z", "-m0=lzma2", "-mx=3", f"-mmt={workers}", split_size,
            str(archive), f"@{filelist_path.as_posix()}", "-spf2"
        ]
        print(f"[7z] 正在压缩: {' '.join(cmd)}")
        # 7z 的 cwd 可以为 base_dir，也可以不设（只要 filelist.txt 路径是绝对的）
        result = subprocess.run(cmd, cwd=base_dir if base_dir else None)
        try:
            filelist_path.unlink()
        except Exception:
            pass
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