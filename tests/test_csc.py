import sys
import unittest
import asyncio
import numpy as np
import logging

from lsst.ts import salobj

from lsst.ts.environment import csc

np.random.seed(50)

BASE_TIMEOUT = 10.

index_gen = salobj.index_generator()

logger = logging.getLogger()
logger.level = logging.DEBUG


class Harness:
    def __init__(self, index, config_dir, initial_simulation_mode):
        salobj.test_utils.set_random_lsst_dds_domain()
        self.csc = csc.CSC(index=index,
                           config_dir=config_dir,
                           initial_simulation_mode=initial_simulation_mode)
        self.remote = salobj.Remote(self.csc.domain,
                                    "Environment",
                                    index)

    async def __aenter__(self):
        await self.csc.start_task
        await self.remote.start_task
        return self

    async def __aexit__(self, *args):
        await self.csc.close()


class TestEnvironmentCSC(unittest.TestCase):

    def test_standard_state_transitions(self):
        """Test standard CSC state transitions.

        The initial state is STANDBY.
        The standard commands and associated state transitions are:

        * enterControl: OFFLINE to STANDBY
        * start: STANDBY to DISABLED
        * enable: DISABLED to ENABLED

        * disable: ENABLED to DISABLED
        * standby: DISABLED to STANDBY
        * exitControl: STANDBY, FAULT to OFFLINE (quit)
        """

        async def doit():

            commands = ("start", "enable", "disable", "exitControl", "standby")
            index = next(index_gen)
            self.assertGreater(index, 0)

            async with Harness(index, None, 1) as harness:

                # Check initial state
                current_state = await harness.remote.evt_summaryState.next(flush=False,
                                                                           timeout=BASE_TIMEOUT)

                self.assertEqual(harness.csc.summary_state, salobj.State.STANDBY)
                self.assertEqual(current_state.summaryState, salobj.State.STANDBY)

                # Check that settingVersions was published
                setting_versions = await harness.remote.evt_settingVersions.next(flush=False,
                                                                                 timeout=BASE_TIMEOUT)
                self.assertIsNotNone(setting_versions)

                for bad_command in commands:
                    if bad_command in ("start", "exitControl"):
                        continue  # valid command in STANDBY state
                    with self.subTest(bad_command=bad_command):
                        cmd_attr = getattr(harness.remote, f"cmd_{bad_command}")
                        with self.assertRaises(salobj.AckError):
                            id_ack = await cmd_attr.start(timeout=BASE_TIMEOUT)

                # send start; new state is DISABLED
                cmd_attr = getattr(harness.remote, f"cmd_start")
                state_coro = harness.remote.evt_summaryState.next(flush=True, timeout=BASE_TIMEOUT)
                id_ack = await cmd_attr.start(timeout=120)  # this one can take longer to execute
                state = await state_coro
                self.assertEqual(id_ack.ack, salobj.SalRetCode.CMD_COMPLETE)
                self.assertEqual(id_ack.error, 0)
                self.assertEqual(harness.csc.summary_state, salobj.State.DISABLED)
                self.assertEqual(state.summaryState, salobj.State.DISABLED)

                for bad_command in commands:
                    if bad_command in ("enable", "standby"):
                        continue  # valid command in DISABLED state
                    with self.subTest(bad_command=bad_command):
                        cmd_attr = getattr(harness.remote, f"cmd_{bad_command}")
                        with self.assertRaises(salobj.AckError):
                            id_ack = await cmd_attr.start(timeout=BASE_TIMEOUT)

                # send enable; new state is ENABLED
                cmd_attr = getattr(harness.remote, f"cmd_enable")
                state_coro = harness.remote.evt_summaryState.next(flush=True, timeout=BASE_TIMEOUT)
                id_ack = await cmd_attr.start(timeout=BASE_TIMEOUT)
                state = await state_coro
                self.assertEqual(id_ack.ack, salobj.SalRetCode.CMD_COMPLETE)
                self.assertEqual(id_ack.error, 0)
                self.assertEqual(harness.csc.summary_state, salobj.State.ENABLED)
                self.assertEqual(state.summaryState, salobj.State.ENABLED)

                for bad_command in commands:
                    if bad_command == "disable":
                        continue  # valid command in ENABLE state
                    with self.subTest(bad_command=bad_command):
                        cmd_attr = getattr(harness.remote, f"cmd_{bad_command}")
                        with self.assertRaises(salobj.AckError):
                            id_ack = await cmd_attr.start(timeout=BASE_TIMEOUT)

                # send disable; new state is DISABLED
                cmd_attr = getattr(harness.remote, f"cmd_disable")
                # this CMD may take some time to complete
                id_ack = await cmd_attr.start(timeout=30.)
                self.assertEqual(id_ack.ack, salobj.SalRetCode.CMD_COMPLETE)
                self.assertEqual(id_ack.error, 0)
                self.assertEqual(harness.csc.summary_state, salobj.State.DISABLED)

        asyncio.get_event_loop().run_until_complete(doit())


if __name__ == '__main__':

    stream_handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(stream_handler)

    unittest.main()
