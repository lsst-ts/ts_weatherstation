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

import abc

__all__ = ["BaseEnv"]


class BaseEnv(abc.ABC):
    """Base class for Environment controllers.

    This class defines the minimum set of methods required to connect to a weather station and get data
    from it in the context of the LSST CSC environment. When developing a controller for a CSC, one
    should subclass this method and overwrite the methods as required to setup and operate the weather
    station.
    """

    @abc.abstractmethod
    def setup(self, **argv):
        """Base weather station setup method.

        When subclassing avoid using argv.

        Parameters
        ----------
        argv :
            Named parameters

        """
        raise NotImplementedError()

    @abc.abstractmethod
    def unset(self):
        """Unset weather station."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def start(self):
        """Start weather station."""
        raise NotImplementedError()

    @abc.abstractmethod
    def stop(self):
        """Stop Weather Station."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def get_data(self):
        """Coroutine to wait and return new seeing measurements.

        Returns
        -------
        measurement : dict
            A dictionary with the same values of the dimmMeasurement topic SAL Event.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def error_report(self):
        """Return error report from the controller.

        Returns
        -------
        report : `str`
            String with information about last error.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def reset_error(self):
        """Reset error report.
        """
        raise NotImplementedError()
