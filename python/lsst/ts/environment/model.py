
__all__ = ['Model']


import logging

from lsst.ts.environment import controllers

__all__ = ['Model']

available_controllers = {'lsst': controllers.LSSTWeatherStation}


class Model:
    """An interface class for generic weather stations to connect to the Environment CSC."""

    def __init__(self):

        self.log = logging.getLogger(__name__)

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
            self.log.warning('Controller already set. Unsetting.')
            self.unset_controller()

        self.controller = available_controllers[setting.type]()
        self.controller.setup(setting, simulation=simulation_mode)

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
