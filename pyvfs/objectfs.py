"""
pyvfs.objectfs -- exporting Python objects as files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The module should be used to create filesystem that
represents Python objects as directories and files.
This allows easy inspection of the objects in runtime
with any file management tool, e.g. bash.

.. note::
    This module creates a server thread just after the import,
    without any explicit calls.

To disable objectfs autostart, use environment variable
``OBJECTFS_AUTOSTART=False``. In this case you can start it
later with ``pyvfs.objectfs.srv.start()``.
The started thread requires no attention and stops automatically
as the script exits. In the case of ``fuse`` protocol, it also
mounts the FS immediately with the startup. Later you should
umount it with ``fusermount -u`` command. It is **not** umount'ed
automatically (yet).

.. warning::
    If you use the system ``mount`` and the kernel implementation
    of 9pfs to mount your script, be very careful:
    the cases of kernel crash were reported. System kernel,
    I mean.

"""

import types
import stat
import os
import sys
import dis
import weakref
import logging
import traceback
import inspect
from abc import ABCMeta
from pyvfs.vfs import Storage, Inode, Eexist, Eperm
from pyvfs.utils import Server


Skip = ABCMeta("Skip", (object,), {})
Skip.register(types.BuiltinFunctionType)
Skip.register(types.BuiltinMethodType)
Skip.register(type)
Skip.register(types.GeneratorType)
Skip.register(types.ModuleType)


Func = ABCMeta("Func", (object,), {})
Func.register(types.FunctionType)
Func.register(types.UnboundMethodType)


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


def _setattr(obj, item, value):
    """
    Set attribute by name. If the parent is a list(), the
    name is the index in the list. If the parent is a dict(),
    the name is the key.
    """
    if isinstance(obj, list):
        obj[int(item)] = value
    elif isinstance(obj, dict):
        obj[item] = value
    else:
        setattr(obj, item, value)


def _getattr(obj, item):
    """
    Get attribute by name. The same as for _setattr()
    """
    if isinstance(obj, List):
        return obj[int(item)]
    elif isinstance(obj, dict):
        return obj[item]
    else:
        return getattr(obj, item)


def _dir(obj):
    """
    * For list(): return indices as strings
    * For dict(): return only string keys
    * For other objects: return public attributes
    """
    if isinstance(obj, List):
        return [str(x) for x in range(len(obj))]
    elif isinstance(obj, dict):
        return [x for x in list(obj.keys()) if isinstance(x, bytes)]
    else:
        return [x for x in dir(obj) if not x.startswith("_")]


def _get_name(obj):
    """
    Get automatic name for an object.
    """
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
            obj=None, root=None, blacklist=None, weakref=True,
            functions=False):

        # respect preset mode
        if not (mode | self.mode):
            self.mode = stat.S_IFDIR

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
        self.functions = functions
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
            try:
                return _getattr(self.parent.observe, self.name)
            except:
                return None

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

    def commit(self):
        """
        Write data back from the I/O buffer to the corresponding
        attribute. Please note, that the data will be written
        with the type the attribute had before. If the type can
        not be casted from the data, commit will silently fail
        and the attribute will be unchanged.
        """
        if (self.mode & stat.S_IFREG) and \
            self.name != ".repr":
            try:
                if isinstance(self.observe, bool):
                    _setattr(self.parent.observe, self.name,
                            self.getvalue().lower() in (
                            "yes", "true", "on", "t", "1"))
                else:
                    _setattr(self.parent.observe, self.name,
                        type(self.observe)(self.getvalue()))
            except Exception as e:
                logging.debug("[%s] commit() failed: %s" % (
                    self.path, str(e)))

    def sync(self):
        """
        Synchronize directory subtree with the object's state.

        * Remove directories of GC'ed objects
        * Add inodes for new object's attributes (dirs)
        * Remove inodes of not existing attributes (dirs)
        * Write data from an attribute to the I/O buffer (file)
        """
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
        else:
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
                        parent=self, name=i, functions=self.functions)


class vFunction(vInode):
    """
    The file that represents function as a disassembled code.
    The fisrt line in the file is the function signature.

    Read/only.
    """
    mode = stat.S_IFREG

    def sync(self):
        self.seek(0)
        self.truncate()
        # write function signature
        sig = []
        sig_i = inspect.getargspec(self.observe)
        # get start index for arguments with default values
        try:
            def_start = len(sig_i.args) - len(sig_i.defaults)
        except:
            def_start = len(sig_i.args)
        for i in range(len(sig_i.args)):
            if i >= def_start:
                # get argument with default value
                value = sig_i.defaults[i - def_start]
                if isinstance(value, bytes):
                    value = "\"%s\"" % (value)
                sig.append("%s=%s" % (sig_i.args[i], value))
            else:
                # get argument w/o default value
                sig.append("%s" % (sig_i.args[i]))
        # add positional arguments list (if exists)
        if sig_i.varargs:
            sig.append("*%s" % (sig_i.varargs))
        # add keyword arguments dict (if exists)
        if sig_i.keywords:
            sig.append("**%s" % (sig_i.keywords))
        # format the signature
        self.write("#  %s(%s)\n\n" % (self.name, ", ".join(sig)))
        # write function code
        stdout = sys.stdout
        stderr = sys.stderr
        try:
            sys.stdout = sys.stderr = self
            dis.dis(self.observe)
        except:
            traceback.print_exc()
        sys.stdout = stdout
        sys.stderr = stderr


class vLiteral(vInode):
    """
    The file for string, numbers etc. simple variables.

    Read/write.

    Please note, that the data type on write will be cast
    from the previous data type.
    """
    mode = stat.S_IFREG

    def sync(self):
        self.seek(0)
        self.truncate()
        try:
            self.write(str(self.observe))
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

        if isinstance(obj, Skip) or \
                (isinstance(obj, Func) and not kwarg.get("functions", False)):
            return

        if name.startswith("_"):
            return

        try:
            if isinstance(obj, Func) and kwarg.get("functions", False):
                new = vFunction(name, parent)
                parent.add(new)
            elif isinstance(obj, File):
                new = vLiteral(name, parent)
                parent.add(new)
            else:
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
# do not start FS automatically if OBJECTFS_AUTOSTART is set to False
if os.environ.get("OBJECTFS_AUTOSTART", "True").lower() in (
        "yes", "true", "on", "t", "1"):
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
        * **basedir** -- The base directory, where to put objects. If it
          doesn't exist, it will be created.
        * **blacklist** -- The list of paths from the **object tree root**,
          that should not be exported. For example, if your object has an
          attribute "bala" and you want to hide it, you should use
          ``"/bala"`` in your blacklist. The same is for children, if you
          want to hide the child "dala" of attribute "bala", you should
          use ``"/bala/dala"``.
        * **functions** -- Create files for functions and methods (default:
          False). When True, the files will contain disassembled function
          code.
        * **weakref** -- Use weak references to this object (default: True)
    """
    basedir = kwarg.get("basedir", "").split("/")
    blacklist = kwarg.get("blacklist", [])
    functions = kwarg.get("functions", False)
    weakref = kwarg.get("weakref", True)

    def wrap(c):
        old_init = c.__init__

        def new_init(self, *argv, **kwarg):
            global fs
            old_init(self, *argv, **kwarg)
            parent = fs.root
            for i in basedir:
                if i != "":
                    try:
                        parent = parent.children[i]
                    except:
                        parent = vInode(i, parent, mode=stat.S_IFDIR)
            fs.create(self, root=True, parent=parent,
                    blacklist=blacklist, functions=functions, weakref=weakref)
        c.__init__ = new_init
        return c

    if len(argv):
        return wrap(argv[0])
    else:
        return wrap

# make the module safe for import
__all__ = ["export", "srv"]
