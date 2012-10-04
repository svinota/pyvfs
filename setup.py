#!/usr/bin/env python

from distutils.core import setup

# bump version
setup(name='pyvfs',
    version='0.2.1',
    description='Python VFS library',
    author='Peter V. Saveliev',
    author_email='peet@altlinux.org',
    url='http://peet.spb.ru/pyvfs/',
    license="GPL",
    packages=[
        'pyvfs'
        ]
)
