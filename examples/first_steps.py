#!/usr/bin/env python
"""
Simplest PyFS example
"""

# start PyFS thread and import the decorator
from objectfs.pyfs import export


# export all objects of the Example class
@export
class Example(object):

    def __init__(self, text):
        self.text = text

# spawn several objects
objects_A = [Example(x) for x in range(5)]

# now you can mount your script with the command
# mount -t 9p -o ro,port=10001 127.0.0.1 /mnt

# wait for input
# W: do not forget to umount! :)
raw_input("press enter to exit >")
