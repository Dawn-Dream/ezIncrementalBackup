import py7zr
from pathlib import Path
import math
import os
from tqdm import tqdm

def compress_with_split(source_dir, archive_path, split_size_mb=1024):
    """
    使用py7zr对source_dir进行分卷压缩，分卷大小为split_size_mb。
    """
    source = Path(source_dir)
    archive = Path(archive_path)
    split_size = split_size_mb * 1024 * 1024
    with py7zr.SevenZipFile(archive, 'w', filters=[{'id': py7zr.FILTER_LZMA2}]) as archive_file:
        archive_file.writeall(str(source), arcname='.')
    # 分卷
    file_size = archive.stat().st_size
    if file_size > split_size:
        with open(archive, 'rb') as f:
            idx = 0
            while True:
                chunk = f.read(split_size)
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
    压缩指定文件列表，支持分卷。file_list为文件路径列表，base_dir为相对路径基准目录。
    """
    archive = Path(archive_path)
    split_size = split_size_mb * 1024 * 1024
    with py7zr.SevenZipFile(archive, 'w', filters=[{'id': py7zr.FILTER_LZMA2}]) as archive_file:
        for file_path in tqdm(file_list, desc='压缩进度', unit='file'):
            file_path = Path(file_path)
            arcname = os.path.relpath(file_path, base_dir) if base_dir else file_path.name
            archive_file.write(str(file_path), arcname=arcname)
    # 分卷
    file_size = archive.stat().st_size
    if file_size > split_size:
        with open(archive, 'rb') as f:
            idx = 0
            while True:
                chunk = f.read(split_size)
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