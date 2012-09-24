#!/usr/bin/env python

from objectfs.pyfs import export

@export
class Bala(object):
    def __init__(self, a):
        self.bala = a
        self.sexy = self
        self.d = {
                1: self,
                2: "tratata",
                "dala": self.bala,
                "third": 3,
                "ne": "baladalal",
                }
        self.c = [
                self,
                10,
                12,
                1024,
                ]

e = []

while True:
    a = raw_input("$ ")
    if a == "pop":
        e.pop()
    else:
        e.append(Bala(a))

