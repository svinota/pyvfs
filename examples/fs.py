#!/usr/bin/env python

from pyvfs.vfs import Storage
from pyvfs.utils import Server

# Create an empty read-write storage
#
st = Storage()
#
# Attach it to the server and run
#
# The protocol and options will be set up after
# environment variables, see documentation.
#
srv = Server(st)
#
# run server in the foreground
#
srv.run()
