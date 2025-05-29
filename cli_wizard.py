import questionary
from pathlib import Path
import yaml
import subprocess
import os

def main_menu():
    while True:
        choice = questionary.select(
            "请选择操作：",
            choices=[
                "配置管理",
                "快照还原",
                "包浏览",
                "删除清单应用",
                "全量备份",
                "增量备份",
                "清空源目录",
                "退出"
            ]
        ).ask()
        if choice == "配置管理":
            config_manage()
        elif choice == "快照还原":
            snapshot_restore()
        elif choice == "包浏览":
            package_browse()
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
            else:
                newval = questionary.text(f"{key} [{config[key]}]:").ask()
                if newval:
                    config[key] = newval
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True)
        print("已保存新配置！")

def snapshot_restore():
    snap_dir = Path("snapshot")
    snaps = sorted(snap_dir.glob("snapshot_*.json")) if snap_dir.exists() else []
    if not snaps:
        print("未找到快照文件！")
        return
    snap = questionary.select("请选择要还原的快照：", choices=[str(s.name) for s in snaps]).ask()
    if snap:
        print(f"正在还原快照: {snap} ...")
        subprocess.run(["python", "cli.py", "restore-all", f"snapshot/{snap}", "--to-source"], check=True)
        print("还原完成！")

def package_browse():
    target_dir = questionary.text("请输入备份包所在目录 (默认为 ./test-bk):", default="./test-bk").ask()
    pkg_dir = Path(target_dir)
    if not pkg_dir.exists():
        print(f"目录不存在: {pkg_dir}")
        return
    pkgs = sorted(pkg_dir.glob("*.7z"))
    if not pkgs:
        print("未找到备份包文件 (.7z)！")
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
                subprocess.run(["python", "cli.py", "restore", str(pkg_path), "--target-dir", restore_target_dir], check=True)
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
    dels = sorted(del_dir.glob("deleted_*.txt"))
    if not dels:
        print("未找到删除清单文件！")
        return
    dfile = questionary.select("请选择要应用的删除清单：", choices=[str(d.name) for d in dels]).ask()
    if dfile:
        print(f"正在应用删除清单: {dfile} ...")
        subprocess.run(["python", "cli.py", "apply-delete", dfile], check=True)
        print("删除操作完成！")

def backup(btype):
    print(f"正在执行{btype}备份...")
    subprocess.run(["python", "cli.py", "backup", "--type", btype, "--compress", "--split-size", "1024"], check=True)
    print("备份完成！")

def clean_source_wizard():
    if questionary.confirm("确认清空源目录吗？此操作不可逆！").ask():
        print("正在清空源目录...")
        try:
            subprocess.run(["python", "cli.py", "clean-source"], check=True)
            print("源目录已清空！")
        except subprocess.CalledProcessError as e:
            print(f"清空失败: {e}")

if __name__ == "__main__":
    main_menu() 