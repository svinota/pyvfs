"""
"""
import fuse
import errno
import stat

class fStat(fuse.Stat):
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

# 8<-----------------------------------------------------------------------
#

fuse.fuse_python_api = (0, 2)

class ffs(fuse.Fuse, object):
    """
    """

    def __init__(self, storage, *argv, **kwarg):
        fuse.Fuse.__init__(self, *argv, **kwarg)
        self.mountpoint = '/'
        self.storage = storage
        self.root = self.storage.root

    def open(self, path, size, offset):
        try:
            f = self.storage.checkout(hash8(path))
        except:
            return -errno.ENOENT
        f.sync()

    def getattr(self, path):
        try:
            f = self.storage.checkout(hash8(path))
        except Exception as e:
            import traceback
            traceback.print_exc()
            return -errno.ENOENT
        
        return fStat(f)

    def readdir(self, path, offset):
        try:
            f = self.storage.checkout(hash8(path))
            for i in list(f.children.keys()):
                print "debug: %s" % (i)
                yield fuse.Direntry(i)

        except:
            import traceback
            traceback.print_exc()
            yield -errno.ENOENT

    def read(self, path, size, offset):
        try:
            f = self.storage.checkout(hash8(path))
        except:
            return -errno.ENOENT

        if offset == 0:
            f.sync()

        return self.storage.read(f.path, size, offset)
