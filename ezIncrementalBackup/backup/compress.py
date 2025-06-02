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

def compress_files_with_split(file_list, archive_path, split_size_mb=1024, base_dir=None, arcname_map=None):
    """
    压缩指定文件列表，优先用7z命令行，否则用py7zr。file_list为文件路径列表，base_dir为相对路径基准目录。
    arcname_map: {绝对路径: 包内路径}
    """
    archive = Path(archive_path)
    split_size = f"-v{split_size_mb}m"
    if is_7z_available():
        # 创建临时目录用于存放文件列表和映射文件
        temp_dir = archive.parent / f"_temp_{archive.stem}"
        temp_dir.mkdir(exist_ok=True)
        try:
            # 1. 创建文件列表
            filelist_path = temp_dir / "_filelist.txt"
            with open(filelist_path, 'w', encoding='utf-8') as f:
                for file_path in file_list:
                    p = Path(file_path)
                    if not p.is_file():
                        continue
                    abs_path = str(p.resolve())
                    f.write(f"{abs_path}\n")
            
            # 2. 如果有 arcname_map，创建映射文件（只为存在的文件写入）
            listfile_path = temp_dir / "_listfile.txt"
            with open(listfile_path, 'w', encoding='utf-8') as f:
                for file_path in file_list:
                    p = Path(file_path)
                    if not p.is_file():
                        continue
                    abs_path = str(p.resolve())
                    if abs_path in arcname_map:
                        f.write(f"{abs_path} = {arcname_map[abs_path]}\n")
            
            # 3. 构建命令
            cmd = [
                "7z", "a", "-t7z", "-m0=lzma2", "-mx=3", "-mmt=on", split_size,
                str(archive), f"@{filelist_path}"
            ]
            if listfile_path:
                cmd.extend(["-i@" + str(listfile_path)])
            
            print(f"[7z] 正在压缩: {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, cwd=base_dir if base_dir else None)
                if result.returncode != 0:
                    print("7z 压缩失败，但程序不会退出。")
                    return []
            except Exception as e:
                print(f'7z 压缩异常: {e}，程序不会退出。')
                return []
            
            parts = sorted(archive.parent.glob(f"{archive.name}.part*"))
            if not parts:
                parts = [archive]
            return [str(p) for p in parts]
        finally:
            # 清理临时文件
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    else:
        print("[py7zr] 未检测到7z命令，使用py7zr压缩，速度较慢...")
        split_size_bytes = int(split_size_mb) * 1024 * 1024
        with py7zr.SevenZipFile(archive, 'w', filters=[{'id': py7zr.FILTER_LZMA2}]) as archive_file:
            for file_path in tqdm(file_list, desc='压缩进度', unit='file'):
                file_path = Path(file_path)
                if not file_path.is_file():
                    continue
                arcname = arcname_map[str(file_path)] if arcname_map and str(file_path) in arcname_map else (os.path.relpath(file_path, base_dir) if base_dir else file_path.name)
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