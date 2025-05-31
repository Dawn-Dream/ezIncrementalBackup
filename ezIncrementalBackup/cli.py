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

CONFIG_PATH = 'config.yaml'
SNAPSHOT_PATH = 'snapshot/last_snapshot.json'

@click.group()
def cli():
    """ezIncrementalBackup 命令行工具

    额外参数:
      --gui    启动交互式向导界面
    """
    pass

@cli.command()
def init():
    """初始化配置文件"""
    if not Path(CONFIG_PATH).exists():
        with open(CONFIG_PATH, 'w') as f:
            f.write("""source_dir: /path/to/source\nbackup_type: incremental  # full or incremental\ncompress: true\nsplit_size_mb: 1024\ntarget:\n  type: local\n  path: /path/to/backup\n  url: https://webdav.example.com/backup\n  username: user\n  password: pass\nschedule: '0 2 * * *'\n""")
        click.echo("已生成默认配置文件 config.yaml")
    else:
        click.echo("config.yaml 已存在")

@cli.command()
@click.option('--type', type=click.Choice(['full', 'incremental']), default=None, help='备份类型')
@click.option('--compress/--no-compress', default=None, help='是否压缩')
@click.option('--split-size', type=int, default=None, help='分卷大小（MB）')
def backup(type, compress, split_size):
    """执行备份操作"""
    # 读取配置
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    source_dir = config['source_dir']
    backup_type = type or config.get('backup_type', 'incremental')
    compress_flag = compress if compress is not None else config.get('compress', True)
    split_size_mb = split_size or config.get('split_size_mb', 1024)
    target = config['target']
    target_dir = target.get('path', './backup_output')
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
                for file in files:
                    all_files.append(str(Path(root) / file))
            archive_path = Path(target_dir) / f'full_{now_str}.7z'
            parts = compress_files_with_split(all_files, archive_path, split_size_mb, base_dir=source_dir)
            click.echo(f'生成分卷: {parts}')
        else:
            click.echo('未启用压缩，直接复制源文件到目标目录...')
            full_backup(source_dir, target_dir)
            parts = [str(p) for p in Path(target_dir).glob('*') if p.is_file()]
        # 全量备份后生成快照
        snapshot = {}
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                src_file = Path(root) / file
                file_stat = src_file.stat()
                file_hash = file_md5(src_file)
                file_info = {
                    'mtime': file_stat.st_mtime,
                    'size': file_stat.st_size,
                    'md5': file_hash
                }
                snapshot[str(src_file)] = file_info
        with open(SNAPSHOT_PATH, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2)
        with open(snapshot_history_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2)
    else:
        click.echo('执行增量备份...')
        changed, deleted = incremental_backup(source_dir, SNAPSHOT_PATH)
        click.echo(f'本次增量备份变动文件数: {len(changed)}，删除文件数: {len(deleted)}')
        files_to_pack = changed.copy()
        deleted_list_arcname = None
        if deleted:
            deleted_list_arcname = f'deleted_{now_str}.txt'
            deleted_list_path = Path(source_dir) / deleted_list_arcname
            with open(deleted_list_path, 'w', encoding='utf-8') as f:
                for path in deleted:
                    f.write(path + '\n')
            files_to_pack.append(str(deleted_list_path))
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
    # 2. 选择还原目录
    if to_source:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        target_dir = Path(config['source_dir'])
        click.echo(f'自动还原到源目录: {target_dir}')
        # 自动清空源目录
        if target_dir.exists():
            for item in target_dir.iterdir():
                if item.is_file() or item.is_symlink():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            click.echo(f'已清空目录: {target_dir}')
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
    else:
        target_dir = Path(target_dir) if target_dir else Path('.')
    # 3. 找到全量包和所有相关增量包
    backup_dir = Path('test-bk') if Path('test-bk').exists() else Path('.')
    all_pkgs = sorted(backup_dir.glob('*.7z'))
    full_pkg = None
    incr_pkgs = []
    for pkg in all_pkgs:
        pkg_name = pkg.stem
        if pkg_name.startswith('full_'):
            if pkg_name[5:] <= ts:
                full_pkg = pkg
        elif pkg_name.startswith('incremental_'):
            if pkg_name[12:] <= ts:
                incr_pkgs.append(pkg)
    if not full_pkg:
        click.echo('未找到对应的全量包！')
        return
    incr_pkgs = sorted(incr_pkgs, key=lambda p: p.stem[12:])
    # 4. 依次解压
    click.echo(f'解压全量包: {full_pkg}')
    with py7zr.SevenZipFile(full_pkg, mode='r') as z:
        z.extractall(path=str(target_dir))
    for pkg in incr_pkgs:
        click.echo(f'解压增量包: {pkg}')
        with py7zr.SevenZipFile(pkg, mode='r') as z:
            z.extractall(path=str(target_dir))
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
    with open(deleted_list, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    files = []
    dirs = []
    for rel_path in lines:
        abs_path = source_dir.parent / rel_path if not str(source_dir) in rel_path else Path(rel_path)
        if abs_path.exists():
            if abs_path.is_file() or abs_path.is_symlink():
                files.append(abs_path)
            elif abs_path.is_dir():
                dirs.append(abs_path)
        else:
            click.echo(f'未找到: {abs_path}')
    # 先删文件
    for f in files:
        try:
            f.unlink()
            click.echo(f'已删除文件: {f}')
        except Exception as e:
            click.echo(f'删除失败: {f}，原因: {e}')
    # 再删目录，按路径长度从长到短
    dirs = sorted(dirs, key=lambda x: -len(str(x)))
    for d in dirs:
        try:
            shutil.rmtree(d)
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
    click.echo(f"正在清空源目录: {source_dir}")
    if source_dir.exists():
        for item in source_dir.iterdir():
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
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