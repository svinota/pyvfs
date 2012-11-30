#!/usr/bin/env python

from distutils.core import setup

setup(name='objectfs',
    version='0.2.8',
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
+++++++++++++++++++++++++

PyVFS is a simple pure Python VFS library. It consists of
several layers, allowing to use different low-level protocol
implementations. Now you can choose between 9p (9p2000.u)
and FUSE (you should have python-py9p or python-fuse
installed).

The library has several options to control access to the
filesystem, from FUSE restrictions to PKI client authentication
in 9p2000 protocol. You can mount your FS with TCP/IP or
UNIX sockets, or simply browse it with 9p clients without
mounting.

The simplest example. Environment variables::

    export PYVFS_PROTO=9p
    export PYVFS_ADDRESS=/tmp/socket

Your script::

    # import server
    from pyvfs.utils import Server
    # create it
    srv = Server()
    # start it in foreground
    srv.run()

Client side, 9p + UNIX socket::

    $ sudo mount -t 9p -o trans=unix /tmp/socket /mnt

ObjectFS
========

ObjectFS (``pyvfs.objectfs``) is a library that allows you
to export your Python objects on a dynamic filesystem.
ObjectFS integration is extremely simple and engages only
the decorator import and usage. The developer should not
care about almost any of fs-related issues. Objects of the
decorated classes will automatically appear as file trees
on a dynamic filesystem with read/write access.

Example. Environment variables::

    export PYVFS_PROTO=fuse
    export PYVFS_MOUNTPOINT=~/mnt

Your script::

    # simply import the library in your code
    from pyvfs.objectfs import export
    # decorate a class
    @export
    class MyClass(object):
        some code

Client side (already mounted!)::

    # ls -l ~/mnt

PyVFS
=====

Also you can write your own applications with PyVFS. E.g.,
one can utilize file I/O as an RPC interface, or use a
dynamic filesystem for runtime service configuration.

More details in the documentation and examples.

Links
=====

 * home: https://github.com/svinota/pyvfs
 * bugs: https://github.com/svinota/pyvfs/issues
 * docs: http://peet.spb.ru/pyvfs/
 * wiki: https://github.com/svinota/pyvfs/wiki
 * pypi: http://pypi.python.org/pypi/objectfs/
 * list: https://groups.google.com/forum/#!forum/pyvfs


Changes
=======

0.2.8 -- Paleoarchean
---------------------

 * directory listing fixes

0.2.7 -- Eoarchaean
-------------------

 * support authentication options
 * support setuid, setgid, sticky bits

0.2.6 -- Hadean
---------------

 * initial pypi release
'''
)
