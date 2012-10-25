.. PyVFS documentation master file, created by
   sphinx-quickstart on Mon Oct  1 17:45:10 2012.

Python Virtual FS module
========================

PyVFS introduction
------------------

PyVFS by itself is an abstraction layer that allows to build
FS-like storages. The storage then can be exported with one
of supported protocols. The storage is completely agnostic
of the underlying protocol and a developer can choose the one
that fits better in the requirements.

Two protocols are supported now, **fuse** and **9p**. Fuse
exports FS only to the local running system, has a reasonable
performance. The 9p protocol can be used to export the storage
with several transports: TCP/IP or UNIX socket. Right now
PyVFS does not support client authorization on 9p sockets.

.. toctree::
    :maxdepth: 2

    vfs
    vfs_details

ObjectFS
--------

Objectfs -- ``pyvfs.objectfs`` module -- is a library built
on top of PyVFS. Objectfs implements a storage and a decorator,
that can be used to export there any Python object or function.

It means, that you will get in the runtime a filesystem, with
which you can access your live objects.

The library is not specific for any particular project, and
can be used in any script. The integration is as simple as
it is possible. All you need is to import the library and
decorate functions and/or objects you want to export::

    # just import the module and the decorator
    from pyvfs.objectfs import export

    ...

    # then decorate objects you want to browse
    @export
    class MyObject(object):
        ...

    # or functions
    @export
    def MyFunction(arg1, arg2="default value", ...):
        ...

By default, the library uses weak references to objects, that
allows the Python garbage collector to work properly. All
objects, that are not referenced anymore (except from the FS)
will disappear from the FS as well.

ObjectFS topics:

.. toctree::
    :maxdepth: 2

    first_steps
    second_steps

How to set up the FS export and mount it, read :ref:`vfs_details`

Implementation and API
----------------------

.. toctree::
    :maxdepth: 2

    api

Links
=====

 * home: https://github.com/svinota/pyvfs
 * bugs: https://github.com/svinota/pyvfs/issues
 * docs: http://peet.spb.ru/pyvfs/
 * wiki: https://github.com/svinota/pyvfs/wiki
 * pypi: http://pypi.python.org/pypi/objectfs/
 * list: https://groups.google.com/forum/#!forum/pyvfs



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

