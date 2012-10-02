"""
pyvfs.vfs -- abstract VFS layer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Internal VFS protocol. You can use this module to build your own
filesystems.
"""

import os
import stat
import time
import pwd
import grp
import logging
import threading
import types
from io import BytesIO

DEFAULT_DIR_MODE = 0o755
DEFAULT_FILE_MODE = 0o644


class Eperm(Exception):
    pass


class ThreadSafe(object):

    def __init__(self):
        object.__init__(self)
        self.lock = threading.RLock()

    def __getattribute__(self, attr):
        obj = object.__getattribute__(self, attr)

        def wrapped(*argv, **kwarg):
            self.lock.acquire()
            e = None
            try:
                ret = obj(*argv, **kwarg)
            except Exception as e:
                pass
            self.lock.release()
            if e:
                raise e
            return ret

        if isinstance(obj, types.MethodType):
            return wrapped
        else:
            return obj


class Inode(ThreadSafe, BytesIO):
    """
    VFS inode
    """
    # static member for special names
    special_names = [
            ".",
            "..",
            ]

    def __init__(self, name, parent=None, mode=0, storage=None):

        ThreadSafe.__init__(self)
        BytesIO.__init__(self)

        self.parent = parent or self
        self.storage = storage or parent.storage
        self.name = name
        self.type = 0
        self.dev = 0
        self.atime = self.mtime = int(time.time())
        self.uidnum = self.muidnum = os.getuid()
        self.gidnum = os.getgid()
        self.uid = self.muid = pwd.getpwuid(self.uidnum).pw_name
        self.gid = grp.getgrgid(self.gidnum).gr_name
        self.children = {}
        self.writelock = False
        if mode & stat.S_IFDIR:
            self.mode = stat.S_IFDIR | DEFAULT_DIR_MODE
            self.children["."] = self
            self.children[".."] = self.parent
        else:
            self.mode = DEFAULT_FILE_MODE
        logging.debug("created %s %o [%s]" % (self.absolute_path(),
            self.mode, self.path))

    def __hash__(self):
        return self.path

    def _get_name(self):
        return self.__name

    def _set_name(self, name):
        self._check_special(name)
        try:
            self.storage.unregister(self)
            del self.parent.children[self.name]
            logging.debug("rename %s -> %s" % (self.name, name))
        except:
            pass
        self.__name = name
        self.path = int(abs(hash(self.absolute_path())))
        self.storage.register(self)
        if self.parent != self:
            self.parent.children[name] = self

    name = property(_get_name, _set_name)

    def _check_special(self, *args):
        for i in args:
            if i in self.special_names:
                raise Eperm()

    def absolute_path(self, stop=None):
        if (self.parent is not None) and\
                (self.parent != self) and\
                (self != stop):
            return "%s/%s" % (self.parent.absolute_path(stop), self.name)
        else:
            return ""

    def commit(self):
        pass

    def sync(self):
        pass

    def remove(self, child):
        """
        Remove a child from a directory
        """
        self._check_special(child.name)
        logging.debug("remove child %s [%s]" % (child.name, child.path))
        del self.children[child.name]

    def create(self, name, mode=0, **kwarg):
        """
        Create a child in a directory
        """
        self._check_special(name)
        # return default Inode class
        self.children[name] = type(self)(name, self, mode=mode,
            storage=self.storage, **kwarg)
        return self.children[name]

    def rename(self, old_name, new_name):
        """
        Rename a child
        """
        # just a legacy interface
        self.children[old_name].name = new_name

    def wstat(self, stat):
        # change uid?
        if stat.uidnum != 0xFFFFFFFF:
            self.uid = pwd.getpwuid(stat.uidnum).pw_name
        else:
            if stat.uid:
                self.uid = stat.uid
        # change gid?
        if stat.gidnum != 0xFFFFFFFF:
            self.gid = grp.getgrgid(stat.gidnum).gr_name
        else:
            if stat.gid:
                self.gid = stat.gid
        # change mode?
        if stat.mode != 0xFFFFFFFF:
            self.mode = ((self.mode & 0o7777) ^ self.mode) |\
                    (stat.mode & 0o7777)
        # change name?
        if stat.name:
            self.parent.rename(self.name, stat.name)

    @property
    def length(self):
        if self.mode & stat.S_IFDIR:
            return len(list(self.children.keys()))
        else:
            return self.seek(0, 2)


class Storage(ThreadSafe):
    """
    High-level storage insterface. Implements a simple protocol
    for the file management and file lookup dictionary.

    Should be provided with root 'inode' class on init. The 'inode'
    class MUST support the interface... that should be defined :)
    """
    def __init__(self, inode=Inode, **kwarg):
        ThreadSafe.__init__(self)
        self.files = {}
        self.root = inode(name="/", mode=stat.S_IFDIR, storage=self,
                **kwarg)

    def register(self, inode):
        """
        Register a new inode in the dictionary
        """
        logging.debug("register %s [%s] [%i inodes in the storage]" % (
            inode.absolute_path(), inode.path, len(list(self.files.keys()))))
        self.files[inode.path] = inode

    def unregister(self, inode):
        """
        Remove an inode from the dictionary
        """
        logging.debug("unregister %s [%s] [%i inodes in the storage]" % (
            inode.absolute_path(), inode.path, len(list(self.files.keys()))))
        del self.files[inode.path]

    def create(self, name, parent, mode=0):
        """
        Create an inode
        """
        new = parent.create(name, mode)
        self.register(new)
        return new

    def checkout(self, target):
        return self.files[target]

    def commit(self, target):
        f = self.checkout(target)
        if f.writelock:
            f.writelock = False
            f.commit()

    def write(self, target, data, offset=0):
        f = self.checkout(target)
        f.writelock = True
        f.seek(offset, os.SEEK_SET)
        f.write(data)
        return len(data)

    def read(self, target, size, offset=0):
        f = self.checkout(target)
        if offset == 0:
            f.sync()
        f.seek(offset, os.SEEK_SET)
        return f.read(size)

    def remove(self, target):
        f = self.checkout(target)
        f.parent.remove(f)
        self.unregister(f)

    def wstat(self, target, stat):
        f = self.checkout(target)
        f.wstat(stat)
