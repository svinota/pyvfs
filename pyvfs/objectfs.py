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
import ast
import dis
import weakref
import logging
import traceback
import inspect
import uuid
from abc import ABCMeta
from pyvfs.vfs import Storage, Inode, Eexist, Eperm, restrict
from pyvfs.utils import Server
if sys.version_info[0] > 2:
    from configparser import ConfigParser
else:
    from ConfigParser import SafeConfigParser as ConfigParser


Skip = ABCMeta("Skip", (object,), {})
Skip.register(types.BuiltinFunctionType)
Skip.register(types.BuiltinMethodType)
Skip.register(type)
Skip.register(types.GeneratorType)
Skip.register(types.ModuleType)


Cls = ABCMeta("Cls", (object,), {})
Cls.register(type)
if sys.version_info[0] == 2:
    Cls.register(types.ClassType)


Func = ABCMeta("Func", (object,), {})
Func.register(types.FunctionType)
if sys.version_info[0] == 2:
    Func.register(types.UnboundMethodType)


List = ABCMeta("List", (object,), {})
List.register(list)
List.register(set)
List.register(tuple)
List.register(frozenset)


String = ABCMeta("String", (object,), {})
String.register(str)
String.register(bytes)
if sys.version_info[0] == 2:
    String.register(unicode)


File = ABCMeta("File", (object,), {})
File.register(bool)
File.register(float)
File.register(int)
File.register(bytes)
File.register(str)
File.register(type(None))
if sys.version_info[0] == 2:
    File.register(types.FileType)
    File.register(unicode)
    File.register(long)


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
        return [str(x) for x in list(obj.keys()) if isinstance(x, String)]
    else:
        return [x for x in dir(obj) if not x.startswith("_")]


def _get_name(obj):
    """
    Get automatic name for an object.
    """
    if isinstance(obj, types.FunctionType):
        return obj.func_name

    try:
        text = obj.__repr__()
        if text.find("/") == -1:
            return text
    except:
        pass

    try:
        obj_id = "0x%x" % (id(obj))
        for i in ("key", "name", "id"):
            try:
                text = str(getattr(obj, i))
                if text.find("/") == -1:
                    obj_id = text
                    break
            except:
                pass

        return "%s [%s]" % (obj.__class__.__name__, obj_id)
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

    auto_names = [".repr", ]

    def __init__(self, name, parent=None, mode=0, storage=None,
                 obj=None, root=None, callback=None, **kwarg):

        # respect preset mode
        if not (mode | self.mode):
            self.mode = stat.S_IFDIR

        self.preserve_name = name is not None

        if mode:
            self.mode = mode

        Inode.__init__(self, name, parent, mode, storage)
        if hasattr(self.parent, "stack"):
            self.stack = self.parent.stack
        else:
            self.stack = {}
        self.kwarg = kwarg
        self.root = root
        self.callback = callback
        self.blacklist = None
        self.blacklist = kwarg.get("blacklist", None) or \
            self.parent.blacklist
        if isinstance(self.blacklist, List):
            if self.absolute_path(stop=self.get_root()) in self.blacklist:
                self.destroy()
                raise Eperm()
        # force self.observe, bypass property setter
        self.__observe = None
        cycle_detect = kwarg.get("cycle_detect", "symlink")
        # create the hook to the object only on the object root vInode
        try:
            if self.root:
                self.observe = obj
                self.stack[id(self.observe)] = self
            else:
                # cycle links detection
                if cycle_detect != "none" and self.mode & stat.S_IFDIR:
                    self._check_cycle()
        except Eexist as e:
            if cycle_detect == "symlink":
                self.write(self.relative_path(e.target.absolute_path()))
                e.target.cleanup[str(id(self))] = (self.storage.destroy,
                                                   (self,))
                self.mode = stat.S_IFLNK
            else:
                self.destroy()
                raise e
        except Exception as e:
            self.destroy()
            raise e
        if (self.mode & stat.S_IFDIR) and kwarg.get("repr", True):
            self.children[".repr"] = vRepr(".repr", self)

    def relative_path(self, target):
        to_root = [".."] * (len(self.absolute_path().split("/")) - 2)
        return "%s%s" % ("/".join(to_root), target)

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

        try:
            # we can not use callback here, 'cause it forces
            # weakref to generate different proxies for one
            # object and it breaks cycle reference detection
            #
            # this won't work: lambda x: self.storage.remove(self)
            if not self.kwarg.get("use_weakrefs", True):
                raise Exception()
            wp = weakref.proxy(obj)
        except:
            wp = obj

        self.__observe = wp

    observe = property(_get_observe, _set_observe)

    def _check_cycle(self):
        try:
            if not self.kwarg.get("use_weakrefs", True):
                raise Exception()
            self_id = id(weakref.proxy(self.observe))
        except:
            self_id = id(self.observe)
        if self_id in self.stack:
            raise Eexist(self.stack[self_id])
        self.stack[self_id] = self
        self.cleanup["stack"] = (self.stack.pop, (id(self.observe),))

    @restrict
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
                if self.callback:
                    getattr(self.observe, self.callback)(self.getvalue())
                elif isinstance(self.observe, bool):
                    _setattr(self.parent.observe, self.name,
                             self.getvalue().lower() in
                             ("yes", "true", "on", "t", "1"))
                else:
                    _setattr(self.parent.observe, self.name,
                             type(self.observe)(self.getvalue()))
            except Exception as e:
                logging.debug("[%s] commit() failed: %s" % (
                    self.path, str(e)))

    @restrict
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
                        if k.observe is not None and not self.preserve_name:
                            if _get_name(k.observe) != i:
                                k.name = _get_name(k.observe)
                except:
                    logging.debug("destroying %s" % (k.name))
                    logging.debug("%s" % (k.cleanup))
                    k.destroy()
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
                self.children[i].destroy()
            for i in to_create:
                self.storage.create(name=i, parent=self,
                                    obj=_getattr(self.observe, i),
                                    **self.kwarg)


class vFunction(vInode):
    """
    A function directory. It contains three files (among others):

    * ``call`` -- function call interface
    * ``context`` -- creates new ``call`` files
    * ``code`` -- function source
    """

    def __init__(self, *argv, **kwarg):
        kwarg['cycle_detect'] = 'none'

        vInode.__init__(self, *argv, **kwarg)
        try:
            self.children["code"] = vFunctionCode("code", self,
                                                  cycle_detect="none")
            self.children["call"] = vFunctionCall("call", self,
                                                  cycle_detect="none")
            self.children["context"] = vFunctionContext("context", self,
                                                        cycle_detect="none")
        except Exception as e:
            self.destroy()
            raise e

    def sync(self):
        pass

    def get_args(self, skip=None):
        if skip is None:
            skip = []
        sig = []
        sig_i = inspect.getargspec(self.observe)
        # get start index for arguments with default values
        try:
            def_start = len(sig_i.args) - len(sig_i.defaults)
        except:
            def_start = len(sig_i.args)
        for i in range(len(sig_i.args)):
            if sig_i.args[i] in skip:
                continue
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
        return sig


class vFunctionCall(vInode):
    """
    The ``call`` file initially contains the function parameters
    to be filled in. It is in .ini format, all parameters should
    be placed in the [call] section. Each parameter should have
    a value (only simple literals allowed yet).

    For example, you have the next ``call`` file::

        [call]
        arg1
        arg2 = 20
        *argv
        **kwarg

    Then you can fill it like that::

        [call]
        arg1 = 'some value'
        arg2 = 20   # 20 was the default value, you can change it
        argv = [0, 1, 2, 3]
        kwarg = {"key1": "value1", "key2": "value2"}

    The function then will receive all the parameters you filled.
    By write()/close() the ``call`` file will run the method.

    .. note::
        The sequence should be exactly like that:
            * open()
            * ... read() parameters tempalte [optional]
            * write() parameters
            * close()
            * open() again
            * read() function result (or backtrace)
            * close()

        It can be done by simple shell cat / echo. If you use
        vim, please note, that by default it does not write files
        in-place, but use create/mv scheme. It will not work with
        ``call`` files.
    """
    mode = stat.S_IFREG
    called = False

    @property
    def observe(self):
        return self.parent.observe

    def sync(self):
        if not self.called:
            self.seek(0)
            self.truncate()
            self.write("[call]\n%s" % ("\n".join(
                self.parent.get_args(skip=("self",)))))

    def commit(self):
        if self.length == 0:
            return
        self.called = True
        self.seek(0)
        config = ConfigParser()
        try:
            config.readfp(self)
            kwarg = dict([(x[0], ast.literal_eval(x[1])) for x
                          in config.items('call')])
            result = self.observe(**kwarg)
        except:
            result = traceback.format_exc()
        self.seek(0)
        self.truncate()
        self.write(str(result))


class vFunctionContext(vInode):
    """
    The ``context`` file is a dynamic file that creates new
    call context by reading it. If you want to use several
    processes to make concurrent calls with ``call`` file, you
    can face a race condition, like that::

        call file:
        process1 write() ---> call[1]
                              results[1]
                              call[2]    <--- process2 write()
        process1 read()  <--- results[2] ---> process2 read()

    To avoid such races, you can create new call contexts::

        $ cd function/
        $ export CONTEXT=`cat context`
        $ echo $PARAMETERS >$CONTEXT
        $ export RESULT=`cat $CONTEXT`
        $ rm -f $CONTEXT

    In other words, by opening ``context`` you generate new
    ``call``-files, that can be used independently.
    """
    mode = stat.S_IFREG
    length = len("call-%s" % (uuid.uuid4()))

    @property
    def observe(self):
        return self.parent.observe

    def open(self):
        new = vFunctionCall("call-%s" % (uuid.uuid4()), self.parent,
                            cycle_detect="none")
        self.parent.auto_names.append(new.name)
        self.seek(0)
        self.truncate()
        self.write(new.name)
        self.seek(0)


class vFunctionCode(vInode):
    """
    The ``code`` file contains the function source. If the script
    can not load the source, ``code`` contains the disassembled
    code and the function signature.
    """
    mode = stat.S_IFREG

    @property
    def observe(self):
        return self.parent.observe

    def sync(self):
        self.seek(0)
        self.truncate()
        # write function code
        try:
            self.write(inspect.getsource(self.observe))
        except:
            # write function signature
            self.write("#  %s(%s)\n\n" % (self.parent.name, ", ".join(
                self.parent.get_args())))
            # disassemble the code
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
            if isinstance(self.observe, unicode):
                self.write(bytes(self.observe.encode('utf-8')))
            else:
                self.write(bytes(self.observe))
        except:
            self.write(traceback.format_exc())


class ObjectFS(Storage):
    """
    ObjectFS storage class. Though there is no limit of
    ObjectFS instances, the module starts only one storage.
    """

    def create(self, name=None, parent=None, obj=None, mode=0, **config):
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
        with self.lock:
            if not parent:
                parent = self.root

            if not name:
                name = _get_name(obj)

            if isinstance(obj, Skip) or \
                    (isinstance(obj, Func) and not
                     config.get("export_functions", False)):
                return

            if name.startswith("_"):
                return

            try:
                klass = Inode
                mode |= stat.S_IFREG
                if config:
                    if isinstance(obj, Func) and \
                            config.get("export_functions", False):
                        klass = vFunction
                        mode = stat.S_IFDIR
                    elif isinstance(obj, File) or config.get('is_file', False):
                        klass = vLiteral
                    else:
                        klass = vInode
                        mode = stat.S_IFDIR
                new = parent.create(name,
                                    klass=klass,
                                    obj=obj,
                                    mode=mode,
                                    **config)
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


class Export(object):
    '''
    Class decorator
    '''
    def __init__(self, obj, config=None):
        global fs
        self.fs = fs
        self.obj = obj
        self.config = {'root': True,
                       'name': None}
        self.config.update(config or {})
        if isinstance(self.obj, types.FunctionType):
            self.config['export_functions'] = True
            self.config['use_weakrefs'] = False
            self.create(self.obj, self.config)
            self.__call__ = obj

    def __call__(self, *argv, **kwarg):
        config = {}
        config.update(self.config)
        obj = self.obj(*argv, **kwarg)
        for attr in ('basedir',
                     'name',
                     'on_commit',
                     'on_open'):
            value = config.get(attr, '')
            if isinstance(value, basestring) and value and value[0] == '@':
                config[attr] = getattr(obj, value[1:])
        self.create(obj, config)
        return obj

    def mkdir(self, basedir):
        if isinstance(basedir, basestring):
            basedir = basedir.split('/')

        parent = self.fs.root
        for name in basedir:
            if name != '':
                try:
                    parent = parent.children[name]
                except:
                    parent = vInode(name,
                                    parent,
                                    mode=stat.S_IFDIR,
                                    cycle_detect="none")
        return parent

    def create(self, obj, config):
        self.fs.create(parent=self.mkdir(config.get('basedir', '')),
                       obj=obj,
                       mode=config.pop('mode', 0o700),
                       **config)


def export(obj=None, **kwarg):
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

    In the case when __init__() is not called (e.g., in pickling or
    SQLAlchemy), on can use `@export` on some particular method. In
    this case make sure that `@export` is the last in the decorator
    chain::

        class Record(Base):
            field1 = Column(String)
            field2 = Column(String)

            @reconstructor
            @export(set_hook=True)
            def hook(self):
                pass

    Right now supported parameters are:
        * **set_hook** -- use the function as a reconstruction hook
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
        * **cycle_detect** -- The cycle reference detection mode. Can be:
            * ``none`` -- No cycle detection, the FS will not try
              to watch references to the object from existing inodes.
              So, if the object (or one of its children) will have a
              reference to itself, it will be represented on the FS
              as a new subdirectory, and so forth to the infinity.
            * ``symlink`` -- Inodes, referencing the same objects, as
              an existing inode does, will be created as symlinks.
              This is the default behaviour.
            * ``drop`` -- Such inodes will not be created at all. If
              you want your FS for some reason be searchable by
              recursive grep, you should use this option.
    """
    if obj:
        return Export(obj, **kwarg)
    else:
        def wrapper(obj):
            return Export(obj, **kwarg)
        return wrapper


# make the module safe for import
__all__ = ["export", "srv"]
