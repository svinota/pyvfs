#!/usr/bin/env python
"""
Simple PyVFS example
"""

# start PyVFS thread and import the decorator
from pyvfs.objectfs import MetaExport

# Python3 support
import sys
if sys.version_info[0] > 2:
    def raw_input(s):
        return input(s)


# export all objects of the Example class
# do not export "boo" atributes (see Child class)

class Example(object):

    __metaclass__ = MetaExport
    __inode__ = {'blacklist': ['boo'],
                 'mode': 0o644,
                 'is_file': '@is_file',
                 'name': '@text'}
    dala = "bala"

    def __init__(self, text):
        """
        PyVFS @export decorator substitutes the constructor
        with wrapped function, that creates weakref.proxy()
        to the object.
        """
        print "Example init"
        self.text = '%s (%s)' % (self.__class__.__name__, text)
        self.is_file = True
        self.vala = "dala"
        print globals()
        print dir(self)
        print self.__dict__

    def bala(self):
        print "dala"

    def __repr__(self):
        """
        Files inside the object tree are named after attributes
        names, but the tree root is named automatically. If you
        want, you can change the naming with __repr__()
        """
        return "%s(%s) at 0x%x" % (self.__class__.__name__,
                                   self.text, id(self))


# please note, that objects of derived classes will be
# also exported
class Child(Example):

    def __init__(self, text):
        """
        The most tricky thing is that in this case the object
        will be exported by parent's __init__(), and just after
        creation it will not have all the attributes and,
        possibly, will not be ready for __repr__(). But we don't
        care, 'cause it is sync'ed in runtime, and in the case
        of failing __repr__() it will be renamed later -- you
        will not even notice that unless you will read the log
        """
        Example.__init__(self, text)
        print "Child init"
        self.is_file = False
        self.id = id(self)
        # this one will not be exported, 'cause it is
        # blacklisted
        self.boo = True

    def __repr__(self):
        """
        This __repr__() will fail at the time of object's
        export (see above), so it will cause the object's
        tree root to be renamed. To look at this you should
        export env variable PYVFS_LOG=True and cat .../log
        """
        return "%s [0x%x]" % (self.__class__.__name__, self.id)

# spawn several objects
objects_A = [Example(x) for x in range(2)]
objects_B = [Child(x) for x in range(2)]

# now you can mount your script with the command
# mount -t 9p -o ro,port=10001 127.0.0.1 /mnt

# wait for input
# W: do not forget to umount! :)
raw_input("press enter to exit >")
