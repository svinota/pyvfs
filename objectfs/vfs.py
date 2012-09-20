"""
Internal VFS protocol
"""
import os
import stat

class Storage(object):
    """
    High-level storage insterface. Implements a simple protocol
    for the file management and file lookup dictionary.

    Should be provided with root 'inode' class on init. The 'inode'
    class MUST support the interface... that should be defined :)
    """
    def __init__(self, inode):
        self.files = {}
        self.root = inode(name="/", ftype=stat.S_IFDIR, storage=self)
        self.cwd = self.root
        self.files[hash(self.root)] = self.root

    def register(self, inode):
        """
        Register a new inode in the dictionary
        """
        self.files[hash(inode)] = inode

    def unregister(self, inode):
        """
        Remove an inode from the dictionary
        """
        del self.files[hash(inode)]

    def create(self, name, mode=0, parent=None):
        """
        Create an inode
        """
        if parent:
            self.cwd = parent
        new = self.cwd.create(name, mode)
        self.files[hash(new)] = new
        return new

    def chdir(self, target):
        self.cwd = self.files[target]

    def checkout(self, target):
        return self.files[target]

    def commit(self, target):
        f = self.checkout(target)
        if f.writelock:
            f.writelock = False
            f.commit()

    def write(self, target, data, offset=0):
        f = self.checkout(target)
        f.writelock = True
        f.seek(offset, os.SEEK_SET)
        f.write(data)
        return len(data)

    def read(self, target, size, offset=0):
        f = self.checkout(target)
        if offset == 0:
            f.sync()
        f.seek(offset, os.SEEK_SET)
        return f.read(size)

    def remove(self, target):
        f = self.checkout(target)
        f.parent.remove(f)
        del self.files[target]

    def wstat(self, target, stat):
        f = self.checkout(target)
        f.wstat(stat)


