# -*- coding: utf-8 -*-
from distutils.core import setup
from setuptools import find_packages

with open('README.rst') as readme:
    long_description = readme.read()

with open('requirements.txt') as reqs:
    install_requires = [
        line for line in reqs.read().split('\n') if (line and not
                                                     line.startswith('--'))
    ]

setup(
    name='python-gooclientlib',
    version='0.1.0',
    author='Beraldo Leal',
    author_email='beraldo@ncc.unesp.br',
    packages=find_packages(exclude=['test', 'bin']),
    url='http://goo.ncc.unesp.br/',
    license='LICENSE',
    description='Python 2.x bindings for Goo command line client and goo-dataproxy',
    install_requires=install_requires,
    scripts=[],
)
