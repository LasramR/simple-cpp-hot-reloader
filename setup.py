from setuptools import setup, find_packages

setup(
    name='schr',
    author="LasramR",
    description="a configurationless, stateless hot reloader for C and CPP projects",
    version='1.0.0',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=open('requirements.txt').read().splitlines(),
    entry_points={
        'console_scripts': [
            'schr=cli:main',
        ],
    },
)
