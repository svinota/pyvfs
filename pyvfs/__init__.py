##
#
import sys
import logging
from abc import ABCMeta

log = logging.getLogger(__name__)
# Add a NullHandler to the library's top-level logger to avoid complaints
# on logging calls when no handler is configured.
# see https://docs.python.org/2/howto/logging.html#library-config
if sys.version_info >= (2, 7):  # This is only available from 2.7 onwards
    log.addHandler(logging.NullHandler())


__all__ = []
_modules = {'export': 'pyvfs.objectfs',
            'ObjectFS': 'pyvfs.objectfs',
            'Server': 'pyvfs.server'}


for name in _modules:
    module = __import__(_modules[name], globals(), locals(), [name], 0)
    obj = getattr(module, name)
    globals()[name] = obj
    __all__.append(name)
