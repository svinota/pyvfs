"""
Internal VFS protocol
"""

import types
import stat
import py9p
import weakref
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
        if hasattr(self.parent, "stack"):
            self.stack = self.parent.stack
        else:
            self.stack = {}
        self.root = False
        # force self.observe, bypass property setter
        self.__observe = None

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
            return x_get(self.parent.observe, self.name)

    def _set_observe(self, obj):

        if isinstance(obj, File):
            return

        try:
            wp = weakref.proxy(obj) #, lambda x: self.storage.remove(self.path))
        except:
            wp = obj

        if self.stack.has_key(id(wp)):
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
            for (i,k) in self.children.items():
                try:
                    x_dir(k.observe)
                except:
                    self.storage.remove(k.path)
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
        else:
            self.seek(0)
            self.truncate()
            self.write(str(x_get(self.parent.observe, self.name)))

class PyFS(Storage):

    def create(self, obj, parent=None, name=None, root=False):
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
        else:
            try:
                new = parent.create(name, mode=stat.S_IFDIR, obj=obj,
                        root=root)
                for item in x_dir(obj):
                    self.create(x_get(obj, item), new, item)
            except:
                return

        return new

# import rpdb2
# rpdb2.start_embedded_debugger("bala", fAllowRemote=True)

pyfs = PyFS(vInode)
pyfs.root.root = True
srv = py9p.Server(listen=('0.0.0.0', 10001), chatty=True, dotu=True)
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


