.. PyVFS documentation master file, created by
   sphinx-quickstart on Mon Oct  1 17:45:10 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to PyVFS's documentation!
=================================

.. note::
    This is pre-alpha. We're also surprised, that it works, you know.

PyVFS howto
-----------

VFS
~~~

.. toctree::
    :maxdepth: 2

    vfs

You can just import VFS as is and start the server. It will create
a slow and resource-hungry analogue of tmpfs. By itself it has no
use, unless you want to share your memory-based FS via network. But
you can write your own file implemenations on the base of ``pyvfs.vfs``.
E.g., you can parse and utilize the file contents on ``write()``,
create simple data channels and FS-based RPC interfaces.

ObjectFS
~~~~~~~~

.. toctree::
    :maxdepth: 2

    first_steps
    second_steps

With ``pyvfs.objectfs`` you can *mount* your Python script (sic)
and browse exported objects as directories and files. The usage
is extremely simple::

    # just import module and decorator
    from pyvfs.objectfs import export

    ...

    # then decorate objects you want to browse
    @export
    class MyObject(object):
        ...

To mount your running script, you can use simple mount call::

    $ sudo mount -t 9p -o port=10001 127.0.0.1 /mnt/pyvfs

Implementation and API
----------------------

.. toctree::
    :maxdepth: 2

    api

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

