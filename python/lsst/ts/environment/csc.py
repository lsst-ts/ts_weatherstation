import asyncio
import traceback
import logging

import SALPY_Environment

from lsst.ts.salobj import base_csc

from .model import Model

__all__ = ['CSC']


TELEMETRY_LOOP_ERROR = 7801
"""Error in the telemetry loop (`int`).

This error code is published in 
`SALPY_Environment.Environment_logevent_errorCodeC` if there is an error in 
the telemetry loop.
"""
CONTROLLER_START_ERROR = 7802
"""Error starting the model controller (`int`)

this error code is published in 
`SALPY_Environment.Environment_logevent_errorCodeC` if there is an error 
calling `self.model.controller.start()`.
"""
CONTROLLER_STOP_ERROR = 7803
"""Error stopping the model controller (`int`)

this error code is published in 
`SALPY_Environment.Environment_logevent_errorCodeC` if there is an error 
calling `self.model.controller.stop()`.
"""

class CSC(base_csc.BaseCsc):
    """Commandable SAL Component (CSC) for the Environment monitoring system
    (a.k.a. Weather Station).
    """

    def __init__(self, index):
        """
        Initialize CSC.
        """

        self.model = Model()  # instantiate the model so I can have the settings once the component is up

        super().__init__(SALPY_Environment, index=index)

        self.evt_settingVersions.set_put(recommendedSettingsVersion=self.model.recommended_settings,
                                         recommendedSettingsLabels=self.model.settings_labels)

        self.loop_die_timeout = 5  # how long to wait for the loops to die?

        self.telemetry_loop_running = False
        self.telemetry_loop_task = None

    def begin_start(self, id_data):
        """Begin do_start; called before state changes.

        This method call setup on the model, passing the selected setting.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data
        """
        self.model.setup(id_data.data.settingsToApply)
        # self.evt_settingsApplied.set_put(selectedSettings=id_data.data.settingsToApply)

    async def do_enable(self, id_data):
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
        self._do_change_state(id_data, "enable", [base_csc.State.DISABLED], base_csc.State.ENABLED)

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

    def begin_disable(self, id_data):
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
                                       errorReport='Error starting model controller.',
                                       traceback=traceback.format_exc())
            self.log.exception(e)
            self.fault()
            raise

    async def do_disable(self, id_data):
        """Transition to from `State.ENABLED` to `State.DISABLED`.

        After switching from enable to disable, wait for telemetry loop to
        finish. If it takes longer then a timeout to finish, cancel the future.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data
        """
        self._do_change_state(id_data, "disable", [base_csc.State.ENABLED], base_csc.State.DISABLED)

        await self.wait_loop(self.telemetry_loop_task)

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
                self.evt_logMessage.set_put(level=logging.DEBUG,
                                            message=f"Got {weather_data}")
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
