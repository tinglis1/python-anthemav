# python-anthemav_x00

[![Build Status](https://travis-ci.org/nugget/python-anthemav.svg?branch=master)](https://travis-ci.org/nugget/python-anthemav)
[![GitHub release](https://img.shields.io/github/release/nugget/python-anthemav.svg)](https://github.com/nugget/python-anthemav/releases)
[![PyPI](https://img.shields.io/pypi/v/anthemav.svg)](https://pypi.python.org/pypi/anthemav)

C:\Users\tingl\AppData\Local\Programs\Python\Python36\python.exe .\example.py -v

This is a Python package to interface with [Anthem](http://www.anthemav.com)
AVM and MRX-x00 receivers and processors.  It uses the asyncio library to maintain
an object-based connection to the network port of the receiver with supporting
methods and properties to poll and adjust the receiver settings.

This package was created primarily to support an anthemav media_player platform
for the [Home Assistant](https://home-assistant.io/) automation platform but it
is structured to be general-purpose and should be usable for other applications
as well.

### Important
This package will maintain a persistant connection to the network control port
which may prevent any other application from communicating with the receiver.
This will depend on the IP to serial interface used. Devices such as the
GlobalCache iTach devices will accept multiple connections.

## Requirements

- Python 3.4 or newer with asyncio
- An Anthem MRX x00 or AVM receiver or processor

## Known Issues

- This has only been tested with an MRXx00 series receiver and a GlobalCache
  iTach Ip2SL adapter.

- Only Zone 1 is currently supported.  If you have other zones configured, this
  library will not allow you to inspect or control them.  This is not an
  intractable problem, I just chose not to address that nuance in this initial
  release.  It's certainly feasible to add support but I am not settled on how
  that should be exposed in the internal API of the package.


## Installation

You can, of course, just install the most recent release of this package using
`pip`.  This will download the more rececnt version from [PyPI] and install it
to your host.

[PyPI]: https://pypi.python.org/pypi/anthemav_x00

    pip install anthemav_x00

If you want to grab the the development code, you can also clone this git
repository and install from local sources:

	cd python-anthemav_x00
    pip install .

And, as you probably expect, you can live the developer's life by working with
the live repo and edit to your heart's content:

    cd python-anthemav_x00
	pip install . -e

## Testing

The package installs a command-line tool which will connect to your receiver,
power it up, and then monitor all activity and changes that take place.  The
code for this console monitor is in `anthemav/tools.py` and you can invoke it
by simply running this at the command line with the appropriate IP and port
number that matches your receiver and its configured port:

    anthemav_monitor --host 10.0.0.100 --port 4999

## Helpful Commands

    sudo tcpflow -c port 4999


## Interesting Links

- [Project Home](https://github.com/tinglis1/python-anthemav_x00)
- [API Documentation for Anthem Network
  Protocol](http://www.anthemav.com/downloads/s)
  (Excel Spreadsheet)
- [Pictures of cats](http://imgur.com/r/cats)

## Credits

- This package was written by David McNett and modified to suit x00 revievers by
  Tim Inglis.
  - https://github.com/nugget
  - https://keybase.io/nugget
  - https://github.com/tinglis1
