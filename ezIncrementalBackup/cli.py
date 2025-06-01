import click
import yaml
import os
from pathlib import Path
from .backup.full import full_backup
from .backup.incremental import incremental_backup, file_md5
from .backup.compress import compress_with_split, compress_files_with_split
from .backup.webdav import upload_to_webdav
import datetime
import tempfile
import json
import sys
import subprocess
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
import re
import py7zr
from .utils import is_excluded_path

CONFIG_PATH = 'config.yaml'
SNAPSHOT_PATH = 'snapshot/last_snapshot.json'

def get_file_info(path):
    p = Path(path)
    stat = p.stat()
    return path, {
        'mtime': stat.st_mtime,
        'size': stat.st_size,
        'md5': file_md5(p)
    }

def safe_rmtree(path, source_dir, exclude_dirs):
    rel_path = os.path.relpath(path, source_dir).replace("\\", "/")
    if is_excluded_path(rel_path, exclude_dirs):
        return
    if path.is_file() or path.is_symlink():
        path.unlink()
    elif path.is_dir():
        for item in list(path.iterdir()):
            safe_rmtree(item, source_dir, exclude_dirs)
        if len(list(path.iterdir())) == 0 and not is_excluded_path(rel_path, exclude_dirs):
            path.rmdir()

@click.group()
def cli():
    """ezIncrementalBackup 命令行工具

    注意：webdav未经过实验！推荐使用本地备份

    额外参数:
      --gui    启动交互式向导界面
    """
    pass

@cli.command()
def init():
    """初始化配置文件"""
    if not Path(CONFIG_PATH).exists():
        with open(CONFIG_PATH, 'w') as f:
            f.write("""source_dir: /path/to/source\nbackup_type: incremental  # full or incremental\ncompress: true\nsplit_size_mb: 1024\ntarget:\n  type: local\n  path: /path/to/backup\n  url: https://webdav.example.com/backup\n  username: user\n  password: pass\nexclude_dirs:\n  - .git\n  - node_modules\n  - __pycache__\nschedule: '0 2 * * *'\n""")
        click.echo("已生成默认配置文件 config.yaml")
    else:
        click.echo("config.yaml 已存在")

@cli.command()
@click.option('--type', type=click.Choice(['full', 'incremental']), default=None, help='备份类型')
@click.option('--compress/--no-compress', default=None, help='是否压缩')
@click.option('--split-size', type=int, default=None, help='分卷大小（MB）')
@click.option('--workers', type=int, default=None, help='并发进程数')
def backup(type, compress, split_size, workers):
    """执行备份操作"""
    # 读取配置
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    source_dir = config['source_dir']
    backup_type = type or config.get('backup_type', 'incremental')
    compress_flag = compress if compress is not None else config.get('compress', True)
    split_size_mb = split_size or config.get('split_size_mb', 1024)
    target = config['target']
    exclude_dirs = set(config.get('exclude_dirs', []))
    target_dir = target.get('path', './backup_output')
    workers = workers or config.get('workers', None)
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    Path('snapshot').mkdir(exist_ok=True)

    # 备份
    now_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    snapshot_history_path = Path('snapshot') / f'snapshot_{now_str}.json'
    if backup_type == 'full' or (backup_type == 'incremental' and not Path(SNAPSHOT_PATH).exists()):
        if backup_type == 'incremental':
            click.echo('未检测到快照，自动切换为全量备份...')
        click.echo('执行全量备份...')
        if compress_flag:
            click.echo('直接压缩源目录并分卷...')
            # 获取所有文件列表
            all_files = []
            for root, dirs, files in os.walk(source_dir):
                rel_root = os.path.relpath(root, source_dir).replace("\\", "/")
                # 递归过滤目录
                dirs[:] = [d for d in dirs if not is_excluded_path((rel_root + "/" + d).lstrip("/"), exclude_dirs)]
                for file in files:
                    rel_file = (rel_root + "/" + file).lstrip("/")
                    if is_excluded_path(rel_file, exclude_dirs):
                        continue
                    all_files.append(str(Path(root) / file))
            archive_path = Path(target_dir) / f'full_{now_str}.7z'
            parts = compress_files_with_split(all_files, archive_path, split_size_mb, base_dir=source_dir)
            click.echo(f'生成分卷: {parts}')
        else:
            click.echo('未启用压缩，直接复制源文件到目标目录...')
            full_backup(source_dir, target_dir, exclude_dirs=exclude_dirs)
            parts = [str(p) for p in Path(target_dir).glob('*') if p.is_file()]
        # 全量备份后生成快照
        snapshot = {}
        # 统计所有文件路径
        all_files = []
        for root, dirs, files in os.walk(source_dir):
            rel_root = os.path.relpath(root, source_dir).replace("\\", "/")
            # 递归过滤目录
            dirs[:] = [d for d in dirs if not is_excluded_path((rel_root + "/" + d).lstrip("/"), exclude_dirs)]
            for file in files:
                rel_file = (rel_root + "/" + file).lstrip("/")
                if is_excluded_path(rel_file, exclude_dirs):
                    continue
                all_files.append(str(Path(root) / file))
        with tqdm(total=len(all_files), desc='生成快照', unit='file') as pbar:
            with ProcessPoolExecutor() as executor:
                future_to_path = {executor.submit(get_file_info, f): f for f in all_files}
                for future in as_completed(future_to_path):
                    path, info = future.result()
                    snapshot[path] = info
                    pbar.update(1)
        with open(SNAPSHOT_PATH, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2)
        with open(snapshot_history_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2)
    else:
        click.echo('执行增量备份...')
        changed, deleted = incremental_backup(source_dir, SNAPSHOT_PATH, exclude_dirs=exclude_dirs, workers=workers)
        files_to_pack = changed.copy()
        deleted_list_arcname = None
        valid_deleted = []
        if deleted:
            deleted_list_arcname = f'deleted_{now_str}.txt'
            deleted_list_path = Path(source_dir) / deleted_list_arcname
            with open(deleted_list_path, 'w', encoding='utf-8') as f:
                for path in deleted:
                    try:
                        rel_path = os.path.relpath(path, source_dir)
                    except ValueError:
                        continue  # 跳过非法路径
                    if rel_path in ('.', '', '..') or rel_path.startswith('..'):
                        continue
                    f.write(rel_path + '\n')
                    valid_deleted.append(path)
            files_to_pack.append(str(deleted_list_path))
        else:
            valid_deleted = []
        click.echo(f'本次增量备份变动文件数: {len(changed)}，删除文件数: {len(valid_deleted)}')
        if compress_flag and files_to_pack:
            click.echo('压缩本次变动文件和删除清单并分卷...')
            archive_path = Path(target_dir) / f'incremental_{now_str}.7z'
            parts = compress_files_with_split(files_to_pack, archive_path, split_size_mb, base_dir=source_dir)
            click.echo(f'生成分卷: {parts}')
        elif files_to_pack:
            parts = files_to_pack
        else:
            parts = []
        # 删除临时删除清单文件
        if deleted_list_arcname:
            del_path = Path(source_dir) / deleted_list_arcname
            if del_path.exists():
                os.remove(del_path)

    # WebDAV上传
    if target['type'] == 'webdav':
        click.echo('上传到WebDAV...')
        upload_to_webdav(parts, target)
        click.echo('WebDAV上传完成')
    else:
        click.echo('备份已保存到本地')

    # 备份完成后保存快照副本
    if Path(SNAPSHOT_PATH).exists():
        import shutil
        shutil.copy2(SNAPSHOT_PATH, snapshot_history_path)

@cli.command()
@click.argument('archive', type=click.Path(exists=True))
@click.option('--target-dir', type=click.Path(), default=None, help='恢复到的目标目录')
def restore(archive, target_dir):
    """恢复备份（支持自动同步删除）"""
    import py7zr
    import shutil
    from pathlib import Path
    import os
    click.echo(f"解压 {archive} ...")
    if target_dir is None:
        with py7zr.SevenZipFile(archive, mode='r') as z:
            z.extractall()
        extract_dir = Path('.')
    else:
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        with py7zr.SevenZipFile(archive, mode='r') as z:
            z.extractall(path=str(target_dir))
        extract_dir = target_dir
    # 查找并处理删除清单
    deleted_txt = None
    for f in extract_dir.glob('deleted_*.txt'):
        deleted_txt = f
        break
    if deleted_txt and deleted_txt.exists():
        click.echo(f"检测到删除清单: {deleted_txt}，自动删除对应文件...")
        with open(deleted_txt, 'r', encoding='utf-8') as f:
            for line in f:
                file_path = line.strip()
                if not file_path:
                    continue
                abs_path = extract_dir / Path(file_path)
                if abs_path.exists():
                    try:
                        if abs_path.is_file():
                            abs_path.unlink()
                        elif abs_path.is_dir():
                            shutil.rmtree(abs_path)
                        click.echo(f"已删除: {abs_path}")
                    except Exception as e:
                        click.echo(f"删除失败: {abs_path}，原因: {e}")
    click.echo("恢复完成！")

@cli.command()
def config():
    """编辑/显示配置"""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        click.echo(f.read())

@cli.command()
def show_snapshot():
    """显示快照信息"""
    if Path(SNAPSHOT_PATH).exists():
        with open(SNAPSHOT_PATH, 'r') as f:
            click.echo(f.read())
    else:
        click.echo('暂无快照信息')

@cli.command()
def upload():
    """上传备份到WebDAV"""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    target = config['target']
    target_dir = target.get('path', './backup_output')
    parts = [str(p) for p in Path(target_dir).glob('*.part*')] or [str(p) for p in Path(target_dir).glob('*.7z')]
    if target['type'] == 'webdav':
        upload_to_webdav(parts, target)
        click.echo('WebDAV上传完成')
    else:
        click.echo('目标不是WebDAV，无需上传')

@cli.command()
@click.argument('snapshot_file', type=click.Path(exists=True))
def restore_snapshot(snapshot_file):
    """恢复快照文件为当前快照基准"""
    import shutil
    shutil.copy2(snapshot_file, SNAPSHOT_PATH)
    click.echo(f'已恢复快照: {snapshot_file} -> {SNAPSHOT_PATH}')

@cli.command()
@click.argument('snapshot_file', type=click.Path(exists=True))
@click.option('--target-dir', type=click.Path(), default=None, help='恢复到的目标目录')
@click.option('--to-source', is_flag=True, default=False, help='还原到配置文件中的源目录并自动清空')
def restore_all(snapshot_file, target_dir, to_source):
    """一键还原到指定快照对应的文件状态，可自动清空源目录"""
    import re
    import shutil
    from pathlib import Path
    import py7zr
    import yaml
    # 1. 解析快照时间戳
    snap_name = Path(snapshot_file).stem
    m = re.match(r'snapshot_(\d{8}_\d{6})', snap_name)
    if not m:
        click.echo('快照文件名格式不正确！')
        return
    ts = m.group(1)
    # 2. 选择还原目录和备份包目录
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    backup_dir = Path(config['target']['path'])
    exclude_dirs = set(config.get('exclude_dirs', []))
    if to_source:
        target_dir = Path(config['source_dir'])
        click.echo(f'自动还原到源目录: {target_dir}')
        if target_dir.exists():
            items = [item for item in target_dir.iterdir() if not is_excluded_path(os.path.relpath(item, target_dir).replace("\\", "/"), exclude_dirs)]
            if items:
                click.echo('还原前将清空以下内容：')
                for item in items:
                    click.echo(str(item))
                confirm = input('确认要清空这些内容并还原吗？(y/yes 才会执行): ').strip().lower()
                if confirm not in ('y', 'yes'):
                    click.echo('操作已取消，未清空也未还原。')
                    return
            for item in target_dir.iterdir():
                safe_rmtree(item, target_dir, exclude_dirs)
            click.echo(f'已清空目录: {target_dir}')
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
    else:
        target_dir = Path(target_dir) if target_dir else Path('.')
    # 3. 找到全量包和所有相关增量包
    all_pkgs = sorted(list(backup_dir.glob('*.7z')) + list(backup_dir.glob('*.7z.001')))
    # 构建基名到包的映射，优先 .7z.001
    pkg_map = {}
    for pkg in all_pkgs:
        m = re.match(r'(full_\d{8}_\d{6}|incremental_\d{8}_\d{6})\.7z(\.001)?$', pkg.name)
        if m:
            base = m.group(1)
            # 优先 .7z.001
            if base not in pkg_map or str(pkg).endswith('.7z.001'):
                pkg_map[base] = pkg
    # 选取最接近快照时间戳且不大于快照的全量包
    full_pkg = None
    for base, pkg in pkg_map.items():
        if base.startswith('full_'):
            if base[5:] <= ts:
                if (not full_pkg) or (base[5:] > full_pkg[0][5:]):
                    full_pkg = (base, pkg)
    # 选取所有相关增量包
    incr_pkgs = []
    for base, pkg in pkg_map.items():
        if base.startswith('incremental_'):
            if base[12:] <= ts:
                incr_pkgs.append((base, pkg))
    incr_pkgs = [p[1] for p in sorted(incr_pkgs, key=lambda x: x[0][12:])]
    if not full_pkg:
        click.echo('未找到对应的全量包！')
        return
    full_pkg = full_pkg[1]
    # 4. 依次解压
    click.echo(f'解压全量包: {full_pkg}')
    # 优先用 7z 命令行解压分卷包
    def try_7z_extract(pkg, target_dir):
        import shutil
        import subprocess
        pkg = str(pkg)
        target_dir = str(target_dir)
        try:
            result = subprocess.run([
                '7z', 'x', pkg, f'-o{target_dir}', '-y', '-mmt=on'
            ], check=True)
            return True
        except Exception as e:
            click.echo(f'7z 命令行解压失败: {e}')
            return False
    extracted = False
    if str(full_pkg).endswith('.7z.001') or str(full_pkg).endswith('.7z'):
        # 检查所有分卷是否存在（仅分卷包）
        if str(full_pkg).endswith('.7z.001'):
            idx = 1
            while True:
                part_file = full_pkg.with_suffix(full_pkg.suffix[:-4] + f'.{idx:03d}')
                if not part_file.exists():
                    break
                idx += 1
        # 优先尝试 7z 命令行
        if shutil.which('7z'):
            click.echo('7z 命令行解压中，请关注终端输出进度...')
            extracted = try_7z_extract(full_pkg, target_dir)
        if not extracted:
            try:
                click.echo('使用 py7zr 解压中，请稍候...')
                with py7zr.SevenZipFile(full_pkg, mode='r') as z:
                    z.extractall(path=str(target_dir))
                click.echo('py7zr 解压完成。')
                extracted = True
            except Exception as e:
                click.echo(f'py7zr 解压失败: {e}')
                return
    else:
        click.echo('不支持的包类型，请选择 .7z 或 .7z.001 文件')
        return
    # 5. 还原快照
    shutil.copy2(snapshot_file, SNAPSHOT_PATH)
    click.echo(f'已恢复快照: {snapshot_file} -> {SNAPSHOT_PATH}')
    click.echo('一键还原完成！')

@cli.command()
@click.argument('deleted_list', type=click.Path(exists=True))
def apply_delete(deleted_list):
    """根据删除清单批量删除源目录下的文件和文件夹"""
    import yaml
    import shutil
    from pathlib import Path
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    source_dir = Path(config['source_dir'])
    exclude_dirs = set(config.get('exclude_dirs', []))
    with open(deleted_list, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    files = []
    dirs = []
    to_delete = []
    for rel_path in lines:
        rel_path_norm = rel_path.replace("\\", "/")
        if is_excluded_path(rel_path_norm, exclude_dirs):
            click.echo(f'跳过保护目录/文件: {rel_path}')
            continue
        abs_path = source_dir / rel_path_norm
        if abs_path.exists():
            to_delete.append(abs_path)
            if abs_path.is_file() or abs_path.is_symlink():
                files.append(abs_path)
            elif abs_path.is_dir():
                dirs.append(abs_path)
        else:
            click.echo(f'未找到: {abs_path}')
    # 删除前确认
    if to_delete:
        click.echo('即将删除以下文件/目录：')
        for p in to_delete:
            click.echo(str(p))
        confirm = input('确认要删除这些文件/目录吗？(y/yes 才会执行): ').strip().lower()
        if confirm not in ('y', 'yes'):
            click.echo('操作已取消，未删除任何文件/目录。')
            return
    # 先删文件
    for f in files:
        try:
            safe_rmtree(f, source_dir, exclude_dirs)
            click.echo(f'已删除文件: {f}')
        except Exception as e:
            click.echo(f'删除失败: {f}，原因: {e}')
    # 再删目录，按路径长度从长到短
    dirs = sorted(dirs, key=lambda x: -len(str(x)))
    for d in dirs:
        try:
            safe_rmtree(d, source_dir, exclude_dirs)
            click.echo(f'已删除文件夹: {d}')
        except Exception as e:
            click.echo(f'删除失败: {d}，原因: {e}')

@cli.command()
def clean_source():
    """清空配置文件中的源目录"""
    import yaml
    import shutil
    from pathlib import Path
    import os
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    source_dir = Path(config['source_dir'])
    exclude_dirs = set(config.get('exclude_dirs', []))
    click.echo(f"正在清空源目录: {source_dir}")
    if source_dir.exists():
        for item in source_dir.iterdir():
            safe_rmtree(item, source_dir, exclude_dirs)
        click.echo(f"已清空目录: {source_dir}")
    else:
        click.echo(f"源目录不存在: {source_dir}，无需清空")

if '--gui' in sys.argv:
    sys.argv.remove('--gui')
    base_dir = os.path.dirname(os.path.abspath(__file__))
    wizard_path = os.path.join(base_dir, 'cli_wizard.py')
    subprocess.run([sys.executable, wizard_path])
    sys.exit(0)

if __name__ == '__main__':
    cli() 