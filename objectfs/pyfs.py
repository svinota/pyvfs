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

class PyFS(Storage):

    def create(self, obj, parent=None, name=None, stack=None):
        if not parent:
            parent = self.root

        if not stack:
            stack = {}

        if obj in stack.keys():
            return

        if isinstance(obj, File):
            if not name:
                name = str(hash(obj))
            new = parent.create(name)
            new.write(str(obj))
        else:
            try:
                stack[obj] = True
                new = parent.create(repr(obj).strip("<>"), mode=stat.S_IFDIR)
                for item in dir(obj):
                    if item.startswith('_') or isinstance(getattr(obj, item), Skip):
                        continue
                    self.create(getattr(obj, item), new, item, stack)
            except:
                return

        return new

pyfs = PyFS()
srv = py9p.Server(listen=('127.0.0.1', 8000), chatty=False, dotu=True)
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


