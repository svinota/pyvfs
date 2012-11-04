#!/usr/bin/env python

from pyvfs.utils import Server

#
# The protocol and options will be set up after
# environment variables, see documentation.
#
srv = Server()
#
# run server in the foreground
#
srv.run()
