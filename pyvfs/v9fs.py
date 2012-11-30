"""
pyvfs.v9fs -- 9pfs connector
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

9p2000 abstraction layer, is used to plug VFS into py9p
"""
import stat
import logging
from py9p import py9p

try:
    assert hasattr(py9p, "DMSTICKY")
    assert hasattr(py9p, "mode2plan")
    assert hasattr(py9p, "mode2stat")
except Exception as e:
    logging.warning("""\n
    incompatible py9p version
    get the last here: https://github.com/svinota/py9p
    """)
    raise e


def inode2dir(inode):
    return py9p.Dir(
            dotu=1,
            type=0,
            dev=0,
            qid=py9p.Qid((py9p.mode2plan(inode.mode) >> 24) & py9p.QTDIR, 0,
                inode.path),
            mode=py9p.mode2plan(inode.mode),
            atime=inode.atime,
            mtime=inode.mtime,
            length=inode.length,
            name=inode.name,
            uid=inode.uid,
            gid=inode.gid,
            muid=inode.muid,
            extension="",
            uidnum=inode.uidnum,
            gidnum=inode.gidnum,
            muidnum=inode.muidnum)


def checkout(c):
    def wrapped(self, srv, req, *argv):
        try:
            inode = self.storage.checkout(req.fid.qid.path)
            return c(self, srv, req, inode, *argv)
        except:
            srv.respond(req, None)
    return wrapped

# 8<-----------------------------------------------------------------------
#
# 9p2000 specific layer, that represents internal storage protocol in the
# terms of 9p2000 file system. One MUST extract Inode class to the layer
# above, removeing all py9p references. A specific overloaded v9inode can
# be implemented on the top of it.
#


class v9fs(py9p.Server):
    """
    VFS 9p abstraction layer
    """

    def __init__(self, storage):
        self.mountpoint = '/'
        self.storage = storage
        self.root = inode2dir(self.storage.root)

    @checkout
    def create(self, srv, req, inode):
        new = self.storage.create(req.ifcall.name, inode,
            py9p.mode2stat(req.ifcall.perm))
        if new.mode == stat.S_IFLNK:
            new.write(req.ifcall.extension)
        req.ofcall.qid = py9p.Qid((req.ifcall.perm >> 24) & py9p.QTDIR, 0,
            new.path)
        srv.respond(req, None)

    @checkout
    def open(self, srv, req, inode):
        if req.ifcall.mode & py9p.OTRUNC:
            self.storage.truncate(inode)
        else:
            self.storage.open(inode)
        srv.respond(req, None)

    def walk(self, srv, req, fid=None):

        fd = fid or req.fid
        f = self.storage.checkout(fd.qid.path)
        self.storage.sync(f)

        for (i, k) in list(f.children.items()):
            if req.ifcall.wname[0] == i:
                qid = py9p.Qid((py9p.mode2plan(k.mode) >> 24) & py9p.QTDIR, 0,
                    hash(k))
                req.ofcall.wqid.append(qid)
                if len(req.ifcall.wname) > 1:
                    req.ifcall.wname.pop(0)
                    self.walk(srv, req, inode2dir(k))
                else:
                    srv.respond(req, None)
                return

        srv.respond(req, "file not found")
        return

    @checkout
    def wstat(self, srv, req, inode):

        istat = req.ifcall.stat[0]
        if (istat.uidnum >> 16) == 0xFFFF:
            istat.uidnum = -1
        if (istat.gidnum >> 16) == 0xFFFF:
            istat.gidnum = -1
        self.storage.chown(inode, istat.uidnum, istat.gidnum)
        # change mode?
        if istat.mode != 0xFFFFFFFF:
            self.storage.chmod(inode, py9p.mode2stat(istat.mode))
        # change name?
        if istat.name:
            inode.parent.rename(inode.name, istat.name)
        srv.respond(req, None)

    @checkout
    def stat(self, srv, req, inode):
        self.storage.sync(inode)
        p9dir = inode2dir(inode)
        if inode.mode == stat.S_IFLNK:
            p9dir.extension = inode.getvalue()
        req.ofcall.stat.append(p9dir)
        srv.respond(req, None)

    @checkout
    def write(self, srv, req, inode):
        req.ofcall.count = self.storage.write(inode,
            req.ifcall.data, req.ifcall.offset)
        srv.respond(req, None)

    @checkout
    def clunk(self, srv, req, inode):
        try:
            self.storage.commit(inode)
        except:
            pass
        srv.respond(req, None)

    @checkout
    def remove(self, srv, req, inode):
        self.storage.remove(inode)
        srv.respond(req, None)

    @checkout
    def read(self, srv, req, inode):

        if req.ifcall.offset == 0:
            self.storage.sync(inode)

        if py9p.mode2plan(inode.mode) & py9p.DMDIR:
            req.ofcall.stat = []
            for (i, k) in list(inode.children.items()):
                if i not in (".", ".."):
                    self.storage.sync(k)
                    req.ofcall.stat.append(inode2dir(k))
        else:
            req.ofcall.data = self.storage.read(inode, req.ifcall.count,
                req.ifcall.offset)
            req.ofcall.count = len(req.ofcall.data)

        srv.respond(req, None)
