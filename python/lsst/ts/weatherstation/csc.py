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

import asyncio
import traceback

from .config_schema import CONFIG_SCHEMA
from . import __version__
from lsst.ts.salobj import base_csc, ConfigurableCsc, State

from .model import Model

__all__ = ["CSC"]


TELEMETRY_LOOP_ERROR = 7801
"""Error in the telemetry loop (`int`).

This error code is published in
`WeatherStation_logevent_errorCodeC` if there is an error in
the telemetry loop.
"""
CONTROLLER_START_ERROR = 7802
"""Error starting the model controller (`int`)

this error code is published in
`WeatherStation_logevent_errorCodeC` if there is an error
calling `self.model.controller.start()`.
"""
CONTROLLER_STOP_ERROR = 7803
"""Error stopping the model controller (`int`)

this error code is published in
`WeatherStation_logevent_errorCodeC` if there is an error
calling `self.model.controller.stop()`.
"""


class CSC(ConfigurableCsc):
    """Commandable SAL Component (CSC) for the WeatherStation monitoring
    system.
    """

    valid_simulation_modes = (0, 1)
    version = __version__

    def __init__(
        self,
        index,
        config_dir=None,
        initial_state=State.STANDBY,
        simulation_mode=0,
    ):
        """
        Initialize CSC.
        """

        self.model = Model()

        super().__init__(
            "WeatherStation",
            index=index,
            config_schema=CONFIG_SCHEMA,
            config_dir=config_dir,
            initial_state=initial_state,
            simulation_mode=simulation_mode,
        )

        self.loop_die_timeout = 5  # how long to wait for the loops to die?

        self.telemetry_loop_running = False
        self.telemetry_loop_task = None

    async def begin_enable(self, id_data):
        """Begin do_enable; called before state changes.

        This method will send a CMD_INPROGRESS signal.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data

        """
        await super().begin_enable(id_data)
        await self.cmd_enable.ack_in_progress(id_data, timeout=60)

    async def end_enable(self, id_data):
        """End do_enable; called after state changes
        but before command acknowledged.

        This method will call `start` on the model controller and start the
        telemetry loop.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data
        """
        try:
            await self.model.controller.start()
        except Exception:
            error_msg = "Error starting model controller."
            self.log.exception(error_msg)
            await self.fault(
                code=CONTROLLER_START_ERROR,
                report=error_msg,
                traceback=traceback.format_exc(),
            )
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
        except Exception:
            error_msg = "Error stopping model controller."
            self.log.exception(error_msg)
            await self.fault(
                code=CONTROLLER_STOP_ERROR,
                report=error_msg,
                traceback=traceback.format_exc(),
            )

        await super().begin_disable(id_data)
        await self.cmd_enable.ack_in_progress(id_data, timeout=60)

    async def end_disable(self, id_data):
        """After switching from enable to disable, wait for telemetry loop to
        finish. If it takes longer then a timeout to finish, cancel the future.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data
        """
        await self.wait_loop(self.telemetry_loop_task)

        await super().end_disable(id_data)

    async def fault(self, code=None, report="", traceback=""):
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
        traceback : `str`, optional
            Description of the traceback, if any.
        """

        # Stop the controller.
        try:
            self.model.controller.stop()
        except Exception as e:
            self.log.error("Exception trying to stop model controller.")
            self.log.exception(e)
        self.model.controller.reset_error()
        await super().fault(code=code, report=report, traceback=traceback)

    @staticmethod
    def get_config_pkg():
        return "ts_config_ocs"

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
        for instance in config.instances:
            if instance["sal_index"] == self.salinfo.index:
                break
        else:
            raise RuntimeError(f"No config found for sal_index={self.salinfo.index}")
        self.model.setup(instance, simulation_mode=self.simulation_mode)

    async def telemetry_loop(self):
        """Telemetry loop coroutine. This method should only be running if the
        component is enabled. It will get
        the weather data from the controller and publish it to SAL.

        """
        if self.telemetry_loop_running:
            raise RuntimeError("Telemetry loop still running...")
        self.telemetry_loop_running = True

        try:
            while self.telemetry_loop_running:
                self.log.debug("Getting data...")
                weather_data = await self.model.get_weatherstation_data()

                if weather_data is None:
                    self.log.warning("No data from controller.")
                    self.log.error(f"{self.model.controller.error_report()!r}")
                else:
                    self.log.debug(f"Got {weather_data}")
                    for topic_name in weather_data:
                        telemetry = getattr(self, f"tel_{topic_name}", None)
                        if telemetry is not None:
                            await telemetry.set_write(**weather_data[topic_name])
        except Exception:
            # If there is an exception go to FAULT state, log the exception and
            # break the loop
            error_msg = "Error in the telemetry loop."
            self.log.exception(error_msg)
            await self.fault(
                code=TELEMETRY_LOOP_ERROR,
                report=error_msg,
                traceback=traceback.format_exc(),
            )
        finally:
            self.telemetry_loop_running = False

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
            self.log.info("Loop cancelled...")
        except Exception as e:
            # Something else may have happened. I still want to disable as this
            # will stop the loop on the target production
            self.log.exception(e)
