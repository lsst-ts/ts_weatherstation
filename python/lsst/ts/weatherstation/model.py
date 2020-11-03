# This file is part of ts_weatherstation.
#
# Developed for the LSST Telescope and Site Systems.
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

__all__ = ["Model"]


import logging

from lsst.ts.weatherstation import controllers

available_controllers = {"lsst": controllers.LSSTWeatherStation}


class Model:
    """An interface class for generic weather stations to connect to the
    WeatherStation CSC.
    """

    def __init__(self):

        self.log = logging.getLogger(__name__)

        # List of weather topics to publish
        self.weather_topics = [
            "weather",
            "windDirection",
            "windGustDirection",
            "windSpeed",
            "airTemperature",
            "relativeHumidity",
            "dewPoint",
            "snowDepth",
            "solarNetRadiation",
            "airPressure",
            "precipitation",
            "soilTemperature",
        ]

        self.controller = None

    def setup(self, setting, simulation_mode):
        """Setup the model with the given setting.

        Parameters
        ----------
        setting : `object`
            The configuration as described by the schema at ``schema_path``,
            as a struct-like object.
        simulation_mode : `int`
            Requested simulation mode; 0 for normal operation.
        """

        if self.controller is not None:
            self.log.warning("Controller already set. Unsetting.")
            self.unset_controller()

        self.controller = available_controllers[setting.type]()
        self.controller.setup(setting, simulation=simulation_mode)

    def unset_controller(self):
        """Unset controller. This will call unset method on controller and make
        controller = None.
        """
        self.controller.unset()
        self.controller = None

    async def get_weatherstation_data(self):
        """A coroutine to get data from the controller.

        Returns
        -------
        weather_data: dict
            A dictionary with the WeatherStation data.

        """
        return await self.controller.get_data()
