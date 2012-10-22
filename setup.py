#!/usr/bin/env python

from distutils.core import setup

setup(name='objectfs',
    version='0.2.6',
    description='Simple Python VFS module',
    author='Peter V. Saveliev',
    author_email='peet@redhat.com',
    url='https://github.com/svinota/pyvfs',
    license='GPLv3+',
    packages=[
        'pyvfs'
        ],
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Operating System :: POSIX',
        'Intended Audience :: Developers',
        'Development Status :: 4 - Beta',
        ],
    long_description='''

Simple Python VFS library
-------------------------

PyVFS is a simple pure Python VFS library. It consists of
several layers, allowing to use different low-level protocol
implementations. Now you can choose between 9p (9p2000.u)
and FUSE (you should have python-py9p or python-fuse
installed)

ObjectFS
++++++++

ObjectFS (``pyvfs.objectfs``) is a library that allows you
to export your Python objects on a dynamic filesystem.
ObjectFS integration is extremely simple and engages only
the decorator import and usage. The developer should not
care about almost any of fs-related issues. Objects of the
decorated classes will automatically appear as file trees
on a dynamic filesystem with read/write access.

PyVFS
+++++

Also you can write your own applications with PyVFS. E.g.,
one can utilize file I/O as an RPC interface, or use a
dynamic filesystem for runtime service configuration.

More details in the documentation and examples.
'''
)
