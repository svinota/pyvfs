#!/usr/bin/env python

from distutils.core import setup

# bump version
setup(name='objectfs',
    version='0.1.1',
    description='Python VFS library',
    author='Peter V. Saveliev',
    author_email='peet@altlinux.org',
    url='http://peet.spb.ru/pyfs/',
    license="GPLv3",
    packages=[
        'objectfs'
        ]
)
