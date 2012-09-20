#!/usr/bin/env python
import time
import os
import stat
import py9p
import pwd
import grp
from StringIO import StringIO

DEFAULT_DIR_MODE = 0755
DEFAULT_FILE_MODE = 0644

# 8<----------------------------------------------------------------------------
#
# 9p2000 specific layer, that represents internal storage protocol in the
# terms of 9p2000 file system. One MUST extract Inode class to the layer
# above, removeing all py9p references. A specific overloaded v9inode can
# be implemented on the top of it.
#

class Inode(py9p.Dir, StringIO):
    """
    VFS inode, based on py9p.Dir
    """
    # static member for special names
    special_names = [
            ".",
            ".."
            ]
    # static member for mapping stat -> py9p
    ftypes = {
            stat.S_IFDIR:   py9p.DMDIR,
            }

    def __init__(self, name, parent=None, ftype=0, dmtype=0, storage=None):

        py9p.Dir.__init__(self, False)
        StringIO.__init__(self)

        if parent:
            self.parent = parent
        else:
            self.parent = self

        self.storage = storage or parent.storage
        self.dmtype = 0 # initially, it is a plain file
        # check for ftype
        if ftype:
            self.dmtype = self.ftypes[ftype]
        # check for dmtype
        if dmtype:
            self.dmtype = dmtype

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
        if self.dmtype & py9p.DMDIR:
            self.mode = py9p.DMDIR | DEFAULT_DIR_MODE
            self.children["."] = self
            self.children[".."] = self.parent
        else:
            self.mode = DEFAULT_FILE_MODE

    def __hash__(self):
        return self.qid.path

    def _get_name(self):
        return self.__name

    def _set_name(self, name):
        self._check_special(name)
        try:
            self.storage.unregister(self)
            del self.qid
        except:
            pass
        self.__name = name
        self.qid = py9p.Qid((self.dmtype >> 24) & py9p.QTDIR, 0,
                py9p.hash8(self._absolute_name()))
        self.storage.register(self)

    name = property(_get_name, _set_name)

    def _check_special(self, *args):
        for i in args:
            if i in self.special_names:
                raise py9p.ServerError(py9p.Eperm)

    def _absolute_name(self):
        if (self.parent is not None) and (self.parent != self):
            return "%s/%s" % (self.parent._absolute_name(), self.name)
        else:
            return self.name

    def commit(self):
        pass

    def sync(self):
        pass

    def remove(self, child):
        """
        Remove a child from a directory
        """
        self._check_special(child.name)
        del self.children[child.name]

    def create(self, name, dmtype=0):
        """
        Create a child in a directory
        """
        self._check_special(name)
        # return default Inode class
        self.children[name] = Inode(name, self, dmtype=dmtype,
            storage=self.storage)
        return self.children[name]

    def rename(self, old_name, new_name):
        """
        Rename a child
        """
        self._check_special(old_name, new_name)
        self.children[new_name] = self.children[old_name]
        self.children[new_name].name = new_name
        del self.children[old_name]

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
            self.mode = ((self.mode & 07777) ^ self.mode) | (stat.mode & 07777)
        # change name?
        if stat.name:
            self.parent.rename(self.name, stat.name)

    @property
    def length(self):
        if self.qid.type & py9p.QTDIR:
            return len(self.children.keys())
        else:
            return self.len


class v9fs(py9p.Server):
    """
    VFS 9p abstraction layer
    """

    def __init__(self, storage):
        self.mountpoint = '/'
        self.storage = storage
        self.root = self.storage.root

    def create(self, srv, req):
        # get parent
        f = self.storage.checkout(req.fid.qid.path)
        req.ofcall.qid = self.storage.create(req.ifcall.name,
                req.ifcall.perm, f).qid
        srv.respond(req, None)

    def open(self, srv, req):
        '''If we have a file tree then simply check whether the Qid matches
        anything inside. respond qid and iounit are set by protocol'''
        f = self.storage.checkout(req.fid.qid.path)
        f.sync()

        if (req.ifcall.mode & f.mode) != py9p.OREAD :
            raise py9p.ServerError(py9p.Eperm)

        srv.respond(req, None)

    def walk(self, srv, req, fid = None):

        fd = fid or req.fid
        f = self.storage.checkout(fd.qid.path)
        f.sync()

        for (i, k) in f.children.items():
            if req.ifcall.wname[0] == i:
                req.ofcall.wqid.append(k.qid)
                if k.qid.type & py9p.QTDIR:
                    self.storage.chdir(k.qid.path)
                if len(req.ifcall.wname) > 1:
                    req.ifcall.wname.pop(0)
                    self.walk(srv, req, k)
                else:
                    srv.respond(req, None)
                return

        srv.respond(req, "file not found")
        return

    def wstat(self, srv, req):

        f = self.storage.checkout(req.fid.qid.path)
        s = req.ifcall.stat[0]
        self.storage.wstat(req.fid.qid.path, s)
        srv.respond(req, None)

    def stat(self, srv, req):
        f = self.storage.checkout(req.fid.qid.path)
        f.sync()
        req.ofcall.stat.append(f)
        srv.respond(req, None)

    def write(self, srv, req):
        f = self.storage.checkout(req.fid.qid.path)
        req.ofcall.count = self.storage.write(req.fid.qid.path, req.ifcall.data,
            req.ifcall.offset)
        srv.respond(req, None)

    def clunk(self, srv, req):
        try:
            self.storage.commit(req.fid.qid.path)
        except:
            pass
        srv.respond(req, None)

    def remove(self, srv, req):
        self.storage.remove(req.fid.qid.path)
        srv.respond(req, None)

    def read(self, srv, req):

        f = self.storage.checkout(req.fid.qid.path)

        if f.qid.type & py9p.QTDIR:
            f.sync()
            req.ofcall.stat = []
            for (i, k) in f.children.items():
                if i not in (".", ".."):
                    req.ofcall.stat.append(k)
        else:
            if req.ifcall.offset == 0:
                f.sync()
            req.ofcall.data = self.storage.read(f.qid.path, req.ifcall.count,
                req.ifcall.offset)
            req.ofcall.count = len(req.ofcall.data)

        srv.respond(req, None)


