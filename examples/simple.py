#!/usr/bin/env python
"""
Simple PyFS example
"""

# start PyFS thread and import decorator
from objectfs.pyfs import export


# export all objects of the Example class
@export
class Example(object):

    def __init__(self, text):
        self.text = text


# spawn several objects
objects = [Example(x) for x in range(10)]

# wait for input
raw_input("press enter to exit >")
