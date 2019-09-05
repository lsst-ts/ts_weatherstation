# This file is part of ts_environment.
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

__all__ = ['Model']

import os, yaml, logging

from lsst.ts.environment import controllers

available_controllers = {'lsst': controllers.LSSTWeatherStation}

class Model:
    """
    An interface class for generic weather stations to connect to the Environment CSC.
    """
    def __init__(self):
        self.log = logging.getLogger(__name__)

        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config/config.yaml')

        with open(self.config_path, 'r') as stream:
            self.config = yaml.load(stream)

        # List of weather topics to publish
        self.weather_topics = ["weather",
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
                               "soilTemperature"]

        self.controller = None

    @property
    def recommended_settings(self):
        """Recommended settings property.

        Returns
        -------
        recommended_settings : str
            Recommended settings read from Model configuration file.
        """
        return 'default'  # FIXME: Read from config file

    @property
    def settings_labels(self):
        """Recommended settings labels.

        Returns
        -------
        recommended_settings_labels : str
            Comma separated string with the valid setting labels read from Model configuration file.

        """
        valid_settings = ''

        n_set = len(self.config['settingVersions']['recommendedSettingsLabels'])
        for i, label in enumerate(self.config['settingVersions']['recommendedSettingsLabels']):
            valid_settings += label
            if i < n_set-1:
                valid_settings += ','

        return valid_settings

    def setup(self, setting):
        """Setup the model with the given setting.

        Parameters
        ----------
        setting : str
            A string with the selected setting label. Must match one on the configuration file.

        Returns
        -------

        """

        if len(setting) == 0:
            setting = self.config['settingVersions']['recommendedSettingsVersion']
            self.log.debug('Received empty setting label. Using default: %s', setting)

        if setting not in self.config['settingVersions']['recommendedSettingsLabels']:
            raise RuntimeError('Setting %s not a valid label. Must be one of %s.',
                               setting,
                               self.settings_labels)

        if self.controller is not None:
            self.log.debug('Controller already set. Unsetting.')
            self.unset_controller()

        self.controller = available_controllers[self.config['setting'][setting]['type']]()
        self.controller.setup(**self.config['setting'][setting]['configuration'])

    def unset_controller(self):
        """Unset controller. This will call unset method on controller and make controller = None.

        Returns
        -------

        """
        self.controller.unset()
        self.controller = None

    async def get_evironment_data(self):
        """A coroutine to get data from the controller.

        Returns
        -------
        env_data: dict
            A dictionary with the environment data.

        """
        return await self.controller.get_data()
