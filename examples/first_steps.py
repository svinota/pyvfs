#!/usr/bin/env python
"""
Simplest PyVFS example
"""

# start PyVFS thread and import the decorator
from pyvfs.objectfs import MetaExport

# Python3 support
import sys
if sys.version_info[0] > 2:
    def raw_input(s):
        return input(s)


class Example(object):

    # export all objects of the Example class
    __metaclass__ = MetaExport

    def __init__(self, text):
        self.text = text

# spawn several objects
objects_A = [Example(x) for x in range(10)]

# now you can mount your script with the command
# mount -t 9p -o ro,port=10001 127.0.0.1 /mnt

# wait for input
# W: do not forget to umount! :)
raw_input("press enter to exit >")
