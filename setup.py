import setuptools
from setuptools.command.install import install
from setuptools.command.develop import develop
from setuptools.command.egg_info import egg_info
import os
import sys

# Check if we're installing from source
IS_SOURCE_INSTALL = os.path.exists('Makefile')  # or any other repo-specific file

def get_command_class(base_command, custom_command):
    if IS_SOURCE_INSTALL:
        return custom_command
    return base_command

def check_dependencies():
    # Check if Go is installed
    if os.system('which go >/dev/null 2>&1') != 0:
        raise RuntimeError(
            "golang is not installed. Please install Go first.\n"
            "Visit https://golang.org/doc/install for installation instructions."
        )
    
    # Check if gopy is installed
    if os.system('which gopy >/dev/null 2>&1') != 0:
        raise RuntimeError(
            "gopy is not installed. Please install it from:\n"
            "https://github.com/go-python/gopy#installation"
        )

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

setuptools.setup(
    cmdclass={
        'install': CustomInstallCommand,
        'develop': CustomDevelopCommand,
        'egg_info': CustomEggInfoCommand,
    },
)