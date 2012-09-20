objectfs
========

Pre-alfa version of a simple userspace virtual file system implementation.

* vfs.py — VFS abstract layer, is not specific for any FS type
* v9fs.py — 9p2000-specific imlpementation of the FS server and inode
* bin/objectfs — a test executable script to launch a server

You should have objectfs module in the PYTHONPATH as well as the particular
FS stack that is used by VFS (right now only py9p is supported).

