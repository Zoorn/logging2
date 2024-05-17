from setuptools import setup, find_packages

setup(
    name='bub_logger',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'PyYAML',  # Für YAML-Unterstützung
    ],
    entry_points={
        'console_scripts': [
            'bub_logger=bub_logger:main',
        ],
    },
    package_data={
        '': ['*.json', '*.yaml'],
    },
    description='A flexible and extendable logging module',
    author='Robert Woelte',
    author_email='woelte@bub-group.com',
    url='https://gitea.bub-group.com/woelte/logging',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)