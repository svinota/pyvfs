"""
pyvfs.v9fs -- 9pfs connector
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

9p2000 abstraction layer, is used to plug VFS into py9p
"""
import stat
from py9p import py9p


def mode2stat(mode):
    return (mode & 0o777) |\
            ((mode & py9p.DMDIR) >> 17) |\
            ((mode & py9p.DMSYMLINK) >> 10) |\
            ((mode & py9p.DMSYMLINK) >> 12)


def mode2plan(mode):
    return (mode & 0o777) | \
            ((mode & stat.S_IFDIR) << 17) |\
            (int(mode == stat.S_IFLNK) << 25)


def inode2dir(inode):
    return py9p.Dir(
            dotu=0,
            type=0,
            dev=0,
            qid=py9p.Qid((mode2plan(inode.mode) >> 24) & py9p.QTDIR, 0,
                inode.path),
            mode=mode2plan(inode.mode),
            atime=inode.atime,
            mtime=inode.mtime,
            length=inode.length,
            name=inode.name,
            uid=inode.uid,
            gid=inode.gid,
            muid=inode.muid)

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

    def create(self, srv, req):
        f = self.storage.checkout(req.fid.qid.path)
        new = self.storage.create(req.ifcall.name, f,
            mode2stat(req.ifcall.perm))
        if new.mode == stat.S_IFLNK:
            new.write(req.ifcall.extension)
        req.ofcall.qid = py9p.Qid((req.ifcall.perm >> 24) & py9p.QTDIR, 0,
            new.path)
        srv.respond(req, None)

    def open(self, srv, req):
        f = self.storage.checkout(req.fid.qid.path)
        if req.ifcall.mode & py9p.OTRUNC:
            f.seek(0)
            f.truncate()
            f.commit()
        else:
            f.sync()
            f.open()
        srv.respond(req, None)

    def walk(self, srv, req, fid=None):

        fd = fid or req.fid
        f = self.storage.checkout(fd.qid.path)
        f.sync()

        for (i, k) in list(f.children.items()):
            if req.ifcall.wname[0] == i:
                qid = py9p.Qid((mode2plan(k.mode) >> 24) & py9p.QTDIR, 0,
                    hash(k))
                req.ofcall.wqid.append(qid)
                if len(req.ifcall.wname) > 1:
                    req.ifcall.wname.pop(0)
                    self.walk(srv, req, k)
                else:
                    srv.respond(req, None)
                return

        srv.respond(req, "file not found")
        return

    def wstat(self, srv, req):

        self.storage.checkout(req.fid.qid.path)
        s = req.ifcall.stat[0]
        self.storage.wstat(req.fid.qid.path, s)
        srv.respond(req, None)

    def stat(self, srv, req):
        f = self.storage.checkout(req.fid.qid.path)
        f.sync()
        r = inode2dir(f)
        if f.mode == stat.S_IFLNK:
            r.extension = f.getvalue()
        req.ofcall.stat.append(r)
        srv.respond(req, None)

    def write(self, srv, req):
        req.ofcall.count = self.storage.write(req.fid.qid.path,
            req.ifcall.data, req.ifcall.offset)
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

        if mode2plan(f.mode) & py9p.DMDIR:
            f.sync()
            req.ofcall.stat = []
            for (i, k) in list(f.children.items()):
                if i not in (".", ".."):
                    req.ofcall.stat.append(inode2dir(k))
        else:
            if req.ifcall.offset == 0:
                f.sync()
            req.ofcall.data = self.storage.read(f.path, req.ifcall.count,
                req.ifcall.offset)
            req.ofcall.count = len(req.ofcall.data)

        srv.respond(req, None)
