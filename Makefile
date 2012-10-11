# 	Copyright (c) 2012 Peter V. Saveliev
#
# 	This file is part of PyVFS project.
#
# 	PyVFS is free software; you can redistribute it and/or modify
# 	it under the terms of the GNU General Public License as published by
# 	the Free Software Foundation; either version 3 of the License, or
# 	(at your option) any later version.
#
# 	PyVFS is distributed in the hope that it will be useful,
# 	but WITHOUT ANY WARRANTY; without even the implied warranty of
# 	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# 	GNU General Public License for more details.
#
# 	You should have received a copy of the GNU General Public License
# 	along with PyVFS; if not, write to the Free Software
# 	Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

version ?= "0.2"
release ?= "0.2.3"
python ?= "python"

ifdef root
	override root := "--root=${root}"
endif

ifdef lib
	override lib := "--install-lib=${lib}"
endif


all:
	@echo targets: dist, install

clean:
	rm -rf dist build MANIFEST
	find . -name "*pyc" -exec rm -f "{}" \;
	make -C docs clean

check:
	for i in pyvfs examples tests; \
		do pep8 $$i || exit 1; \
		pyflakes $$i || exit 1; \
		done
	2to3 pyvfs

setup.py docs/conf.py:
	gawk -v version=${version} -v release=${release} -v flavor=${flavor}\
		-f configure.gawk $@.in >$@

update-version: setup.py docs/conf.py

docs: clean update-version
	make -C docs html

dist: clean update-version
	${python} setup.py sdist

rpm: dist
	rpmbuild -ta dist/*tar.gz

install: clean update-version
	${python} setup.py install ${root} ${lib}

