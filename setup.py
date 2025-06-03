from setuptools import setup, find_packages

setup(
    name="ezIncrementalBackup",
    version="1.1.0",
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
    include_package_data=True,
    package_data={'': ['LICENSE', 'README.md']},
) 