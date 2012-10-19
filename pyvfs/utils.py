"""
pyvfs.utils -- utility classes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Utility classes for VFS
"""
import os
import logging
import threading
from collections import deque
from pyvfs.vfs import Inode

protocols = []

try:
    from py9p import py9p
    from pyvfs.v9fs import v9fs
    protocols.append("9p")
except:
    pass


try:
    import fuse
    from pyvfs.ffs import ffs
    protocols.append("fuse")
except:
    pass


class logInode(Inode):
    """
    Deque-based log file. Should be read-only on the
    filesystem. Can be used as a stream for Python
    ``logging.StreamHandler()`` objects. Stores ``maxlen``
    of records, addition of records above ``maxlen`` at the same
    time discards discards old records.
    """

    def __init__(self, name, parent, maxlen=30):
        Inode.__init__(self, name, parent)
        self.deque = deque(maxlen=maxlen)

    def sync(self):
        self.seek(0)
        self.truncate()
        for i in self.deque:
            Inode.write(self, i)

    def commit(self):
        self.deque.clear()

    def write(self, value):
        self.deque.append(value)

    def flush(self):
        pass


class indexInode(Inode):
    """
    An inode that lists full storage file index.
    Can be used for debugging purposes.
    """
    def sync(self):
        self.seek(0)
        self.truncate()
        self.write("# storage file index debug\n")
        self.write("%-20s : %-8s : %s\n\n" % (
            "hash8", "mode", "name"))
        for (i, k) in list(self.storage.files.items()):
            self.write("%-20s : %-8s : \"%s\"\n" % (
                i, oct(k.mode), k.absolute_path()))


class Server(threading.Thread):
    """
    The main interface to create and start a filesystem.

    The filesystem will be exported with the protocol
    you will choose. Supported protocols now are ``9p`` and
    ``fuse``. For ``9p`` you should have py9p installed,
    for ``fuse``, respectively, fuse-python binding. With
    ``9p`` you will be able to mount the FS with mount(8)
    or with any other 9p implementation::

        mount -t 9p -o ro,port=10001 127.0.0.1 /mnt/debugfs

    In the case of ``fuse`` protocol, the FS will be mounted
    immediately with the script startup. You can configure
    the behaviour with environment variables:

     * **PYVFS_PROTO** -- ``9p`` (default) or ``fuse``
     * **PYVFS_PORT** -- tcp port; UNIX sockets are not supported
       by now, but they are planned (9p only, default: 10001)
     * **PYVFS_ADDRESS** -- IPv4 address, use 0.0.0.0 to allow
       public access (9p only, default: 127.0.0.1)
     * **PYVFS_MOUNTPOINT** -- the mountpoint (fuse only, default: ./mnt)
     * **PYVFS_DEBUG** -- turn on stderr debug output of the FS protocol
     * **PYVFS_LOG** -- create /log inode

    .. warning::
        No authentication for 9p is used in this library yet.
        Do not expose the socket to the public access unless you
        completely understand what are you doing.

    The typical code should look like that::

        from pyvfs.vfs import Storage
        from pyvfs.utils import Server

        server = Server(Storage())
        server.start()

    To run server in the backgroung, use ``start()``, in the
    foreground -- ``run()`` method.
    """
    parser = {
            "proto": "9p",
            "address": "127.0.0.1",
            "port": 10001,
            "mountpoint": "./mnt",
            "debug": False,
            "log": False,
            }

    def __init__(self, fs):
        threading.Thread.__init__(self,
                name="PyVFS for ObjectFS at 0x%x" % (id(fs)))
        self.setDaemon(True)
        self.fs = fs
        for (i, k) in list(self.parser.items()):
            value = os.environ.get("PYVFS_%s" % (i.upper()), str(k))
            if isinstance(k, bool):
                value = value.lower() in (
                        "yes", "true", "on", "t", "1")
            elif not isinstance(k, str):
                value = type(k)(value)
            setattr(self, i, value)
        for i in list(self.protocols.keys()):
            if i not in protocols:
                del self.protocols[i]
        if self.proto not in list(self.protocols.keys()):
            raise Exception("Requested protocol <%s> is not available" %\
                    (self.proto))
        if self.log:
            indexInode("index", self.fs.root)
            log = logInode("log", self.fs.root, maxlen=1024)
            logger = logging.getLogger()
            logger.setLevel(logging.DEBUG)
            handler = logging.StreamHandler(log)
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                "%(asctime)s : %(levelname)s : %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            for i in range(len(logger.handlers) - 1):
                logger.removeHandler(logger.handlers[0])
            logger.debug("PyVFS started")

        self.run = self.protocols[self.proto](self)

    def mount_v9fs(self):
        srv = py9p.Server(listen=(self.address, self.port),
                chatty=self.debug, dotu=True)
        srv.mount(v9fs(self.fs))
        return srv.serve

    def mount_fuse(self):
        srv = ffs(storage=self.fs, version="%prog " + fuse.__version__,
                dash_s_do='undef')
        srv.fuse_args.setmod('foreground')
        if self.debug:
            srv.fuse_args.add('debug')
        srv.fuse_args.mountpoint = os.path.realpath(self.mountpoint)
        return srv.main

    protocols = {
            "9p": mount_v9fs,
            "fuse": mount_fuse,
            }
