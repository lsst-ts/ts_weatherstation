#!/usr/bin/env python
#
# This file is part of ts_weatherstation.
#
# Developed for the Vera Rubin Observatory Telescope and Site Systems.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import sys
import setuptools
import pathlib

install_requires = []
tests_require = ["pytest", "pytest-cov", "pytest-flake8", "asynctest"]
dev_requires = install_requires + tests_require + ["documenteer[pipelines]"]
scm_version_template = """# Generated by setuptools_scm
__all__ = ["__version__"]

__version__ = "{version}"
"""
tools_path = pathlib.PurePosixPath(setuptools.__path__[0])
base_prefix = pathlib.PurePosixPath(sys.base_prefix)
data_files_path = tools_path.relative_to(base_prefix).parents[1]

setuptools.setup(
    name="ts-weatherstation",
    description="LSST telescope weatherstation controller",
    use_scm_version={
        "write_to": "python/lsst/ts/weatherstation/version.py",
        "write_to_template": scm_version_template,
    },
    setup_requires=["setuptools_scm", "pytest-runner"],
    install_requires=install_requires,
    package_dir={"": "python"},
    packages=setuptools.find_namespace_packages(where="python"),
    package_data={"": ["*.rst", "*.yaml"]},
    data_files=[],
    scripts=["bin/weatherstation_csc.py"],
    tests_require=tests_require,
    extras_require={"dev": dev_requires},
    license="GPL",
    project_urls={
        "Bug Tracker": "https://jira.lsstcorp.org/secure/Dashboard.jspa",
        "Source Code": "https://github.com/lsst-ts/ts_weatherstation",
    },
)
