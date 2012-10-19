#!/usr/bin/env python

from distutils.core import setup

# bump version
setup(name='pyvfs',
    version='0.2.5',
    description='Simple Python VFS module',
    author='Peter V. Saveliev',
    author_email='peet@redhat.com',
    url='https://github.com/svinota/pyvfs',
    license='GPLv3+',
    packages=[
        'pyvfs'
        ]
)
