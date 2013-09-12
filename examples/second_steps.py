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

    # this tells python to use MetaExport for this class
    # and all child classes.
    __metaclass__ = MetaExport

    # the configuration of the inode, it also will be
    # inherited by children
    __inode__ = {'blacklist': ['boo'],
                 'mode': 0o644,
                 'is_file': '@is_file',
                 'name': '@text'}

    def __init__(self, text):
        """
        Latest PyVFS revision, that uses metaclass to export
        objects, doesn't modify classed in any way. So,
        `__init__()` remains intact.
        """
        self.text = '%s (%s)' % (self.__class__.__name__, text)
        self.is_file = True
        self.vala = "dala"

    def __repr__(self):
        """
        Files inside the object tree are named after attributes
        names, but the tree root is named automatically. If you
        want, you can change the naming with `__repr__()`

        But if `is_file` == True, then `__repr__()` will return
        file's content.
        """
        return "%s(%s) at 0x%x" % (self.__class__.__name__,
                                   self.text, id(self))


# please note, that objects of derived classes will be
# also exported
class Child(Example):

    def __init__(self, text):
        Example.__init__(self, text)
        self.is_file = False
        self.id = id(self)
        # this one will not be exported, 'cause it is blacklisted
        self.boo = True


# spawn several objects
objects_A = [Example(x) for x in range(2)]
objects_B = [Child(x) for x in range(2)]

# now you can mount your script with the command
# mount -t 9p -o ro,port=10001 127.0.0.1 /mnt

# wait for input
# W: do not forget to umount! :)
raw_input("press enter to exit >")
