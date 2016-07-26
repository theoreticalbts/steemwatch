from setuptools import setup

setup(
    name="steem_watch",
    version="0.0.1.dev1",
    packages=["steem_watch"],
    license="MIT",
    long_description=open("README.md").read(),
    entry_points={
        "console_scripts" :
        [
            "watch_steem = steem_watch.main:sys_main",
        ]
    },
    install_requires=[
        "tornado",
        ],
)
