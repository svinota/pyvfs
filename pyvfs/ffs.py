"""
pyvfs.ffs -- FUSE connector
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The abstraction layer for the FUSE
"""
import fuse
import errno
import stat


class fStat(fuse.Stat):
    """
    FUSE stat structure, that will represent PyVFS Inode
    """
    def __init__(self, inode):
        self.st_mode = inode.mode
        self.st_ino = 0
        self.st_dev = 0
        if inode.mode & stat.S_IFDIR:
            self.st_nlink = inode.length
        else:
            self.st_nlink = 1
        self.st_uid = inode.uidnum
        self.st_gid = inode.gidnum
        self.st_size = inode.length
        self.st_atime = inode.atime
        self.st_mtime = inode.mtime
        self.st_ctime = inode.ctime


def hash8(path):
    if path == "/":
        return 0
    return int(abs(hash(path)))


def getParts(path):
    fname = path.split("/")[-1]
    parent = path[:-(len(fname) + 1)] or "/"
    return (fname, parent)


def checkout(c):
    def wrapped(self, path, *argv):
        try:
            inode = self.storage.checkout(hash8(path))
        except:
            return -errno.ENOENT
        return c(self, inode, *argv)
    return wrapped

# 8<-----------------------------------------------------------------------
#

fuse.fuse_python_api = (0, 2)


class ffs(fuse.Fuse, object):
    """
    FUSE abstraction layer
    """

    def __init__(self, storage, *argv, **kwarg):
        fuse.Fuse.__init__(self, *argv, **kwarg)
        self.mountpoint = '/'
        self.storage = storage
        self.root = self.storage.root

    def symlink(self, path, dest):
        self.mknod(path, stat.S_IFLNK, 0)
        inode = self.storage.checkout(hash8(path))
        inode.write(dest)

    def mknod(self, path, mode, dev):
        # work only with regular files
        if dev:
            return -errno.ENOSYS
        # if it is not a file, it should be a dir
        if not mode & stat.S_IFREG:
            mode |= stat.S_IFDIR
        fname, parent = getParts(path)
        f = self.storage.checkout(hash8(parent))
        self.storage.create(fname, f, mode)

    def mkdir(self, path, mode):
        return self.mknod(path, mode, None)

    @checkout
    def readlink(self, inode):
        return inode.getvalue()

    @checkout
    def flush(self, inode):
        self.storage.commit(inode)

    @checkout
    def chmod(self, inode, mode):
        self.storage.chmod(inode, mode)

    @checkout
    def chown(self, inode, uid, gid):
        self.storage.chown(inode, uid, gid)

    @checkout
    def open(self, inode, flags):
        self.storage.open(inode)

    @checkout
    def getattr(self, inode):
        self.storage.sync(inode)
        return fStat(inode)

    @checkout
    def read(self, inode, size, offset):
        return self.storage.read(inode, size, offset)

    @checkout
    def write(self, inode, buf, offset):
        return self.storage.write(inode, buf, offset)

    @checkout
    def truncate(self, inode, size):
        self.storage.truncate(inode, size)

    @checkout
    def utime(self, inode, times):
        inode.atime = times[0]
        inode.mtime = times[1]

    @checkout
    def unlink(self, inode):
        try:
            self.storage.remove(inode)
        except:
            return -errno.EPERM

    @checkout
    def rmdir(self, inode):
        return self.unlink(inode.absolute_path())

    @checkout
    def rename(self, inode, path):
        fname, parent = getParts(path)
        parent = self.storage.checkout(hash8(parent))
        try:
            self.storage.reparent(parent, inode, fname)
        except:
            return -errno.EEXIST

    def readdir(self, path, offset):
        try:
            f = self.storage.checkout(hash8(path))
            for i in f.children:
                yield fuse.Direntry(i)

        except:
            yield -errno.ENOENT
