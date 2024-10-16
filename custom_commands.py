import os
from setuptools.command.install import install
from setuptools.command.develop import develop
from setuptools.command.egg_info import egg_info

class CustomInstallCommand(install):
    def run(self):
        os.system('make gopy_build')
        install.run(self)

class CustomDevelopCommand(develop):
    def run(self):
        os.system('make gopy_build')
        develop.run(self)

class CustomEggInfoCommand(egg_info):
    def run(self):
        os.system('make gopy_build')
        egg_info.run(self)