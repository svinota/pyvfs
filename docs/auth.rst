.. _auth:

Authentication issues
---------------------

Depending on the protocol you use, you can face several authentication
issues with accessing your filesystem. Most of them are covered here.
If not, please create a bug record here:
https://github.com/svinota/pyvfs/issues

FUSE
++++

Fuse filesystem is mounted to the local system immediately as
the script starts. But by default, to access your FS, you must
have the same credentials as the script does. It means, that
by default no other users can access your FS, even root. To change
this behaviour, you can use two environment variables:

 * **PYVFS_ALLOW_ROOT=True** will open your mountpoint to the root
 * **PYVFS_ALLOW_OTHER=True** will do the same for other users

.. note::
    You should have ``user_allow_other`` in ``/etc/fuse.conf``,
    if you want to do this, otherwise options will be ignored.

9p FS
+++++

By default, ``9p`` protocol runs on 127.0.0.1:10001 without any
authentication, anyone from the local host can mount the FS and
gain read/write access. This can be managed in several ways:

Use UNIX-socket
~~~~~~~~~~~~~~~

For localhost, you can use UNIX-domain sockets instead of TCP
socket. Created UNIX-socket can have access rights that prevent
unauthorized access::

    export PYVFS_ADDRESS=/tmp/socket
    export PYVFS_PORT=660
    python my_script.py &>/dev/null &

Please note, that with UNIX sockets **PYVFS_PORT** means file
access mode. To mount the FS with usual system mount, you have to
set up ``trans`` option::

    mount -t 9p -o trans=unix /tmp/socket /mnt

Use PKI auth
~~~~~~~~~~~~

Another possibility is PKI-authentication, supported by py9p library.
To engage it, you have to set up **PYVFS_AUTHMODE** environment
variable to ``pki``::

    ... on the server side:
    export PYVFS_AUTHMODE=pki
    python my_script.py

    ... on the client side:
    cl.py -m pki 127.0.0.1:10001

The PKI auth requires a public key for a user on the server side,
and a private key for that user on the client side. By default,
the user is the current username, and the key is loaded from
``~/.ssh/id_rsa[.pub]``. If you want use different names and key
locations, use **PYVFS_KEYFILES** dictionary::

    ... on the server side:
    export PYVFS_AUTHMODE=pki
    export PYVFS_KEYFILES='{"admin": "/etc/pki/admin_key.pub"}'

    ... on the client side:
    fuse9p -c pki -k /root/admin_key.priv admin@127.0.0.1:10001
 
.. note::
    Linux kernel v9fs implementation does not support nor pki,
    neither sk1/2 authentication for 9p2000 protocol. If you
    set up authmode, you will not be able to mount your fs with
    standard Linux mount command. In this case, consider usage
    of UNIX-socket and not set up authmode.

