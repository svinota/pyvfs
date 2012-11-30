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
import threading
import logging
import inspect
import traceback
from io import BytesIO

DEFAULT_DIR_MODE = 0o755
DEFAULT_FILE_MODE = 0o644


class Eperm(Exception):
    pass


class Eexist(Exception):
    def __init__(self, target=None):
        Exception.__init__(self, str(target))
        self.target = target


class Edebug(Exception):
    pass


def _restrict_debug(c):
    def wrapped(*argv, **kwarg):
        stack = inspect.stack()
        try:
            caller = stack[1][0].f_locals['self']
            line = stack[1][0].f_code.co_firstlineno
            assert isinstance(caller, Storage) or\
                    isinstance(caller, Inode)
        except AssertionError:
            logging.warning("Inode method %s called from: %s:%s" %\
                    (c, caller, line))
        except:
            logging.error("Got error while analyzing stack: %s" %\
                    (traceback.format_exc()))
        return c(*argv, **kwarg)
    return wrapped


def _restrict_bypass(c):
    return c


if os.environ.get("PYVFS_LOG", "False").lower() in (
        "yes", "true", "on", "t", "1"):
    restrict = _restrict_debug
else:
    restrict = _restrict_bypass


class Inode(BytesIO, object):
    """
    VFS inode
    """
    mode = 0
    cleanup = None
    # static member for special names
    special_names = [
            ".",
            "..",
            ]

    def __init__(self, name, parent=None, mode=0, storage=None, **kwarg):

        BytesIO.__init__(self)

        self.parent = parent or self
        self.storage = storage or parent.storage
        self.children = {}
        # if there is no transaction yet, create a blank one
        if not isinstance(self.cleanup, dict):
            self.cleanup = {}
        self.name = name
        self.type = 0
        self.dev = 0
        self.ctime = self.atime = self.mtime = int(time.time())
        self.uidnum = self.muidnum = os.getuid()
        self.gidnum = os.getgid()
        self.uid = self.muid = pwd.getpwuid(self.uidnum).pw_name
        self.gid = grp.getgrgid(self.gidnum).gr_name
        self.writelock = False
        if not self.mode:
            if mode & stat.S_IFDIR:
                self.mode = stat.S_IFDIR | DEFAULT_DIR_MODE
                self.children["."] = self
                self.children[".."] = self.parent
            elif mode == stat.S_IFLNK:
                self.mode = mode
            else:
                self.mode = stat.S_IFREG | DEFAULT_FILE_MODE
        # all is ok for this moment, so we can clean up
        # the transaction and create one exit hook

    def __hash__(self):
        return self.path

    def _update_register(self):
        if self.orphaned:
            return
        try:
            self._check_special(self.name)
            self.storage.unregister(self)
        except:
            pass
        self.path = int(abs(hash(self.absolute_path())))
        self.storage.register(self)
        self.cleanup["storage"] = (self.storage.destroy, (self,))
        for (i, k) in [x for x in list(self.children.items())
                if x[0] not in (".", "..")]:
            k._update_register()

    def _get_name(self):
        return self.__name

    def _set_name(self, name):
        self._check_special(name)
        try:
            if name in list(self.parent.children.keys()):
                raise Eexist(self.parent.children[name])
            del self.parent.children[self.name]
        except Eexist as e:
            raise e
        except:
            pass
        self.__name = name
        if (self.parent != self) and (self.parent != None):
            self.parent.children[name] = self
        try:
            self._update_register()
        except Exception as e:
            self.destroy()
            raise e

    name = property(_get_name, _set_name)

    def _check_special(self, *args):
        for i in args:
            if i in self.special_names:
                raise Eperm()

    @property
    def orphaned(self):
        if self.parent == self:
            return False
        if self.parent is None:
            return True
        return self.parent.orphaned

    @restrict
    def absolute_path(self, stop=None):
        if (self.parent is not None) and\
                (self.parent != self) and\
                (self != stop):
            return "%s/%s" % (self.parent.absolute_path(stop), self.name)
        else:
            return ""

    @restrict
    def commit(self):
        pass

    @restrict
    def sync(self):
        pass

    @restrict
    def open(self):
        pass

    @restrict
    def destroy(self):
        ret = {}
        for (i, k) in list(self.cleanup.items()):
            try:
                if len(k) < 3:
                    kwarg = {}
                else:
                    kwarg = k[2]
                if len(k) < 2:
                    argv = []
                else:
                    argv = k[1]
                ret[i] = k[0](*argv, **kwarg)
            except Exception as e:
                ret[i] = e
        logging.debug("destroy returned: %s" % (ret))
        return ret

    @restrict
    def add(self, inode):
        if inode.name in list(self.children.keys()):
            raise Eexist()
        self.children[inode.name] = inode
        inode.parent = self
        inode.storage = self.storage
        inode._update_register()

    @restrict
    def remove(self, inode):
        """
        Remove a child from a directory
        """
        self._check_special(inode.name)
        inode.parent = None
        del self.children[inode.name]

    @restrict
    def create(self, name, mode=0, klass=None, **kwarg):
        """
        Create a child in a directory
        """
        self._check_special(name)
        if klass is None:
            klass = type(self)
        self.children[name] = klass(name, self, mode=mode,
            storage=self.storage, **kwarg)
        return self.children[name]

    @restrict
    def rename(self, old_name, new_name):
        """
        Rename a child
        """
        # just a legacy interface
        logging.debug("deprecated call Inode.rename() used")
        self.children[old_name].name = new_name

    @property
    def length(self):
        if self.mode & stat.S_IFDIR:
            return len(list(self.children.keys()))
        else:
            return self.seek(0, 2)


class Storage(object):
    """
    High-level storage insterface. Implements a simple protocol
    for the file management and file lookup dictionary.

    Should be provided with root 'inode' class on init. The 'inode'
    class MUST support the interface... that should be defined :)
    """
    def __init__(self, inode=Inode, **kwarg):
        self.files = {}
        self.lock = threading.RLock()
        self.root = inode(name="/", mode=stat.S_IFDIR, storage=self,
                **kwarg)

    def register(self, inode):
        """
        Register a new inode in the dictionary
        """
        self.files[inode.path] = inode

    def unregister(self, inode):
        """
        Remove an inode from the dictionary
        """
        del self.files[inode.path]

    def create(self, name, parent, mode=0):
        """
        Create an inode
        """
        with self.lock:
            new = parent.create(name, mode)
            self.register(new)
        return new

    def checkout(self, target):
        return self.files[target]

    def reparent(self, new_parent, inode, new_name=None):
        with self.lock:
            lookup = new_name or inode.name
            if lookup in list(new_parent.children.keys()):
                raise Eexist()
            inode.parent.remove(inode)
            if new_name:
                inode.name = new_name
            new_parent.add(inode)

    def truncate(self, inode, size=0):
        with self.lock:
            inode.seek(size)
            inode.truncate()
            inode.commit()

    def open(self, inode):
        with self.lock:
            inode.sync()
            inode.open()

    def sync(self, inode):
        with self.lock:
            inode.sync()

    def commit(self, inode):
        with self.lock:
            if inode.writelock:
                inode.writelock = False
                inode.commit()

    def write(self, inode, data, offset=0):
        with self.lock:
            inode.writelock = True
            inode.seek(offset, os.SEEK_SET)
            inode.write(data)
        return len(data)

    def read(self, inode, size, offset=0):
        with self.lock:
            if offset == 0:
                inode.sync()
            inode.seek(offset, os.SEEK_SET)
            data = inode.read(size)
        return data

    def destroy(self, inode):
        with self.lock:
            for i, k in list(inode.children.items()):
                if i not in inode.special_names:
                    self.remove(k)
            inode.parent.remove(inode)
            self.unregister(inode)

    def remove(self, inode):
        with self.lock:
            inode.destroy()

    def chmod(self, inode, mode):
        inode.mode = ((inode.mode & 0o7777) ^ inode.mode) |\
                (mode & 0o7777)

    def chown(self, inode, uid, gid):
        if uid > -1:
            try:
                inode.uid = pwd.getpwuid(uid).pw_name
            except:
                inode.uid = ""
            inode.uidnum = uid
        if gid > -1:
            try:
                inode.gid = grp.getgrgid(gid).gr_name
            except:
                inode.gid = ""
            inode.gidnum = gid
