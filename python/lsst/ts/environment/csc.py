import asyncio
import traceback
import logging
import pathlib

from lsst.ts.salobj import (base_csc, ConfigurableCsc, State)

from .model import Model

__all__ = ['CSC']


TELEMETRY_LOOP_ERROR = 7801
"""Error in the telemetry loop (`int`).

This error code is published in
`Environment_logevent_errorCodeC` if there is an error in
the telemetry loop.
"""
CONTROLLER_START_ERROR = 7802
"""Error starting the model controller (`int`)

this error code is published in
`Environment_logevent_errorCodeC` if there is an error
calling `self.model.controller.start()`.
"""
CONTROLLER_STOP_ERROR = 7803
"""Error stopping the model controller (`int`)

this error code is published in
`Environment_logevent_errorCodeC` if there is an error
calling `self.model.controller.stop()`.
"""


class CSC(ConfigurableCsc):
    """Commandable SAL Component (CSC) for the Environment monitoring system
    (a.k.a. Weather Station).
    """

    def __init__(self, index, config_dir=None,
                 initial_state=State.STANDBY,
                 initial_simulation_mode=0):
        """
        Initialize CSC.
        """

        self.model = Model()  # instantiate the model so I can have the settings once the component is up

        schema_path = pathlib.Path(__file__).resolve().parents[4].joinpath("schema",
                                                                           "Environment.yaml")

        super().__init__("Environment", index=index,
                         schema_path=schema_path,
                         config_dir=config_dir,
                         initial_state=initial_state,
                         initial_simulation_mode=initial_simulation_mode)

        self.loop_die_timeout = 5  # how long to wait for the loops to die?

        self.telemetry_loop_running = False
        self.telemetry_loop_task = None

    async def end_enable(self, id_data):
        """End do_enable; called after state changes
        but before command acknowledged.

        This method will call `start` on the model controller and start the
        telemetry
        loop.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data
        """
        try:
            await self.model.controller.start()
        except Exception as e:
            self.evt_errorCode.set_put(errorCode=CONTROLLER_START_ERROR,
                                       errorReport='Error starting model controller.',
                                       traceback=traceback.format_exc())
            self.log.exception(e)
            self.fault()
            raise
        self.telemetry_loop_task = asyncio.ensure_future(self.telemetry_loop())

        await super().end_enable(id_data)

    async def begin_disable(self, id_data):
        """Begin do_disable; called before state changes.

        This method will try to gracefully stop the telemetry loop by setting
        the running flag to False, then stops the model controller.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data

        """
        self.telemetry_loop_running = False
        try:
            self.model.controller.stop()
        except Exception as e:
            self.evt_errorCode.set_put(errorCode=CONTROLLER_STOP_ERROR,
                                       errorReport='Error stopping model controller.',
                                       traceback=traceback.format_exc())
            self.log.exception(e)
            self.fault()

        await super().begin_disable(id_data)

    async def end_disable(self, id_data):
        """ After switching from enable to disable, wait for telemetry loop to
        finish. If it takes longer then a timeout to finish, cancel the future.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data
        """
        await self.wait_loop(self.telemetry_loop_task)

        await super().end_disable(id_data)

    def fault(self, code=None, report=""):
        """Enter the fault state.

        Subclass parent method to disable corrections in the wait to FAULT
        state.

        Parameters
        ----------
        code : `int` (optional)
            Error code for the ``errorCode`` event; if None then ``errorCode``
            is not output and you should output it yourself.
        report : `str` (optional)
            Description of the error.
        """

        # Stop the controller.
        try:
            self.model.controller.stop()
        except Exception as e:
            self.log.error("Exception trying to stop model controller.")
            self.log.exception(e)

        # Logging error report from the controller
        self.log.error(f"Error report from controller: \n [START]"
                       f"{self.model.controller.error_report()!r} \n [END]")
        self.model.controller.reset_error()

        super().fault(code=code, report=report)

    @staticmethod
    def get_config_pkg():
        return 'ts_config_ocs'

    async def configure(self, config):
        """Configure the CSC.

        Parameters
        ----------
        config : `object`
            The configuration as described by the schema at ``schema_path``,
            as a struct-like object.

        Notes
        -----
        Called when running the ``start`` command, just before changing
        summary state from `State.STANDBY` to `State.DISABLED`.
        """
        self.model.setup(config,
                         simulation_mode=self.simulation_mode)

    async def implement_simulation_mode(self, simulation_mode):
        """Implement going into or out of simulation mode.

        Parameters
        ----------
        simulation_mode : `int`
            Requested simulation mode; 0 for normal operation.

        """
        if self.summary_state != State.STANDBY:
            raise RuntimeError(f"CSC must be in {State.STANDBY!r} state to change simulation "
                               f"mode. Current state is {self.state!r}. "
                               f"Current simulation mode is {self.simulation_mode}.")

    async def telemetry_loop(self):
        """Telemetry loop coroutine. This method should only be running if the
        component is enabled. It will get
        the weather data from the controller and publish it to SAL.

        """
        if self.telemetry_loop_running:
            raise RuntimeError('Telemetry loop still running...')
        self.telemetry_loop_running = True

        while self.telemetry_loop_running:
            try:
                self.evt_logMessage.set_put(level=logging.DEBUG,
                                            message=f"Getting data...")
                weather_data = await self.model.get_evironment_data()

                if weather_data is None:
                    self.log.warning("No data from controller.")
                    self.log.error(f"{self.model.controller.error_report()!r}")
                else:
                    self.log.debug(f"Got {weather_data}")
                    for topic_name in weather_data:
                        telemetry = getattr(self, f'tel_{topic_name}', None)
                        if telemetry is not None:
                            telemetry.set_put(**weather_data[topic_name])
            except Exception as e:
                # If there is an exception go to FAULT state, log the exception and break the loop
                error_topic = self.evt_errorCode.DataType()
                error_topic.errorCode = TELEMETRY_LOOP_ERROR
                error_topic.errorReport = 'Error in the telemetry loop coroutine.'
                error_topic.traceback = traceback.format_exc()
                self.evt_errorCode.put(error_topic)
                self.log.exception(e)
                self.fault()
                self.model.controller.stop()
                break

        self.evt_logMessage.set_put(level=logging.INFO,
                                    message="Telemetry loop dying.",
                                    traceback=traceback.format_exc())

    async def wait_loop(self, loop):
        """A utility method to wait for a task to die or cancel it and handle
        the aftermath.

        Parameters
        ----------
        loop : _asyncio.Future

        """
        # wait for telemetry loop to die or kill it if timeout
        timeout = True
        for i in range(self.loop_die_timeout):
            if loop.done():
                timeout = False
                break
            await asyncio.sleep(base_csc.HEARTBEAT_INTERVAL)
        if timeout:
            loop.cancel()
        try:
            await loop
        except asyncio.CancelledError:
            self.log.info('Loop cancelled...')
        except Exception as e:
            # Something else may have happened. I still want to disable as this will stop the loop on the
            # target production
            self.log.exception(e)
