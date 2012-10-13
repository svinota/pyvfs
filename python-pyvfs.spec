%global pkgname pyvfs

Name: python-%{pkgname}
Version: 0.2.3
Release: 2%{?dist}
Summary: Simple python VFS library
License: GPLv3+
Group: Development/Languages
URL: https://github.com/svinota/%{pkgname}

BuildArch: noarch
BuildRequires: python2-devel
Source: http://peet.spb.ru/archives/%{pkgname}-%{version}.tar.gz

%description
PyVFS is a simple VFS library written in Python. It consists of
several layers, allowing to use different low-level protocol
implementations. Now you can choose between 9p (9p2000.u) and
FUSE.

The library can be used to create own servers as well as deploy
bundled applications, e.g. pyvfs.objectfs -- the library, that allows
to represent Python objects as files.

%prep
%setup -q -n %{pkgname}-%{version}

%build
# nothing to build

%install
%{__python} setup.py install --root $RPM_BUILD_ROOT

%files
%doc README* LICENSE
%{python_sitelib}/%{pkgname}*

%changelog
* Sat Oct 13 2012 Peter V. Saveliev <peet@redhat.com> 0.2.3-2
- Add build section
- Change BuildRequires python2-devel
- Change to correct group 
- Include doc section 
- Use pkgname macro

* Thu Oct 11 2012 Peter V. Saveliev <peet@redhat.com> 0.2.3-1
- initial RH build

