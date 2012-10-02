Name: python-module-pyvfs
Version: 0.1.1
Release: alt1
Summary: Simple python VFS library
License: GPL
Group: Development/Python
URL: https://github.com/svinota/pyvfs

BuildArch: noarch
BuildPreReq: python-devel rpm-build-python

Source: %name-%version.tar

%description
PyVFS is a simple VFS library written in Python. It consists of
several layers, allowing to change low-level protocol implementation.

The library can be used to create own servers as well as deploy
bundled applications, e.g. pyvfs.objectfs -- the library, that allows
to represent Python objects as files.

%prep
%setup

%install
%makeinstall python=%{__python} root=%buildroot lib=%{python_sitelibdir}

%files

%{python_sitelibdir}/pyvfs*

%changelog
* Tue Oct  2 2012 Peter V. Saveliev <peet@altlinux.org> 0.1.1-alt1
- initial build
