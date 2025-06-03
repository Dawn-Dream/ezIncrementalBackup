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
                
                "快照还原",
                "快照删除",
                "包浏览",
                #"删除清单应用",
                "全量备份",
                "增量备份",
                #"清空源目录",
                "配置管理",
                "退出"
            ]
        ).ask()
        if choice == "配置管理":
            config_manage()
        elif choice == "快照还原":
            snapshot_restore()
        elif choice == "快照删除":
            snapshot_delete_wizard()
        elif choice == "包浏览":
            package_browse()
        # elif choice == "删除清单应用":
        #     delete_apply()
        elif choice == "全量备份":
            backup("full")
        elif choice == "增量备份":
            backup("incremental")
        # elif choice == "清空源目录":
        #     clean_source_wizard()
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

def get_snapshot_dir():
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    target_dir = Path(config['target'].get('path', './backup_output'))
    snap_dir = target_dir / 'snapshot'
    snap_dir.mkdir(parents=True, exist_ok=True)
    return snap_dir

def snapshot_restore():
    snap_dir = get_snapshot_dir()
    snaps = sorted({s.name for s in snap_dir.glob("*.json")}) if snap_dir.exists() else []
    if not snaps:
        print("未找到快照文件！")
        return
    choices = snaps + ["返回主菜单"]
    snap = questionary.select("请选择要还原的快照：", choices=choices).ask()
    if snap == "返回主菜单":
        return
    if snap:
        print(f"正在还原快照: {snap} ...")
        subprocess.run([sys.executable, "-m", "ezIncrementalBackup.cli", "restore-all", str(get_snapshot_dir() / snap), "--to-source"], check=True)
        print("还原完成！")

def snapshot_delete_wizard():
    snap_dir = get_snapshot_dir()
    backup_dir = snap_dir.parent
    snaps = sorted({s.name for s in snap_dir.glob("*.json")}) if snap_dir.exists() else []
    if not snaps:
        print("未找到快照文件！")
        return
    choices = snaps + ["全部删除", "返回主菜单"]
    snap = questionary.select("请选择要删除的快照：", choices=choices).ask()
    if snap == "返回主菜单":
        return
    elif snap == "全部删除":
        # 显示所有将被删除的文件
        print("\n将删除以下快照和相关备份包:")
        for s in snap_dir.glob("*.json"):
            print(f"- 快照: {s.name}")
            ts = None
            m = re.match(r"snapshot(?:_full)?_(\d{8}_\d{6})\.json", s.name)
            if m:
                ts = m.group(1)
                if ts:
                    for pkg in backup_dir.glob(f"*_{ts}.7z*"):
                        print(f"  - 备份包: {pkg.name}")
        
        # 确认删除
        if not questionary.confirm("确认要删除以上所有文件吗?").ask():
            print("已取消删除操作")
            return
            
        print("正在删除所有快照和相关备份包...")
        # 删除所有快照
        for s in snap_dir.glob("*.json"):
            # 删除对应的包
            ts = None
            m = re.match(r"snapshot(?:_full)?_(\d{8}_\d{6})\.json", s.name)
            if m:
                ts = m.group(1)
            if ts:
                for pkg in backup_dir.glob(f"*_{ts}.7z*"):
                    pkg.unlink()
            s.unlink()
        print("所有快照及相关包已删除！")
    else:
        # 显示将被删除的文件
        print(f"\n将删除以下快照和相关备份包:")
        print(f"- 快照: {snap}")
        s = snap_dir / snap
        ts = None
        m = re.match(r"snapshot(?:_full)?_(\d{8}_\d{6})\.json", snap)
        if m:
            ts = m.group(1)
            if ts:
                for pkg in backup_dir.glob(f"*_{ts}.7z*"):
                    print(f"  - 备份包: {pkg.name}")
        
        # 确认删除
        if not questionary.confirm("确认要删除以上文件吗?").ask():
            print("已取消删除操作")
            return
            
        print(f"正在删除快照: {snap} ...")
        if ts:
            for pkg in backup_dir.glob(f"*_{ts}.7z*"):
                pkg.unlink()
        s.unlink()
        print("快照及相关包已删除！")

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
    cmd = [sys.executable, "-m", "ezIncrementalBackup.cli", "backup", "--type", btype]
    if workers:
        cmd += ["--workers", str(workers)]
    subprocess.run(cmd, check=True)
    print("备份完成！")

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

if __name__ == "__main__":
    main_menu() 