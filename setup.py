from setuptools import setup, find_packages

setup(
    name="ezIncrementalBackup",
    version="0.1.2b",
    packages=find_packages(),
    install_requires=[
        'click',
        'py7zr',
        'webdavclient3',
        'PyYAML',
        'tqdm',
        'questionary'
    ],
    entry_points={
        'console_scripts': [
            'ezbackup=ezIncrementalBackup.cli:cli',
        ],
    },
    author="DawnDream",
    description="一个简单的增量备份工具",
    python_requires='>=3.7',
) 