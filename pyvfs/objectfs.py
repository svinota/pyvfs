"""
pyvfs.objectfs -- exporting Python objects as files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The module should be used to create filesystem that
represents Python objects as directories and files.
This allows easy inspection of the objects in runtime
with any file management tool, e.g. bash.

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

.. note::
    This module creates a server thread just after the import,
    without any explicit calls. The thread requires no attention
    and stop automatically as the script exits. No cleanup
    procedure is required.

    In the case of ``fuse`` protocol, it also mount the FS
    immediately with the startup. Later you should umount it
    with ``fusermount -u`` command. It is **not** umount'ed
    automatically.

.. warning::
    If you use the system ``mount`` and the kernel implementation
    of 9pfs to mount your script, be very careful:
    the cases of kernel crash were reported. System kernel,
    I mean.

.. note::
    Mount your script only in read-only mode, since read-write
    access is not tested yet and nobody knows what the hell
    can happen.

.. warning::
    No authentication for 9p is used in this library yet.
    Do not expose the socket to the public access unless you
    completely understand what are you doing.
"""

import types
import stat
import weakref
from abc import ABCMeta
from pyvfs.vfs import Storage, Inode, Eexist, Eperm
from pyvfs.utils import Server


Skip = ABCMeta("Skip", (object,), {})
Skip.register(types.BuiltinFunctionType)
Skip.register(types.BuiltinMethodType)
Skip.register(types.MethodType)
Skip.register(type)
Skip.register(types.FunctionType)
Skip.register(types.GeneratorType)
Skip.register(types.ModuleType)
Skip.register(types.UnboundMethodType)


List = ABCMeta("List", (object,), {})
List.register(list)
List.register(set)
List.register(tuple)
List.register(frozenset)


File = ABCMeta("File", (object,), {})
File.register(bool)
File.register(types.FileType)
File.register(float)
File.register(int)
File.register(int)
File.register(bytes)
File.register(str)
File.register(type(None))


def _getattr(obj, item):
    if isinstance(obj, List):
        return obj[int(item)]
    if isinstance(obj, dict):
        return obj[item]
    return getattr(obj, item)


def _dir(obj):
    if isinstance(obj, List):
        return [str(x) for x in range(len(obj))]
    if isinstance(obj, dict):
        return [x for x in list(obj.keys()) if isinstance(x, bytes)]
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
    """
    Sometimes ``__repr__()`` returns a string that can not be used
    as a filename. In this case, the object's inode will be named
    in some other way, but you can always retrieve the original
    representation from the special file ``.repr``, placed in every
    directory.

    As a side-effect, with ``.repr`` you can get text representations
    of Python lists, tuples and dicts just as you do in the Python
    command line.
    """

    def sync(self):
        self.seek(0)
        self.truncate()
        try:
            if self.parent.observe is not None:
                self.write(bytes(self.parent.observe.__repr__()))
        except:
            pass


class vInode(Inode):
    """
    An inode, that can represent and track a Python object.
    The tracked object is referenced by vInode.observe property,
    which is weakref.proxy, if possible.

    Only root object of the tree is tracked, all the children
    are resolved in runtime. It is slower, but it allows to
    avoid unnecessary object references, thus allowing GC to
    work normally. All GC'ed objects automatically disappear
    from the filesystem.
    """

    auto_names = [
            ".repr",
            ]

    def __init__(self, name, parent=None, mode=0, storage=None,
            obj=None, root=None, blacklist=None, weakref=True):
        Inode.__init__(self, name, parent, mode, storage)
        if hasattr(self.parent, "stack"):
            self.stack = self.parent.stack
        else:
            self.stack = {}
        self.root = root
        self.blacklist = None
        self.blacklist = blacklist or self.parent.blacklist
        if isinstance(self.blacklist, List):
            if self.absolute_path(stop=self.get_root()) in self.blacklist:
                self.storage.remove(self.path)
                raise Eperm()
        # force self.observe, bypass property setter
        self.use_weakrefs = weakref
        self.__observe = None
        self.observe = obj
        # repr hack
        if self.mode & stat.S_IFDIR:
            self.children[".repr"] = vRepr(".repr", self)

    def get_root(self):
        if self.root:
            return self
        else:
            return self.parent.get_root()

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

        if id(wp) in list(self.stack.keys()):
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

    def sync(self):
        if self.observe is None:
            for (i, k) in list(self.children.items()):
                try:
                    if hasattr(k, "observe"):
                        _dir(k.observe)
                        if k.observe is not None:
                            if _get_name(k.observe) != i:
                                k.name = _get_name(k.observe)
                except:
                    self.storage.remove(k.path)
            return

        if self.mode & stat.S_IFDIR:
            chs = set(self.children.keys())
            try:
                obs = set(_dir(self.observe))
            except:
                obs = set()
            to_delete = chs - obs -\
                    set(self.special_names) -\
                    set(self.auto_names)
            to_create = obs - chs
            for i in to_delete:
                self.storage.remove(self.children[i].path)
            for i in to_create:
                self.storage.create(_getattr(self.observe, i),
                        parent=self, name=i)
        else:
            self.seek(0)
            self.truncate()
            try:
                self.write(str(_getattr(self.parent.observe, self.name)))
            except:
                pass


class ObjectFS(Storage):
    """
    ObjectFS storage class. Though there is no limit of
    ObjectFS instances, the module starts only one storage.
    """

    def create(self, obj, parent=None, name=None, **kwarg):
        """
        Create an object inode and all the subtree. If ``parent``
        is not defined, attach new inode to the storage root.

        Objects of type ``File`` (see ABC ``File`` above in the code)
        will be represented as files. Private attributes,
        methods and other objects of ABC ``Skip`` will be silently
        skipped. All other attributes will be represented as
        directories, unless the inode creation fails 'cause of
        some reason.

        If ``name`` parameter is not defined, or the object is
        a member of an object of a complex builtin type like
        list or set, the object will be named automatically. Please
        note that you can affect the autonaming with ``__repr__()``
        method.
        """
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
            try:
                new = parent.create(name)
            except:
                return
        else:
            try:
                new = parent.create(name, mode=stat.S_IFDIR, obj=obj,
                        **kwarg)
                for item in _dir(obj):
                    self.create(_getattr(obj, item), new, item)
            except:
                return

        return new

# 8<-----------------------------------------------------------------------
#
# create FS
fs = ObjectFS(vInode, root=True)
srv = Server(fs)
srv.start()


def export(*argv, **kwarg):
    """
    The decorator, that is used to export objects to the filesystem.
    It can be used in two ways. The first, simplest, way allows you just
    to catch the object creation and export the whole object tree
    as is::

        @export
        class Example(object):

            ...

    Or you can provide named parameters::

        @export(blacklist=["/bala","/dala"])
        class Example(object):
            # these two parameters will not be exported:
            bala = None
            dala = None
            # but this one will be:
            vala = None

            ...

    Right now supported parameters are:
        * **blacklist** -- The list of paths from the **object tree root**,
          that should not be exported. For example, if your object has an
          attribute "bala" and you want to hide it, you should use
          ``"/bala"`` in your blacklist. The same is for children, if you
          want to hide the child "dala" of attribute "bala", you should
          use ``"/bala/dala"``.
        * **wekref** -- Use weak references to this object (default: True)
        * **basedir** -- Not implemented yet.
    """
    blacklist = kwarg.get("blacklist", [])
    weakref = kwarg.get("weakref", True)

    def wrap(c):
        old_init = c.__init__

        def new_init(self, *argv, **kwarg):
            global fs
            old_init(self, *argv, **kwarg)
            fs.create(self, root=True,
                    blacklist=blacklist, weakref=weakref)
        c.__init__ = new_init
        return c

    if len(argv):
        return wrap(argv[0])
    else:
        return wrap

# make the module safe for import
__all__ = ["export"]
