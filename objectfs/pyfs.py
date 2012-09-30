"""
The module should be used to create filesystem that
represents Python objects as directories and files.
This allows easy inspection of the objects in runtime
with any file management tool, e.g. bash.

By now the module uses 9p2000 filesystem and creates
it just after the import call. You can mount it with
`mount -t 9p -o port=10001 127.0.0.1 /mnt/debugfs` on
your Linux system, or you can use FUSE, or any 9p
client.

By default it listens on tcp 127.0.0.1:10001, but you
can change the behaviour with environment variables:

PYFS_PORT -- tcp port; UNIX sockets are not supported
    by now, but they are planned
PYFS_ADDRESS -- IPv4 address, use 0.0.0.0 to allow
    remote access
PYFS_DEBUG -- turn on stderr debug output of py9p
PYFS_LOG -- create /log inode
"""

import types
import stat
import sys
import os
import py9p
import weakref
import logging
from abc import ABCMeta
from objectfs.vfs import Storage, Inode
from objectfs.v9fs import v9fs
from objectfs.utils import logInode
from threading import Thread


class Eexist(Exception):
    pass


class Skip:
    __metaclass__ = ABCMeta
Skip.register(types.BuiltinFunctionType)
Skip.register(types.BuiltinMethodType)
Skip.register(types.MethodType)
Skip.register(types.ClassType)
Skip.register(types.FunctionType)
Skip.register(types.GeneratorType)
Skip.register(types.ModuleType)
Skip.register(types.UnboundMethodType)


class List:
    __metaclass__ = ABCMeta
List.register(list)
List.register(set)
List.register(tuple)
List.register(frozenset)


class File:
    __metaclass__ = ABCMeta
File.register(types.BooleanType)
File.register(types.FileType)
File.register(types.FloatType)
File.register(types.IntType)
File.register(types.LongType)
File.register(types.StringType)
File.register(types.UnicodeType)
File.register(types.NoneType)


def _getattr(obj, item):
    if isinstance(obj, List):
        return obj[int(item)]
    if isinstance(obj, types.DictType):
        return obj[item]
    return getattr(obj, item)


def _dir(obj):
    if isinstance(obj, List):
        return [str(x) for x in xrange(len(obj))]
    if isinstance(obj, types.DictType):
        return [x for x in obj.keys() if isinstance(x, types.StringType)]
    return [x for x in dir(obj) if not x.startswith("_")]


def _get_name(obj):
    text = obj.__repr__()
    if text.find("/") == -1:
        return text
    try:
        return "%s [0x%x]" % (obj.__class__.__name__, id(obj))
    except:
        return "0x%x" % (id(obj))


class vRepr(Inode):
    def sync(self):
        self.seek(0)
        self.truncate()
        if self.parent.observe is not None:
            self.write(self.parent.observe.__repr__())


class vInode(Inode):

    special_names = [
            ".",
            "..",
            ".repr",
            ]

    def __init__(self, *argv, **kwarg):
        Inode.__init__(self, *argv, **kwarg)
        if hasattr(self.parent, "stack"):
            self.stack = self.parent.stack
        else:
            self.stack = {}
        self.root = False
        # force self.observe, bypass property setter
        self.__observe = None
        # repr hack
        if self.mode & stat.S_IFDIR:
            self.children[".repr"] = vRepr(".repr", self)

    def _get_root_flag(self):
        return self.__root

    def _set_root_flag(self, value):
        if value:
            # terminate stacks on root vInodes
            self.stack = {}
        self.__root = value

    root = property(_get_root_flag, _set_root_flag)

    def _get_observe(self):
        if self.root:
            return self.__observe
        else:
            return _getattr(self.parent.observe, self.name)

    def _set_observe(self, obj):

        if isinstance(obj, File):
            return

        try:
            # we can not use callback here, 'cause it forces
            # weakref to generate different proxies for one
            # object and it breaks cycle reference detection
            #
            # this won't work: lambda x: self.storage.remove(self.path)
            wp = weakref.proxy(obj)
        except:
            wp = obj

        if id(wp) in self.stack.keys():
            self.storage.remove(self.path)
            raise Eexist()
        try:
            del self.stack[id(self.__observe)]
        except:
            pass
        self.stack[id(wp)] = True

        if not self.root:
            return

        try:
            if id(wp) == id(self.__observe):
                return
        except:
            pass

        self.__observe = wp

    observe = property(_get_observe, _set_observe)

    def register(self, obj):
        self.observe = obj

    def create(self, name, mode=0, obj=None, root=False):

        new = Inode.create(self, name, mode)
        new.root = root
        new.observe = obj

        return new

    def sync(self):
        if self.observe is None:
            for (i, k) in self.children.items():
                try:
                    if hasattr(k, "observe"):
                        _dir(k.observe)
                        if k.observe is not None:
                            if _get_name(k.observe) != i:
                                k.name = _get_name(k.observe)
                except Exception, e:
                    self.storage.remove(k.path)
            return

        if self.mode & stat.S_IFDIR:
            chs = set(self.children.keys())
            obs = set(_dir(self.observe))
            to_delete = chs - obs - set(self.special_names)
            to_create = obs - chs
            for i in to_delete:
                self.storage.remove(self.children[i].path)
            # consider for saving stack in the root object inode!
            for i in to_create:
                self.storage.create(_getattr(self.observe, i),
                        parent=self, name=i)
        else:
            self.seek(0)
            self.truncate()
            self.write(str(_getattr(self.parent.observe, self.name)))


class PyFS(Storage):

    def create(self, obj, parent=None, name=None, root=False):
        if not parent:
            parent = self.root

        if not name:
            try:
                # try to get the name, but the object can be
                # not ready for __repr__
                name = _get_name(obj)
            except:
                # if so, return temporary name, it will be
                # changed later automatically
                name = str(id(obj))

        if isinstance(obj, Skip):
            return

        if name.startswith("_"):
            return

        if isinstance(obj, File):
            new = parent.create(name)
        else:
            try:
                new = parent.create(name, mode=stat.S_IFDIR, obj=obj,
                        root=root)
                for item in _dir(obj):
                    self.create(_getattr(obj, item), new, item)
            except:
                return

        return new

# 8<-----------------------------------------------------------------------
#
# configure file server
_PyFS_ADDRESS = os.environ.get("PYFS_ADDRESS", "127.0.0.1")
_PyFS_PORT = int(os.environ.get("PYFS_PORT", "10001"))
_PyFS_DEBUG = os.environ.get("PYFS_DEBUG", "False").lower() in (
    "yes", "true", "t", "1")
_PyFS_LOG = os.environ.get("PYFS_LOG", "False").lower() in (
    "yes", "true", "t", "1")

# create FS
pyfs = PyFS(vInode)
pyfs.root.root = True

# start logging
if _PyFS_LOG:
    log = logInode("log", pyfs.root, maxlen=1024)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(stream=log)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s : %(levelname)s : %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.removeHandler(logger.handlers[0])
    logger.debug("PyFS started")

# start the server
srv = py9p.Server(listen=(_PyFS_ADDRESS, _PyFS_PORT),
    chatty=_PyFS_DEBUG, dotu=True)
srv.mount(v9fs(pyfs))
srv_thread = Thread(target=srv.serve)
srv_thread.setDaemon(True)
srv_thread.start()


def export(c):
    old_init = c.__init__

    def new_init(self, *argv, **kwarg):
        global pyfs
        old_init(self, *argv, **kwarg)
        pyfs.create(self, root=True)
    c.__init__ = new_init
    return c

# make the module safe for import
__all__ = [export]
