#! /usr/bin/env python

"""Setup file for yang package

See:
    https://packaging.python.org/en/latest/distributing.html
"""

import os
import re
import sys
import shlex
import unittest
import subprocess
from setuptools import setup, find_packages, Command
from setuptools.command.test import test

pkg_name = 'yang.connector'
pkg_path = '/'.join(pkg_name.split('.'))

class CleanCommand(Command):
    '''Custom clean command

    cleanup current directory:
        - removes build/
        - removes src/*.egg-info
        - removes *.pyc and __pycache__ recursively

    Example
    -------
        python setup.py clean

    '''

    user_options = []
    description = 'CISCO SHARED : Clean all build artifacts'

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        os.system('rm -vrf ./build ./dist ./src/*.egg-info')
        os.system('find . -type f -name "*.pyc" | xargs rm -vrf')
        os.system('find . -type d -name "__pycache__" | xargs rm -vrf')

class TestCommand(Command):
    user_options = []
    description = 'CISCO SHARED : Run unit tests against this package'

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        # where the tests are (relative to here)
        tests = os.path.join('src', pkg_path, 'tests')

        # call unittests
        sys.exit(unittest.main(
            module = None,
           argv = ['python -m unittest', 'discover', tests],
           failfast = True))

class BuildAndPreviewDocsCommand(Command):
    user_options = []
    description = 'CISCO SHARED : Build and privately distribute ' \
        'Sphinx documentation for this package'

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        user = os.environ['USER']
        sphinx_build_cmd = "sphinx-build -b html -c ../../docs " \
            "-d ./__build__/documentation/doctrees docs/ ./__build__/documentation/html"
        target_dir = "/users/{user}/WWW/cisco_shared/{pkg_name}".\
            format(user = user, pkg_name = pkg_path)
        mkdir_cmd = "mkdir -p {target_dir}".format(target_dir=target_dir)
        rsync_cmd = "rsync -rvc ./__build__/documentation/ {target_dir}".\
            format(target_dir=target_dir)
        try:
            ret_code = subprocess.call(shlex.split(mkdir_cmd))
            if not ret_code:
                ret_code = subprocess.call(shlex.split(sphinx_build_cmd))
                if not ret_code:
                    ret_code = subprocess.call(shlex.split(rsync_cmd))
                    #print("\nYou may preview the documentation at the following URL:")
                    #print("http://wwwin-home.cisco.com/~{user}/cisco_shared/{pkg_name}/html".\
                    #    format(user=user, pkg_name=pkg_path))
                    sys.exit(0)
            sys.exit(1)
        except Exception:
            sys.exit(1)


def read(*paths):
    '''read and return txt content of file'''
    with open(os.path.join(os.path.dirname(__file__), *paths)) as fp:
        return fp.read()


def find_version(*paths):
    '''reads a file and returns the defined __version__ value'''
    version_match = re.search(r"^__version__ ?= ?['\"]([^'\"]*)['\"]",
                              read(*paths), re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


# launch setup
setup(
    name = pkg_name,
    version = find_version('src', pkg_path, '__init__.py'),

    # descriptions
    description =  'YANG defined interface API protocol connector',
    long_description = 'Client capable of NETCONF and gNMI protocol',

    # the package's documentation page.
    url = 'https://github.com/CiscoTestAutomation/yang.git',

    # author details
    author = 'Jonathan Yang',
    author_email = 'yuekyang@cisco.com',
    maintainer_email =  'yang-python@cisco.com',

    # project licensing
    license = 'Apache 2.0',

    platforms =  ['Linux',],

    # see https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Telecommunications Industry',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Testing',
    ],

    # uses namespace package
    namespace_packages = ['yang'],

    # project keywords
    keywords = 'pyats cisco-shared',

    # project packages
    packages = find_packages(where = 'src'),

    # project directory
    package_dir = {
        '': 'src',
    },

    # additional package data files that goes into the package itself
    package_data = {'':['README.rst']},

    # Standalone scripts
    scripts = [
    ],

    # console entry point
    entry_points = {
    },

    # package dependencies
    install_requires =  [
        'paramiko >= 1.15.1',
        'lxml >= 3.3.0',
        'ncclient >= 0.6.6',
        'grpcio',
        'protobuf ~= 3.20;python_version>="3.7"',
        'protobuf < 3.20;python_version<"3.7"',
    ],

    # any additional groups of dependencies.
    # install using: $ pip install -e .[dev]
    extras_require = {
        'dev': ['coverage',
                'restview',
                'Sphinx',
                'sphinxcontrib-napoleon',
                'sphinx-rtd-theme'],
    },

    # any data files placed outside this package.
    # See: http://docs.python.org/3.4/distutils/setupscript.html
    # format:
    #   [('target', ['list', 'of', 'files'])]
    # where target is sys.prefix/<target>
    data_files = [],

    # custom commands for setup.py
    cmdclass = {
        'clean': CleanCommand,
        'test': TestCommand,
        'docs': BuildAndPreviewDocsCommand,
    },

    # non zip-safe (never tested it)
    zip_safe = False,
)
