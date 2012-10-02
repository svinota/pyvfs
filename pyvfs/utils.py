"""
pyvfs.utils -- utility classes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Utility classes for VFS
"""
from collections import deque
from pyvfs.vfs import Inode


class logInode(Inode):
    """
    Deque-based log file. Should be read-only on the
    filesystem. Can be used as a stream for Python
    ``logging.StreamHandler()`` objects. Stores ``maxlen``
    of records, addition of records above ``maxlen`` at the same
    time discards discards old records.
    """

    def __init__(self, name, parent, maxlen=30):
        Inode.__init__(self, name, parent)
        self.deque = deque(maxlen=maxlen)

    def sync(self):
        self.seek(0)
        self.truncate()
        for i in self.deque:
            Inode.write(self, i)

    def write(self, value):
        self.deque.append(value)

    def flush(self):
        pass
