#!/usr/bin/env python

from pyvfs.objectfs import export
import gc


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

    def __repr__(self):
        return str(id(self))

    def _get_bala(self):
        return self.__bala

    def _set_bala(self, value):
        self.__bala = value

    bala = property(_get_bala, _set_bala)

    def print_bala(self):
        print self.bala

e = []

if __name__ == "__main__":
    while True:
        a = raw_input("$ ")
        if a == "pop":
            e.pop()
        elif a == "gc":
            gc.collect()
        elif a == "ls":
            print e
            print [x for x in gc.get_objects() if isinstance(x, Bala)]
        else:
            e.append(Bala(a))
