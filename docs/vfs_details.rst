.. _vfs_details:

PyVFS protocols setup
---------------------

Simple PyVFS example:

.. toctree::
    :maxdepth: 2

    vfs

You can just import VFS as is and start the server. It will create
a slow and resource-hungry analogue of tmpfs. By itself it has no
use, unless you want to share your memory-based FS via network. But
you can write your own file implemenations on the base of ``pyvfs.vfs``.
E.g., you can parse and utilize the file contents on ``write()``,
create simple data channels and FS-based RPC interfaces.

The behaviour of the script and how/where you can mount the FS, depends on
the FS protocol the script uses. By default, ``9p`` is used, but you can
change it with ``PYVFS_PROTO`` environment variable.

Protocol 9p
+++++++++++

Environment variables to use with 9p:

    * **PYVFS_PROTO** -- should be set to ``9p`` (it is the default)
    * **PYVFS_ADDRESS** -- IPv4 address to listen on (default: 127.0.0.1)
    * **PYVFS_PORT** -- TCP port (default: 10001)
    * **PYVFS_DEBUG** -- switch the debug output [True/False] (default: False)
    * **PYVFS_LOG** -- create /log file and logging handler (default: False)

Bash script sample::

    #!/bin/bash
    export PYVFS_PROTO=9p
    export PYVFS_ADDRESS=0.0.0.0  # allow public access
    export PYVFS_LOG=True
    ./my_script.py

To mount your running script, you can use simple mount call::

    $ sudo mount -t 9p -o port=10001 127.0.0.1 /mnt/pyvfs

Protocol FUSE
+++++++++++++

.. note::
    Python FUSE binding uses not Python threading, so, it can not
    be traced with debugger, e.g. rpdb2, in the same way as py9p.

Environment variables:

    * **PYVFS_PROTO** -- should be set to ``fuse``
    * **PYVFS_MOUNTPOINT** -- the mountpoint with r/w access (default: ./mnt)
    * **PYVFS_DEBUG** -- the same as for ``9p``
    * **PYVFS_LOG** -- the same as for ``9p``

Bash script sample::

    #!/bin/bash
    export PYVFS_PROTO=fuse
    export PYVFS_MOUNTPOINT=/home/erkki/mnt
    export PYVFS_LOG=True
    ./my_script.py
    fusermount -u $PYVFS_MOUNTPOINT

The FS will be mounted with your script startup. Do not forget to umount it
later with fusermount.

