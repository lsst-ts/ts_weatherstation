
import abc

__all__ = ['BaseEnv']


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
