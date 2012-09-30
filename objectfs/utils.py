"""
"""
from collections import deque
from objectfs.vfs import Inode


class logInode(Inode):
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
