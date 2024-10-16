import setuptools
from setuptools.command.install import install
from setuptools.command.develop import develop
from setuptools.command.egg_info import egg_info
import os

class CustomInstallCommand(install):
    def run(self):
        os.system('make gopy_build')
        print("Building SDK install")
        install.run(self)

class CustomDevelopCommand(develop):
    def run(self):
        os.system('make gopy_build')
        print("Building SDK develop")
        develop.run(self)

class CustomEggInfoCommand(egg_info):
    def run(self):
        os.system('make gopy_build')
        print("Building SDK egg info")
        egg_info.run(self)

setuptools.setup(
    cmdclass={
        'install': CustomInstallCommand,
        'develop': CustomDevelopCommand,
        'egg_info': CustomEggInfoCommand,
    },
)