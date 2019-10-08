import copy
import asyncio
import warnings
import numpy as np
import socket

from astropy.io import ascii

from .base_env import BaseEnv

__all__ = ['LSSTWeatherStation']


def fix_data(val):
    """A Utility function to fix data from the weather station.

    Parameters
    ----------
    val : str
        String data to fix.

    Returns
    -------
    val : float
        Fixed data
    """
    new_val = val.replace(':', '').replace(';', '')
    last_valid = None
    for i in new_val:
        if i not in '0123456789.-+':
            last_valid = new_val.rfind(i)
            break
    try:
        return float(new_val[:last_valid])
    except ValueError:
        return np.nan


async def get_last_item(idict, items):
    """A recursive method to get the last item from a list of items in a nested dictionary.

    For example, consider the following nested dictionary:
    my_dict = {'level1' : {'level2_1': 21, 'level2_2': 22}}

    In : get_last_item(my_dict, ['level1', 'level2_1'])
    Out: 21


    Parameters
    ----------
    idict : dict
        Nested dictionary.
    items : list(str)
        A list of keys, each item represents a level inside the nested dictionary.

    Returns
    -------
    val
        The last item in the nested dictionary

    """
    tmp = list(items)
    await asyncio.sleep(0.)
    if len(items) == 1:
        return idict[items[0]]
    else:
        for item in items:
            tmp.pop(0)
            return await get_last_item(idict[item], tmp)


class LSSTWeatherStation(BaseEnv):
    """Implement controller for the LSST Weather Station."""

    def __init__(self):

        # Parameters for this controller
        self.host = ""
        self.port = 0
        self.buffer_size = 0
        self.timeout = 120.

        self.simulation = False

        self.socket = None
        self.conn = None
        self.reader = None

        self.last_error_message = ""

        self.stream_start = '('
        self.stream_end = ')'

        # Example of the data output
        self.data_str = """SMS 0(S:AWS310_LSST;
D:190204;
T:160503;
UT:1549296303;
STNID:0;
MSGID:141106;
ALT:2500;
LAT:-30.2446;
LON:-70.7494;
WS|VALUE|||1|mps|:0.0;
WD|VALUE|||1|deg|:301;
WS|AVG|PT2M||1|mps|:0.1;
WS|MAX|PT2M||1|mps|:0.2;
WS|MIN|PT2M||1|mps|:0.0;
WS|AVG|PT10M||1|mps|:0.1;
WS|MAX|PT10M||1|mps|:0.2;
WS|MIN|PT10M||1|mps|:0.0;
WGD|VALUE|PT10M||10|deg|:186;
WD|AVG|PT2M||1|deg|:270;
WD|MAX|PT2M||1|deg|:328;
WD|MIN|PT2M||1|deg|:152;
WD|AVG|PT10M||1|deg|:237;
WD|MAX|PT10M||1|deg|:328;
WS|VALUE|||2|mps|:0.0;
WD|VALUE|||2|deg|:138;
WS|AVG|PT2M||2|mps|:0.0;
WS|MAX|PT2M||2|mps|:0.0;
WS|MIN|PT2M||2|mps|:0.0;
WS|AVG|PT10M||2|mps|:0.0;
WS|MAX|PT10M||2|mps|:0.1;
WGD|VALUE|PT10M||20|deg|:0.0;
WD|AVG|PT2M||2|deg|:136;
WD|MAX|PT2M||2|deg|:332;
WD|MIN|PT2M||2|deg|:354;
WD|AVG|PT10M||2|deg|:157;
WD|MAX|PT10M||2|deg|:315;
WD|MAX|PT10M||2|deg|:324;
TA|AVG|PT1M||1|degC|:22.2;
TA|AVG|PT24H||1|degC|:22.0;
TA|MAX|PT24H||1|degC|:24.1;
TA|MIN|PT24H||1|degC|:20.7;
TD|AVG|PT1M||1|degC|:13.8;
RH|AVG|PT1M||1|%|:59;
RH|AVG|PT24H||1|%|:57;
RH|MAX|PT24H||1|%|:59;
RH|MIN|PT24H||1|%|:55;
PA|AVG|PT1M||1|hPa|:1002.4;
QFE|AVG|PT1M||1|hPa|:1002.6;
QFF|AVG|PT1M||1|hPa|:1337.7;
QNH|AVG|PT1M||1|hPa|:1338.4;
PATR|VALUE|PT3H||1|hPa|:-0.8;
PATE|VALUE|PT3H||1|hPa|:8;
PR|SUM|PT1M||1|mm|:0.00;
PR|SUM|PT1H||1|mm|:0.00;
PRF|SUM|PT1M||1|mm/h|:0.00;
TA|AVG|PT1M||2|degC|:22.1;
TA|AVG|PT24H||2|degC|:21.6;
TA|MAX|PT24H||2|degC|:23.2;
TA|MIN|PT24H||2|degC|:20.3;
TD|AVG|PT1M||2|degC|:13.7;
RH|AVG|PT1M||2|%|:59;
RH|AVG|PT24H||2|%|:59;
RH|MAX|PT24H||2|%|:59;
RH|MIN|PT24H||2|%|:58;
PA|AVG|PT1M||2|hPa|:1002.3;
QFE|AVG|PT1M||2|hPa|:1002.5;
QFF|AVG|PT1M||2|hPa|:1337.8;
QNH|AVG|PT1M||2|hPa|:1338.3;
PATR|VALUE|PT3H||2|hPa|:-0.8;
PATE|VALUE|PT3H||2|hPa|:8;
TS|AVG|PT1M||1|degC|:22.5;
TS|AVG|PT24H||1|degC|:22.3;
TS|MAX|PT24H||1|degC|:22.5;
TS|MIN|PT24H||1|degC|:22.1;
SRN|AVG|PT1M||1|Wpm2|:-8;
SRN|AVG|PT24H||1|Wpm2|:-2;
SRN|MAX|PT24H||1|Wpm2|:3;
SRN|MIN|PT24H||1|Wpm2|:-8;
SNH|AVG|PT1M||1|cm|:11874.2;
SNH|AVG|PT24H||1|cm|:11874.9;
SNH|MAX|PT24H||1|cm|:11876.8;
SNH|MIN|PT24H||1|cm|:11873.7)D621
"""

        # The structure of the data
        self.data_structure = {
            "PA": {
                "AVG": {
                    "PT1M": {
                        1: {},
                        2: {},
                    },
                },
            },
            "PATE": {
                "VALUE": {
                    1: {},
                    2: {},
                },
            },
            "PATR": {
                "VALUE": {
                    1: {},
                    2: {},
                },
            },
            "PR": {
                "SUM": {
                    "PT1H": {
                        1: {},
                    },
                    "PT1M": {
                        1: {},
                    },
                },
            },
            "PRF": {
                "SUM": {
                    "PT1M": {
                        1: {},
                    },
                },
            },
            "QFE": {
                "AVG": {
                    "PT1M": {
                        1: {},
                        2: {},
                    },
                },
            },
            "QFF": {
                "AVG": {
                    "PT1M": {
                        1: {},
                        2: {},
                    },
                },
            },
            "QNH": {
                "AVG": {
                    "PT1M": {
                        1: {},
                        2: {},
                    },
                },
            },
            "RH": {
                "AVG": {
                    "PT1M": {
                        1: {},
                        2: {},
                    },
                    "PT24H": {
                        1: {},
                        2: {},
                    },
                },
                "MAX": {
                    "PT24H": {
                        1: {},
                        2: {},
                    },
                },
                "MIN": {
                    "PT24H": {
                        1: {},
                        2: {},
                    },
                },
            },
            "SNH": {
                "AVG": {
                    "PT1M": {
                        1: {},
                    },
                    "PT24H": {
                        1: {},
                    },
                },
                "MAX": {
                    "PT24H": {
                        1: {},
                    },
                },
                "MIN": {
                    "PT24H": {
                        1: {},
                    },
                },
            },
            "SRN": {
                "AVG": {
                    "PT1M": {
                        1: {},
                    },
                    "PT24H": {
                        1: {},
                    },
                },
                "MAX": {
                    "PT24H": {
                        1: {},
                    },
                },
                "MIN": {
                    "PT24H": {
                        1: {},
                    },
                },
            },
            "TA": {
                "AVG": {
                    "PT1M": {
                        1: {},
                        2: {},
                    },
                    "PT24H": {
                        1: {},
                        2: {},
                    },
                },
                "MAX": {
                    "PT24H": {
                        1: {},
                        2: {},
                    },
                },
                "MIN": {
                    "PT24H": {
                        1: {},
                        2: {},
                    },
                },
            },
            "TD": {
                "AVG": {
                    "PT1M": {
                        1: {},
                        2: {},
                    },
                },
            },
            "TS": {
                "AVG": {
                    "PT1M": {
                        1: {},
                    },
                    "PT24H": {
                        1: {},
                    },
                },
                "MAX": {
                    "PT24H": {
                        1: {},
                    },
                },
                "MIN": {
                    "PT24H": {
                        1: {},
                    },
                },
            },
            "WD": {
                "AVG": {
                    "PT10M": {
                        1: {},
                        2: {},
                    },
                    "PT2M": {
                        1: {},
                        2: {},
                    },
                },
                "MAX": {
                    "PT10M": {
                        1: {},
                        2: {},
                        3: {},
                    },
                    "PT2M": {
                        1: {},
                        2: {},
                    },
                },
                "MIN": {
                    "PT2M": {
                        1: {},
                        2: {},
                    },
                },
                "VALUE": {
                    1: {},
                    2: {},
                },
            },
            "WGD": {
                "VALUE": {
                    1: {},
                    2: {},
                },
            },
            "WS": {
                "AVG": {
                    "PT10M": {
                        1: {},
                        2: {},
                    },
                    "PT2M": {
                        1: {},
                        2: {},
                    },
                },
                "MAX": {
                    "PT10M": {
                        1: {},
                        2: {},
                    },
                    "PT2M": {
                        1: {},
                        2: {},
                    },
                },
                "MIN": {
                    "PT10M": {
                        1: {},
                    },
                    "PT2M": {
                        1: {},
                        2: {},
                    },
                },
                "VALUE": {
                    1: {},
                    2: {},
                },
            },
        }

        # Map between data and topics
        self.data_mapping = {
            "weather": {"ambient_temp": ("TA", "AVG", "PT1M"),
                        "humidity": ("RH", "AVG", "PT1M"),
                        "pressure": ("PA", "AVG", "PT1M")},
            "windDirection": {"value": ("WD", "VALUE"),
                              "avg2M": ("WD", "AVG", "PT2M"),
                              "max2M": ("WD", "MAX", "PT2M"),
                              "min2M": ("WD", "MIN", "PT2M"),
                              "avg10M": ("WD", "AVG", "PT10M"),
                              "max10M": ("WD", "MAX", "PT10M"),
                              "sensorName": (),
                              },
            "windGustDirection": {"value10M": ("WGD", "VALUE"),
                                  "sensorName": (),
                                  },
            "windSpeed": {"value": ("WS", "VALUE"),
                          "avg2M": ("WS", "AVG", "PT2M"),
                          "max2M": ("WS", "MAX", "PT2M"),
                          "min2M": ("WS", "MIN", "PT2M"),
                          "avg10M": ("WS", "AVG", "PT10M"),
                          "max10M": ("WS", "MAX", "PT10M"),
                          "sensorName": (),
                          },
            "airTemperature": {"avg24H": ("TA", "AVG", "PT24H"),
                               "avg1M": ("TA", "AVG", "PT1M"),
                               "max24H": ("TA", "MAX", "PT24H"),
                               "min24H": ("TA", "MIN", "PT24H"),
                               "sensorName": (),
                               },
            "relativeHumidity": {"avg24H": ("RH", "AVG", "PT24H"),
                                 "avg1M": ("RH", "AVG", "PT1M"),
                                 "max24H": ("RH", "MAX", "PT24H"),
                                 "min24H": ("RH", "MIN", "PT24H"),
                                 "sensorName": (),
                                 },
            "dewPoint": {"avg1M": ("TD", "AVG", "PT1M"),
                         "sensorName": (),
                         },
            "snowDepth": {"avg1M": ("SNH", "AVG", "PT1M"),
                          "max24H": ("SNH", "MAX", "PT24H"),
                          "min24H": ("SNH", "MIN", "PT24H"),
                          "avg24H": ("SNH", "AVG", "PT24H"),
                          "sensorName": (),
                          },
            "solarNetRadiation": {"avg1M": ("SRN", "AVG", "PT1M"),
                                  "max24H": ("SRN", "MAX", "PT24H"),
                                  "min24H": ("SRN", "MIN", "PT24H"),
                                  "avg24H": ("SRN", "AVG", "PT24H"),
                                  "sensorName": (),
                                  },
            "airPressure": {"paAvg1M": ("PA", "AVG", "PT1M"),
                            "patrValue3H": ("PATR", "VALUE"),
                            "pateValue3H": ("PATE", "VALUE"),
                            "sensorName": (),
                            },
            "precipitation": {"prSum1M": ("PR", "SUM", "PT1M"),
                              "prSum1H": ("PR", "SUM", "PT1H"),
                              "prfSum1M": ("PRF", "SUM", "PT1M"),
                              "sensorName": (),
                              },
            "soilTemperature": {"avg24H": ("TS", "AVG", "PT24H"),
                                "avg1M": ("TS", "AVG", "PT1M"),
                                "max24H": ("TS", "MAX", "PT24H"),
                                "min24H": ("TS", "MIN", "PT24H"),
                                "sensorName": (),
                                },
        }

    def setup(self, config, simulation=False):
        """Base weather station setup method.

        When subclassing avoid using argv.

        Parameters
        ----------
        config : `Namespace`
            Namespace with the configuration parameters. The namespace
            should have the following properties.

            config.host : `str`
                IP or address of the host.
            config.port : `int`
                Port on the host controller
            config.buffer_size : `int`
                Published buffer size.
            config.timeout : `float`
                Timeout waiting for new data from the controller.
        simulation : `bool`
            Run in simulation mode (default=False).

        """
        self.host = config.host
        self.port = config.port
        self.buffer_size = config.buffer_size
        self.timeout = config.timeout
        self.simulation = simulation

    def unset(self):
        """Unset weather station."""
        pass

    async def start(self):
        """Start weather station."""
        if not self.simulation:
            self.socket = socket.socket(socket.AF_INET,
                                        socket.SOCK_STREAM)
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)

            self.conn, _ = self.socket.accept()
            self.reader, _ = await asyncio.open_connection(sock=self.conn)

    def stop(self):
        """Stop Weather Station."""
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            finally:
                self.conn = None

        if self.socket is not None:
            try:
                self.socket.close()
            except Exception:
                pass
            finally:
                self.socket = None

    async def parse_data(self, data_str):
        """A utility method to get a data string from the weather station and parse its content into
        `self.data_structure`. It uses `astropy.io.ascii` to parse the input string into a table and
        then loop through the data structure filling it out.

        Parameters
        ----------
        data_str : str
            A string containing the data from the weather station. Its format must match the internal
            definition, that can be found at `self.data_str`.

        """

        # Read the header information, that contains date, time and other useful information.
        # header = ascii.read(data_str, data_start=1, data_end=8, delimiter=':')
        # Read the data into a table
        try:
            data = ascii.read(data_str, data_start=9)
        except Exception as e:
            self.last_error_message = data_str
            raise e

        await asyncio.sleep(0.)  # give control back to event loop

        for col1 in self.data_structure:
            for col2 in self.data_structure[col1]:
                if col2 == "VALUE":
                    mask = np.where(np.bitwise_and(data['col1'] == col1,
                                                   data['col2'] == col2))
                    await asyncio.sleep(0.)  # give control back to event loop
                    data_table = data[mask]
                    if len(data_table) < len(self.data_structure[col1][col2]):
                        raise RuntimeError(f"Size of data_table[{len(data_table)}] incompatible with "
                                           f"data_structure[{len(self.data_structure[col1][col2])}] "
                                           f"for {col1}, {col2}")
                    elif len(data_table) != len(self.data_structure[col1][col2]):
                        warnings.warn(f"Size of data_table[{len(data_table)}] incompatible with "
                                      f"data_structure[{len(self.data_structure[col1][col2])}] "
                                      f"for {col1}, {col2}")
                    i = 0
                    for sensor in self.data_structure[col1][col2]:
                        self.data_structure[col1][col2][sensor] = data_table['col7'][i]
                        i += 1
                    await asyncio.sleep(0.)  # give control back to event loop
                else:
                    for col3 in self.data_structure[col1][col2]:
                        mask = np.where(np.bitwise_and(data['col3'] == col3,
                                                       np.bitwise_and(data['col1'] == col1,
                                                                      data['col2'] == col2)))
                        await asyncio.sleep(0.)  # give control back to event loop
                        data_table = data[mask]
                        i = 0
                        for sensor in self.data_structure[col1][col2][col3]:
                            self.data_structure[col1][col2][col3][sensor] = data_table['col7'][i]
                            i += 1
                        await asyncio.sleep(0.)  # give control back to event loop

                await asyncio.sleep(0.)  # give control back to event loop

            await asyncio.sleep(0.)  # give control back to event loop

    async def get_topic_dict(self):
        """Parse the data from `self.data_structure` into a dictionary with `self.data_mapping` structure.

        Returns
        -------
        topic_dict : dict
            A dictionary with the same structure of `self.data_mapping` but filled with the data from
            `self.data_structure`.

        """
        topic_dict = copy.deepcopy(self.data_mapping)

        for topic in self.data_mapping:
            for data_list in self.data_mapping[topic]:
                if len(self.data_mapping[topic][data_list]) == 0:
                    topic_dict[topic][data_list] = ''
                    # Skipp data_list if not defined
                    continue
                else:
                    try:
                        data = await get_last_item(self.data_structure,
                                                   self.data_mapping[topic][data_list])
                        data = np.array([fix_data(d) for d in data.values()])
                        data = data[data != -99.]
                        if len(data) > 1:
                            topic_dict[topic][data_list] = np.mean(data)
                        elif len(data) == 1:
                            topic_dict[topic][data_list] = data[0]
                        else:
                            topic_dict[topic][data_list] = -99.
                    except KeyError:
                        raise KeyError(f'{topic},{data_list}: {self.data_mapping[topic][data_list]}')
        return topic_dict

    async def read_data_from_socket(self):
        """A Utility function to read data from the socket.

        Returns
        -------
        data : str
            A string with the data received from the socket.
        """

        data = ""

        stream_started = False

        i = 0
        while True:

            char = await self.reader.read(1)
            char = char.decode()
            i += 1

            if not char:
                break
            elif char == self.stream_start:
                stream_started = True
                continue
            elif char == self.stream_end:
                # stream ended
                break
            elif stream_started:
                if char == '\n':
                    continue
                data += char
                if char == ';':
                    data += '\n'

            self.last_error_message = data

        return data

    async def get_data(self):
        """Coroutine to wait and return new seeing measurements.

        Returns
        -------
        measurement : dict
            A dictionary with the same values of the dimmMeasurement topic SAL Event.
        """
        if self.simulation:
            # Running in simulation, use the internal data string
            await self.parse_data(self.data_str)
        else:
            data = await asyncio.wait_for(self.read_data_from_socket(),
                                          timeout=self.timeout)
            self.last_error_message = ""
            await self.parse_data(data)

        return await self.get_topic_dict()

    def error_report(self):
        """Return error report from the controller.

        Returns
        -------
        report : `str`
            String with information about last error.
        """
        return self.last_error_message

    def reset_error(self):
        """Reset error report.
        """
        self.last_error_message = ""
