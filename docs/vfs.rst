.. _vfs:

Simple in-memory FS
-------------------

You can just import VFS as is and start the server. It will create
a slow and resource-hungry analogue of tmpfs. By itself it has no
use, unless you want to share your memory-based FS via network. But
you can write your own file implemenations on the base of ``pyvfs.vfs``.
E.g., you can parse and utilize the file contents on ``write()``,
create simple data channels and FS-based RPC interfaces.


.. literalinclude:: ../examples/fs.py
    :linenos:
