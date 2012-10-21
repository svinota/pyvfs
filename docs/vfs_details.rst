.. _vfs_details:

PyVFS protocols setup
---------------------

How you can access your filesystem, depends on the environment
variables. To set them up, you can use shell, or directly
modify ``os.environ`` dictionary prior to starting the server.
It is done this way to simplify the integration with existing
complex projects, including system daemons written in Python.

There are several environment variables, that affect on the
library behaviour. The full list you can read in the API docs.
Most important are:

Protocol 9p
+++++++++++

Environment variables to use with 9p:

    * **PYVFS_PROTO** -- should be set to ``9p`` (it is the default)
    * **PYVFS_ADDRESS** -- IPv4 address to listen on (default: 127.0.0.1),
      or UNIX socket path, e.g. /tmp/my_vfs
    * **PYVFS_PORT** -- TCP port (default: 10001)
    * **PYVFS_DEBUG** -- switch the debug output [True/False]
      (default: False)
    * **PYVFS_LOG** -- create /log file and logging handler [True/False]
      (default: False)

Bash script sample::

    #!/bin/bash
    export PYVFS_PROTO=9p
    export PYVFS_ADDRESS=/tmp/my_vfs
    export PYVFS_LOG=True
    ./my_script.py

Protocol FUSE
+++++++++++++

.. note::
    Python FUSE binding uses not Python threading, so, it can not
    be traced with debugger, e.g. rpdb2, in the same way as py9p.

Environment variables:

    * **PYVFS_PROTO** -- should be set to ``fuse``
    * **PYVFS_MOUNTPOINT** -- the mountpoint with r/w access
      (default: ./mnt)
    * **PYVFS_DEBUG** -- the same as for ``9p``
    * **PYVFS_LOG** -- the same as for ``9p``

Bash script sample::

    #!/bin/bash
    export PYVFS_PROTO=fuse
    export PYVFS_MOUNTPOINT=/home/erkki/mnt
    export PYVFS_LOG=True
    ./my_script.py
    fusermount -u $PYVFS_MOUNTPOINT

Mount the FS
++++++++++++

In the case of ``fuse`` protocol usage, the FS will be mounted
already with the script start.

.. note::
    You should have write permissions to the mountpoint.
    Also, by default you should have exactly the same euid/egid
    pair to access mounted FUSE fs, as the server does.

In the case of ``9p`` protocol, you can mount your FS several times
or just browse it with command-line 9p-clients.

.. note::
    The library does not implement yet client authentication
    for the 9p-sockets. Use UNIX sockets or, at least, do not use
    "0.0.0.0" address unless you fully undestand what are you doing.

Examples with Linux kernel v9fs implementation::

    1. mount from UNIX-socket:
       $ sudo mount -t 9p -o trans=unix /tmp/my_vfs /mnt

    2. mount from an IP-address:
       $ sudo mount -t 9p -o port=10001 127.0.0.1 /mnt
 
.. note::
    There can be serious latency if you use 9p over low-speed
    connections. Moreover, if the TCP connection became broken, any
    FS operations like read/write/df etc. will stall.

Umount the FS
+++++++++++++

Do not forget to umount your filesystem after usage::

    1. in the case of FUSE:
       $ fusermount -u ~/mnt

    2. in the case of 9p:
       $ sudo umount /mnt
