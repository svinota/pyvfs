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
        self.storage.commit(inode.path)

    @checkout
    def chmod(self, inode, mode):
        inode.mode = mode | (inode.mode & \
                (stat.S_IFREG | stat.S_IFDIR))

    @checkout
    def chown(self, inode, uid, gid):
        if uid > -1:
            inode.uidnum = uid
        if gid > -1:
            inode.gidnum = gid

    @checkout
    def open(self, inode, flags):
        inode.sync()
        inode.open()

    @checkout
    def getattr(self, inode):
        inode.sync()
        return fStat(inode)

    @checkout
    def read(self, inode, size, offset):
        if offset == 0:
            inode.sync()
        return self.storage.read(inode.path, size, offset)

    @checkout
    def write(self, inode, buf, offset):
        return self.storage.write(inode.path, buf, offset)

    @checkout
    def truncate(self, inode, size):
        inode.seek(size)
        inode.truncate()
        inode.commit()

    @checkout
    def utime(self, inode, times):
        inode.atime = times[0]
        inode.mtime = times[1]

    @checkout
    def unlink(self, inode):
        try:
            self.storage.remove(inode.path)
        except:
            return -errno.EPERM

    @checkout
    def rmdir(self, inode):
        return self.unlink(inode.absolute_path())

    @checkout
    def rename(self, inode, path):
        fname, parent = getParts(path)
        try:
            self.storage.reparent(hash8(parent), inode, fname)
        except:
            return -errno.EEXIST

    def readdir(self, path, offset):
        try:
            f = self.storage.checkout(hash8(path))
            for i in list(f.children.keys()):
                yield fuse.Direntry(i)

        except:
            yield -errno.ENOENT
