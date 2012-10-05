#!/usr/bin/env python

from pyvfs.vfs import Storage
from pyvfs.ffs import ffs
import fuse
import os

if __name__ == "__main__":
    _PYVFS_MOUNTPOINT = os.environ.get("PYVFS_MOUNTPOINT", "./mnt")
    storage = Storage()
    srv = ffs(storage=storage, version="%prog " + fuse.__version__,
            dash_s_do='setsingle')
    srv.fuse_args.setmod('foreground')
    srv.fuse_args.add('debug')
    srv.fuse_args.mountpoint = os.path.realpath(_PYVFS_MOUNTPOINT)
    srv.main()
