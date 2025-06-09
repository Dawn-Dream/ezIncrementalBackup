import questionary
from pathlib import Path
import yaml
import subprocess
import os
import sys
import re

def main_menu():
    while True:
        choice = questionary.select(
            "请选择操作：",
            choices=[
                "全量备份",
                "增量备份",
                "快照包浏览",
                "快照还原",
                "快照包删除",
                # "删除清单应用",
                # "清空源目录",
                "配置管理",
                "退出"
            ]
        ).ask()
        if choice == "配置管理":
            config_manage()
        elif choice == "快照还原":
            snapshot_restore()
        elif choice == "快照包浏览":
            package_browse()
        elif choice == "快照包删除":
            snapshot_delete()
        elif choice == "删除清单应用":
            delete_apply()
        elif choice == "全量备份":
            backup("full")
        elif choice == "增量备份":
            backup("incremental")
        elif choice == "清空源目录":
            clean_source_wizard()
        elif choice == "退出":
            break

def config_manage():
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("未找到 config.yaml，先用 cli.py init 初始化！")
        return
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    print("当前配置：")
    print(yaml.dump(config, allow_unicode=True))
    if questionary.confirm("是否编辑配置？").ask():
        for key in config:
            if isinstance(config[key], dict):
                for subkey in config[key]:
                    newval = questionary.text(f"{key}.{subkey} [{config[key][subkey]}]:").ask()
                    if newval:
                        config[key][subkey] = newval
            elif isinstance(config[key], list):
                print(f"当前 {key}: {config[key]}")
                if questionary.confirm(f"编辑 {key} 列表吗？").ask():
                    new_list = []
                    while True:
                        item = questionary.text(f"添加到 {key}（留空结束）:").ask()
                        if not item:
                            break
                        new_list.append(item)
                    if new_list:
                        config[key] = new_list
            else:
                newval = questionary.text(f"{key} [{config[key]}]:").ask()
                if newval:
                    config[key] = newval
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True)
        print("已保存新配置！")

def snapshot_restore():
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("未找到 config.yaml，先用 cli.py init 初始化！")
        return
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    snap_dir = Path(config.get('target', {}).get('path', './test-bk')) / 'snapshot'
    snaps = sorted(snap_dir.glob("*.json")) if snap_dir.exists() else []
    if not snaps:
        print("未找到快照文件！")
        return
    snap = questionary.select("请选择要还原的快照：", choices=[str(s.name) for s in snaps]).ask()
    if snap:
        print(f"正在还原快照: {snap} ...")
        snap_path = str((snap_dir / snap).resolve())
        subprocess.run([sys.executable, "-m", "ezIncrementalBackup.cli", "restore-all", snap_path, "--to-source"], check=True)
        print("还原完成！")

def package_browse():
    # 自动读取配置文件里的 target.path
    config_path = Path("config.yaml")
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        default_dir = config.get('target', {}).get('path', './test-bk')
    else:
        default_dir = './test-bk'
    target_dir = questionary.text(f"请输入备份包所在目录 (默认为 {default_dir}):", default=default_dir).ask()
    pkg_dir = Path(target_dir)
    if not pkg_dir.exists():
        print(f"目录不存在: {pkg_dir}")
        return
    # 同时查找 .7z 和 .7z.001 文件
    pkgs = sorted(list(pkg_dir.glob("*.7z")) + list(pkg_dir.glob("*.7z.001")))
    if not pkgs:
        print("未找到备份包文件 (.7z 或 .7z.001)！")
        return
    pkg_names = [str(p.name) for p in pkgs]
    choice = questionary.select("请选择要操作的备份包：", choices=pkg_names + ["返回主菜单"]).ask()
    if choice == "返回主菜单":
        return
    pkg_path = pkg_dir / choice
    action = questionary.select("请选择操作：", choices=["还原到指定目录", "查看包内容", "返回"]).ask()
    if action == "还原到指定目录":
        restore_target_dir = questionary.text("请输入还原目标目录:").ask()
        if restore_target_dir:
            print(f"正在还原包: {pkg_path} 到 {restore_target_dir} ...")
            try:
                print("如为分卷包，请确保所有分卷都在同一目录，仅需选择 .7z.001 文件即可！")
                subprocess.run([sys.executable, "-m", "ezIncrementalBackup.cli", "restore", str(pkg_path), "--target-dir", restore_target_dir], check=True)
                print("还原完成！")
            except subprocess.CalledProcessError as e:
                print(f"还原失败: {e}")
    elif action == "查看包内容":
        print(f"正在查看包内容: {pkg_path}")
        try:
            import py7zr
            with py7zr.SevenZipFile(str(pkg_path), mode='r') as z:
                print("\n包内容：")
                for name in z.getnames():
                    print(name)
                print("")
        except FileNotFoundError:
            print(f"文件未找到: {pkg_path}")
        except Exception as e:
            print(f"读取包内容失败: {e}")
        questionary.text("按回车键返回...", default="").ask()
    elif action == "返回":
        package_browse() # 返回当前页面

def delete_apply():
    del_dir = Path(".")
    # 递归查找所有 deleted_*.txt
    dels = sorted(del_dir.rglob("deleted_*.txt"))
    if not dels:
        print("未找到删除清单文件！")
        return
    dfile = questionary.select("请选择要应用的删除清单：", choices=[str(d) for d in dels]).ask()
    if dfile:
        print(f"正在应用删除清单: {dfile} ...")
        subprocess.run([sys.executable, "-m", "ezIncrementalBackup.cli", "apply-delete", dfile], check=True)
        print("删除操作完成！")

def backup(btype):
    print(f"正在执行{btype}备份...")
    # 读取 config.yaml，提示并支持 workers
    config_path = Path("config.yaml")
    workers = None
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        workers = config.get('workers', None)
    # 交互式询问是否自定义进程数
    if questionary.confirm("是否自定义并发进程数（多核加速）？").ask():
        workers_input = questionary.text(f"请输入进程数（留空=自动，当前配置={workers}）:").ask()
        if workers_input:
            workers = workers_input
        else:
            workers = int(os.cpu_count() * 0.75) % 100
            print(f"自动设置进程数为: {workers} (75%的cpu核心数)")
    # 交互式询问是否开始备份
    if not questionary.confirm("是否开始备份？").ask():
        return False
    cmd = [sys.executable, "-m", "ezIncrementalBackup.cli", "backup", "--type", btype]
    if workers:
        cmd += ["--workers", str(workers)]
    subprocess.run(cmd, check=True)
    print("备份完成！")
    return True

def is_excluded(item, source_dir, exclude_dirs):
    rel_path = os.path.relpath(item, source_dir).replace("\\", "/")
    return any(rel_path == ex or rel_path.startswith(ex + "/") for ex in exclude_dirs)

def clean_source_wizard():
    if questionary.confirm("确认清空源目录吗？此操作不可逆！").ask():
        print("正在清空源目录...")
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        source_dir = Path(config['source_dir'])
        exclude_dirs = set(config.get('exclude_dirs', []))
        if source_dir.exists():
            for item in source_dir.iterdir():
                if is_excluded(item, source_dir, exclude_dirs):
                    print(f"跳过保护目录: {item}")
                    continue
                if item.is_file() or item.is_symlink():
                    item.unlink()
                elif item.is_dir():
                    import shutil
                    shutil.rmtree(item)
            print("源目录已清空！")
        else:
            print(f"源目录不存在: {source_dir}，无需清空")

def snapshot_delete():
    # 读取 config.yaml 获取快照目录
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("未找到 config.yaml，先用 cli.py init 初始化！")
        return
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    target_dir = Path(config.get('target', {}).get('path', './test-bk'))
    snap_dir = target_dir / 'snapshot'
    
    snaps = []
    if snap_dir.exists():
        snaps = sorted(list(snap_dir.glob("snapshot_*.json")) + list(snap_dir.glob("full_snapshot_*.json")))
    if not snaps:
        print("未找到快照文件！")
        return
    snap = questionary.select("请选择要删除的快照：", choices=[str(s.name) for s in snaps]).ask()
    if not snap:
        return
    snap_path = snap_dir / snap
    # 解析快照时间戳 (支持 snapshot_ 和 full_snapshot_ 两种前缀)
    m = re.match(r'(?:snapshot_|full_snapshot_)(\d{8}_\d{6})', snap)
    if not m:
        print("快照文件名格式不正确！")
        return
    ts = m.group(1) # 提取时间戳
    # 确认
    if not questionary.confirm(f"确定要删除快照 {snap} 及相关备份包吗？").ask():
        return
    # 删除快照文件
    try:
        snap_path.unlink()
        print(f"已删除快照文件: {snap_path}")
    except Exception as e:
        print(f"删除快照文件失败: {e}")
    # 删除全量包快照文件
    full_snap_name = f"full_snapshot_{ts}.json"
    full_snap_path = snap_dir / full_snap_name
    if full_snap_path.exists():
        try:
            # 再次确认是否删除            
            if questionary.confirm(f"确定要删除全量包快照文件: {full_snap_path}？").ask():
                full_snap_path.unlink()
                print(f"已删除全量包快照文件: {full_snap_path}")
        except Exception as e:
            print(f"删除全量包快照文件失败: {e}")
    # 删除全量包和增量包
    pkgs = sorted(list(target_dir.glob("*.7z")) + list(target_dir.glob("*.7z.001")))
    # 构建基名到包的映射，优先 .7z.001
    pkg_map = {}
    for pkg in pkgs:
        m = re.match(r'(full_\d{8}_\d{6}|incremental_\d{8}_\d{6})\.7z(\.\d{3})?$', pkg.name)
        if m:
            base = m.group(1)
            # 优先 .7z.001
            if base not in pkg_map or str(pkg).endswith('.7z.001'):
                pkg_map[base] = pkg
    # 删除对应全量包（时间戳等于快照）
    full_base = f"full_{ts}"
    full_pkg = pkg_map.get(full_base)
    if full_pkg:
        # 删除分卷
        for part in target_dir.glob(f"{full_base}.7z*"):
            try:
                part.unlink()
                print(f"已删除全量包: {part}")
            except Exception as e:
                print(f"删除全量包失败: {e}")
    # 删除所有小于等于快照的增量包
    for base, pkg in pkg_map.items():
        if base.startswith('incremental_'):
            incr_ts = base[12:]
            if incr_ts <= ts:
                for part in target_dir.glob(f"{base}.7z*"):
                    try:
                        part.unlink()
                        print(f"已删除增量包: {part}")
                    except Exception as e:
                        print(f"删除增量包失败: {e}")
    print("删除操作完成！")
    
    # 自动回退到上一个快照或全量快照
    prev_snap = None
    prev_full = None
    # 查找所有剩余快照
    all_snaps = sorted([s for s in snap_dir.glob("snapshot_*.json")])
    for s in all_snaps:
        m2 = re.match(r'(?:snapshot_|full_snapshot_)(\d{8}_\d{6})', s.name)
        if m2 and m2.group(1) < ts:
            prev_snap = s
    if prev_snap:
        print(f"自动回退到上一个快照: {prev_snap.name}")
        subprocess.run([sys.executable, "-m", "ezIncrementalBackup.cli", "restore-snapshot", str(snap_dir / prev_snap.name)], check=True)
        return
    # 没有上一个快照，查找全量快照
    all_full = sorted([s for s in snap_dir.glob("full_snapshot_*.json")])
    for s in all_full:
        m2 = re.match(r'(?:snapshot_|full_snapshot_)(\d{8}_\d{6})', s.name)
        if m2 and m2.group(1) < ts:
            prev_full = s
    if prev_full:
        print(f"自动回退到上一个全量快照: {prev_full.name}")
        subprocess.run([sys.executable, "-m", "ezIncrementalBackup.cli", "restore-snapshot", str(snap_dir / prev_full.name)], check=True)
        return
    print("没有可用快照可恢复！")
    # 询问是否删除 last_snapshot.json
    if questionary.confirm("是否删除 last_snapshot.json？").ask():
        last_snap_path = snap_dir / 'last_snapshot.json'
        if last_snap_path.exists():
            try:
                last_snap_path.unlink()
                print(f"已删除 last_snapshot.json: {last_snap_path}")
            except Exception as e:
                print(f"删除 last_snapshot.json 失败: {e}")

if __name__ == "__main__":
    main_menu() 