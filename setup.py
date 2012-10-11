#!/usr/bin/env python

from distutils.core import setup

# bump version
setup(name='pyvfs',
    version='0.2.3',
    description='Python VFS library',
    author='Peter V. Saveliev',
    author_email='peet@redhat.com',
    url='http://peet.spb.ru/pyvfs/',
    license="GPLv3+",
    packages=[
        'pyvfs'
        ]
)
