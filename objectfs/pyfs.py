"""
Internal VFS protocol
"""

import types
import stat
import py9p
from abc import ABCMeta
from objectfs.vfs import Storage, Inode
from objectfs.v9fs import v9fs
from threading import Thread

class Eexist(Exception): pass

class Skip:
    __metaclass__ = ABCMeta
Skip.register(types.BuiltinFunctionType)
Skip.register(types.BuiltinMethodType)
Skip.register(types.MethodType)
Skip.register(types.ClassType)

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

def x_get(obj, item):
    if isinstance(obj, List):
        return obj[int(item)]
    if isinstance(obj, types.DictType):
        return obj[item]
    return getattr(obj, item)

def x_dir(obj):
    if isinstance(obj, List):
        return [ str(x) for x in xrange(len(obj)) ]
    if isinstance(obj, types.DictType):
        return [ x for x in obj.keys() if isinstance(x, types.StringType) ]
    return [ x for x in dir(obj) if not x.startswith("_") ]

class vInode(Inode):

    def __init__(self, *argv, **kwarg):
        Inode.__init__(self, *argv, **kwarg)
        if self != self.parent:
            if hasattr(self.parent, "stack"):
                self.stack = self.parent.stack
            else:
                self.stack = {}
        self.observe = None

    def _get_observe(self):
        return self.__observe

    def _set_observe(self, obj):
        try:
            if id(obj) == id(self.__observe):
                return
        except:
            pass

        if (self.mode & stat.S_IFDIR) and (obj is not None):
            if self.stack.has_key(id(obj)):
                self.storage.remove(self.path)
                raise Eexist()
            try:
                del self.stack[id(self.__observe)]
            except:
                pass
            self.stack[id(obj)] = True
        self.__observe = obj

    observe = property(_get_observe, _set_observe)

    def register(self, obj):
        self.observe = obj

    def sync(self):
        if not self.observe:
            return

        if self.mode & stat.S_IFDIR:
            chs = set(self.children.keys())
            obs = set(x_dir(self.observe))
            to_delete = chs - obs - set(self.special_names)
            to_create = obs - chs
            for i in to_delete:
                self.storage.remove(self.children[i].path)
            # consider for saving stack in the root object inode!
            for i in to_create:
                self.storage.create(x_get(self.observe, i),
                        parent=self, name=i)
            # sync observe objects of children
            for i in x_dir(self.observe):
                if self.children.has_key(i):
                    try:
                        self.children[i].observe = x_get(self.observe, i)
                    except:
                        pass
        else:
            self.seek(0)
            self.truncate()
            self.write(str(x_get(self.parent.observe, self.name)))

class PyFS(Storage):

    def create(self, obj, parent=None, name=None):
        if not parent:
            parent = self.root

        if not name:
            name = repr(obj)

        if isinstance(obj, Skip):
            return

        if name.startswith("_"):
            return

        if isinstance(obj, File):
            new = parent.create(name)
            new.register(obj)
        else:
            try:
                new = parent.create(name, mode=stat.S_IFDIR)
                new.register(obj)
                for item in x_dir(obj):
                    self.create(x_get(obj, item), new, item)
            except:
                return

        return new

# import rpdb2
# rpdb2.start_embedded_debugger("bala", fAllowRemote=True)

pyfs = PyFS(vInode)
srv = py9p.Server(listen=('0.0.0.0', 10001), chatty=False, dotu=True)
srv.mount(v9fs(pyfs))
srv_thread = Thread(target=srv.serve)
srv_thread.setDaemon(True)
srv_thread.start()

def export(c):
    old_init = c.__init__
    def new_init(self, *argv, **kwarg):
        global pyfs
        old_init(self, *argv, **kwarg)
        pyfs.create(self)
    c.__init__ = new_init
    return c


