from setuptools import setup, find_packages

from setuptools.command.install import install
from setuptools.command.develop import develop
from setuptools.command.egg_info import egg_info
from setuptools.command.build_ext import build_ext

import os


def check_dependencies():
    if os.system('which go >/dev/null 2>&1') != 0:
        raise RuntimeError("Go is not installed. Install it from https://golang.org/doc/install")
    if os.system('which gopy >/dev/null 2>&1') != 0:
        raise RuntimeError("gopy is not installed. Install it from https://github.com/go-python/gopy")
class CustomInstallCommand(install):
    def run(self):
        check_dependencies()
        if os.system('make gopy_build') != 0:
            raise RuntimeError("Failed to build gopy")
        print("Building SDK install")
        install.run(self)

class CustomDevelopCommand(develop):
    def run(self):
        check_dependencies()
        if os.system('make gopy_build') != 0:
            raise RuntimeError("Failed to build gopy")
        print("Building SDK develop")
        develop.run(self)

class CustomEggInfoCommand(egg_info):
    def run(self):
        check_dependencies()
        if os.system('make gopy_build') != 0:
            raise RuntimeError("Failed to build gopy")
        print("Building SDK egg_info")
        egg_info.run(self)
class CustomBuildExt(build_ext):
    def run(self):
        check_dependencies()
        print("Running gopy_build...")
        if os.system("make gopy_build") != 0:
            raise RuntimeError("gopy build failed")
        super().run()


setup(
    name="trufnetwork_sdk_py",
    version="0.1.0",
    description="A Python SDK for Truf Network",
    author="Your Name",
    author_email="you@example.com",
    url="https://github.com/trufnetwork/sdk-py",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    zip_safe=False,
    python_requires=">=3.12",
    cmdclass={
        'install': CustomInstallCommand,
        'develop': CustomDevelopCommand,
        'egg_info': CustomEggInfoCommand,
        'build_ext': CustomBuildExt,
    },
)