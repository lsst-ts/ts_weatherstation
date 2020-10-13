#!/usr/bin/env python

import asyncio

from lsst.ts.environment.csc import CSC

asyncio.run(CSC.amain(index=None))
