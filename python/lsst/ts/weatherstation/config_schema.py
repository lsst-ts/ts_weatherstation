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

__all__ = ["CONFIG_SCHEMA"]

import yaml

CONFIG_SCHEMA = yaml.safe_load(
    """
  $schema: http://json-schema.org/draft-07/schema#
  $id: https://github.com/lsst-ts/ts_weatherstation/blob/main/python/lsst/ts/weatherstation/config_schema.py  # noqa
  title: WeatherStation v2
  description: Schema for the WeatherStation CSC configuration files
  type: object
  properties:
    instances:
      type: array
      description: Configuration for each WeatherStation instance.
      minItem: 1
      items:
        type: object
        properties:
          sal_index:
            type: integer
            description: SAL index of WeatherStation instance.
            minimum: 1
          ws_type:
            description: Type of WeatherStation model.
            type: string
            enum:
            - lsst
          config:
            description: Configuration for the WeatherStation model.
            type: object
    """
)
