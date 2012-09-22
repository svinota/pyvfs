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

class Skip:
    __metaclass__ = ABCMeta
Skip.register(types.MethodType)
Skip.register(types.ClassType)

class File:
    __metaclass__ = ABCMeta
File.register(types.BooleanType)
File.register(types.FileType)
File.register(types.FloatType)
File.register(types.IntType)
File.register(types.LongType)
File.register(types.StringType)
File.register(types.UnicodeType)

class vInode(Inode):

    def register(self, obj):
        self.observe = obj

    def sync(self):
        if not hasattr(self, "observe"):
            return

        if self.mode & stat.S_IFDIR:
            chs = set(self.children.keys())
            obs = set(dir(self.observe))
            to_delete = chs - obs - set(self.special_names)
            to_create = obs - chs
            for i in to_delete:
                self.storage.remove(self.children[i].path)
            # consider for saving stack in the root object inode!
            for i in to_create:
                self.storage.create(getattr(self.observe, i),
                        parent=self, name=i)
            # sync observe objects of children
            for i in dir(self.observe):
                if self.children.has_key(i):
                    self.children[i].observe = getattr(self.observe, i)
        else:
            self.seek(0)
            self.truncate()
            self.write(str(getattr(self.parent.observe, self.name)))

class PyFS(Storage):

    def create(self, obj, parent=None, name=None, stack=None):
        if not parent:
            parent = self.root

        if not stack:
            stack = {}

        if not name:
            name = repr(obj)

        if obj in stack.keys():
            return

        if isinstance(obj, Skip):
            return

        if name.startswith("_"):
            return

        if isinstance(obj, File):
            new = parent.create(name)
            new.register(obj)
        else:
            try:
                stack[obj] = True
                new = parent.create(name, mode=stat.S_IFDIR)
                new.register(obj)
                for item in dir(obj):
                    self.create(getattr(obj, item), new, item, stack)
            except:
                return

        return new

# import rpdb2
# rpdb2.start_embedded_debugger("bala", fAllowRemote=True)

pyfs = PyFS(vInode)
srv = py9p.Server(listen=('127.0.0.1', 8000), chatty=True, dotu=True)
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


