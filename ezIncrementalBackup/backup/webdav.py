from webdav3.client import Client
from pathlib import Path

def upload_to_webdav(files, webdav_config):
    """
    上传分卷文件到WebDAV。
    files: 文件路径列表
    webdav_config: dict, 包含url, username, password
    """
    options = {
        'webdav_hostname': webdav_config['url'],
        'webdav_login': webdav_config['username'],
        'webdav_password': webdav_config['password'],
        'disable_check': True
    }
    client = Client(options)
    for file_path in files:
        file_path = Path(file_path)
        remote_path = f"/{file_path.name}"
        with open(file_path, 'rb') as f:
            client.upload_to(remote_path, str(file_path)) 