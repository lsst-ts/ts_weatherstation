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

__all__ = ['Environment']

import traceback, logging, pathlib, asyncio

from lsst.ts import salobj
from .model import Model

# Aliases
state = salobj.State

TELEMETRY_LOOP_ERROR: int = 7801
"""
Published in `SALPY_Environment.Environment_logevent_errorCodeC`
if error in the telemetry loop.
"""
CONTROLLER_START_ERROR: int = 7802
"""
Published in `SALPY_Environment.Environment_logevent_errorCodeC`
if error calling `self.model.controller.start()`.
"""
CONTROLLER_STOP_ERROR: int = 7803
"""
Published in `SALPY_Environment.Environment_logevent_errorCodeC`
if error calling `self.model.controller.stop()`.
"""

class Environment(salobj.ConfigurableCsc):
    """Environment CSC

    Commandable SAL Component (CSC) for the Environment monitoring system
    (a.k.a. Weather Station).

    """
    def __init__(self, config_dir=None, initial_state=state.STANDBY,
                 initial_simulation_mode=0):
        """Initialize CSC.

        Parameters
        -----------
        config_dir : `str` (optional)
            Directory of configuration files, or None for the standard
            configuration directory (obtained from `get_default_config_dir`).
            This is provided for unit testing.
        initial_state : `salobj.State` (optional)
            The initial state of the CSC. Typically one of:
            - State.ENABLED if you want the CSC immediately usable.
            - State.STANDBY if you want full emulation of a CSC.
        initial_simulation_mode : `int` (optional)
            Initial simulation mode. This is provided for unit testing,
            as real CSCs should start up not simulating, the default.
        """
        schema_path = \
            pathlib.Path(__file__).resolve().parents[4].joinpath("schema", "Environment.yaml")
        super().__init__(name="Environment", schema_path=schema_path, config_dir=config_dir,
                         index=None, initial_state=initial_state,
                         initial_simulation_mode=initial_simulation_mode)

        # instantiate model to have the settings once the component is up
        self.model = Model()

        self.evt_settingVersions.set_put(recommendedSettingsVersion=self.model.recommended_settings,
                                         recommendedSettingsLabels=self.model.settings_labels)

        # how long to wait for the loops to die?
        self.loop_die_timeout = 5

        self.telemetry_loop_running = False
        self.telemetry_loop_task = None

        self.model.setup("default")

    @staticmethod
    def get_config_pkg():
        return "ts_config_attcs"

    async def configure(self, config):
        """Configure this CSC and output the ``settingsApplied`` event.

        Parameters
        ----------
        config : `types.SimpleNamespace`
            Configuration, as described by ``schema/Environment.yaml``
        """
        self.config = config

    async def begin_start(self, id_data):
        """Begin do_start

        Called before state changes.

        This method call setup on the model, passing the selected setting.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data
        """
        self.model.setup(id_data.settingsToApply)
        # self.evt_settingsApplied.set_put(selectedSettings=id_data.data.settingsToApply)

    async def end_enable(self, id_data):
        """End do_enable

        Called after state changes but before command acknowledged.

        Will call `start` on the model controller and start the telemetry loop.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data
        """
        # self._do_change_state(id_data, "enable", [state.DISABLED], state.ENABLED)

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

    async def begin_disable(self, id_data):
        """Begin do_disable

        Called before state changes.

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

    async def end_disable(self, id_data):
        """Transition to from `State.ENABLED` to `State.DISABLED`.

        After switching from enable to disable, wait for telemetry loop to finish.
        If it takes longer then a timeout to finish, cancel the future.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data
        """
        # await self._do_change_state(id_data, "disable", [state.ENABLED], state.DISABLED)
        await self.wait_loop(self.telemetry_loop_task)

    async def telemetry_loop(self):
        """Telemetry loop coroutine.

        This method should only be running if thecomponent is enabled.
        It will get the weather data from the controller and publish it to SAL.
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
                # On exception, go to FAULT state, log exception and break the loop
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
        """A utility method

        Will wait for a task to die or cancel it and handle the aftermath.

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
            await asyncio.sleep(salobj.base_csc.HEARTBEAT_INTERVAL)

        if timeout:
            loop.cancel()

        try:
            await loop
        except asyncio.CancelledError:
            self.log.info('Loop cancelled...')
        except Exception as e:
            # Something else may have happened.
            # Still disable as this will stop the loop on the target production
            self.log.exception(e)
