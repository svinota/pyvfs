%global pkgname pyvfs
%global pypname objectfs

Name: python-%{pkgname}
Version: 0.2.10
Release: 1%{?dist}
Summary: Simple python VFS library
License: GPLv2+
Group: Development/Languages
URL: https://github.com/svinota/%{pkgname}

BuildArch: noarch
BuildRequires: python2-devel
Source: http://peet.spb.ru/archives/%{pypname}-%{version}.tar.gz

%description
PyVFS is a simple VFS library written in Python. It consists of
several layers, allowing to use different low-level protocol
implementations. Now you can choose between 9p (9p2000.u) and
FUSE.

The library can be used to create own servers as well as deploy
bundled applications, e.g. pyvfs.objectfs -- the library, that allows
to represent Python objects as files.

%prep
%setup -q -n %{pypname}-%{version}

%build
# nothing to build

%install
%{__python} setup.py install --root $RPM_BUILD_ROOT

%files
%doc README* LICENSE
%{python_sitelib}/%{pkgname}*
%{python_sitelib}/%{pypname}*

%changelog
* Wed Jun 12 2013 Peter V. Saveliev <peet@redhat.com> 0.2.10-1
- Python 3 compatibility issues
- unicode literals fixed
- license changed from GPLv3+ to GPLv2+

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.2.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Thu Nov 08 2012 Peter V. Saveliev <peet@redhat.com> 0.2.7-1
- support PKI authentication

* Mon Oct 22 2012 Peter V. Saveliev <peet@redhat.com> 0.2.6-1
- symlink support
- truncate() fixed for objectfs
- pypi support

* Fri Oct 19 2012 Peter V. Saveliev <peet@redhat.com> 0.2.5-1
- new cycle detection mechanism for objectfs
- transaction-like cleanup for Inode class

* Tue Oct 16 2012 Peter V. Saveliev <peet@redhat.com> 0.2.4-1
- Function exports added
- Method calls (by FS read/write) implemented

* Sat Oct 13 2012 Peter V. Saveliev <peet@redhat.com> 0.2.3-2
- Add build section
- Change BuildRequires python2-devel
- Change to correct group 
- Include doc section 
- Use pkgname macro

* Thu Oct 11 2012 Peter V. Saveliev <peet@redhat.com> 0.2.3-1
- initial RH build

