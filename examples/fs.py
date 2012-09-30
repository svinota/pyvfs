#!/usr/bin/env python

from objectfs.v9fs import v9fs
from objectfs.vfs import Storage
import py9p


if __name__ == "__main__":
    storage = Storage()
    srv = py9p.Server(listen=('127.0.0.1', 8000), chatty=True, dotu=True)
    srv.mount(v9fs(storage))
    srv.serve()
