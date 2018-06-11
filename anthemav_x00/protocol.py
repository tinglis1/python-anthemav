"""Module to maintain AVR state information and network interface."""
import asyncio
import logging
import time

__all__ = ('AVR')

# In Python 3.4.4, `async` was renamed to `ensure_future`.
try:
    ensure_future = asyncio.ensure_future
except AttributeError:
    ensure_future = asyncio.async

# These properties apply even when the AVR is powered off
ATTR_CORE = {'P1P'}

LOOKUP = {}

LOOKUP['P1P'] = {'description': 'Zone 1 Power',
                   '0': 'Off', '1': 'On'}
LOOKUP['P1VM'] = {'description': 'Zone 1 Volume'}

LOOKUP['P1S'] = {'description': 'Zone 1 current input',
                   '1': 'BDP', '2': 'CD', '3': 'TV', '4': 'SAT', '5': 'GAME',
                   '6': 'AUX', '7': 'MEDIA', '8': 'TV', '9': 'SAT', 'd': 'USB',
                   'e': 'Internet Radio' }
LOOKUP['P1M'] = {'description': 'Zone 1 mute',
                   '0': 'Unmuted', '1': 'Muted'}



# pylint: disable=too-many-instance-attributes, too-many-public-methods
class AVR(asyncio.Protocol):
    """The Anthem AVR IP control protocol handler."""

    def __init__(self, update_callback=None, loop=None, connection_lost_callback=None):
        """Protocol handler that handles all status and changes on AVR.

        This class is expected to be wrapped inside a Connection class object
        which will maintain the socket and handle auto-reconnects.

            :param update_callback:
                called if any state information changes in device (optional)
            :param connection_lost_callback:
                called when connection is lost to device (optional)
            :param loop:
                asyncio event loop (optional)

            :type update_callback:
                callable
            :type: connection_lost_callback:
                callable
            :type loop:
                asyncio.loop
        """
        self._loop = loop
        self.log = logging.getLogger(__name__)
        self._connection_lost_callback = connection_lost_callback
        self._update_callback = update_callback
        self.buffer = ''
        self._input_names = {}
        self._input_numbers = {}
        self._poweron_refresh_successful = False
        self.transport = None

        for key in LOOKUP:
            setattr(self, '_'+key, '')

        self._P1P = '0'
        self.refresh_all()

    def refresh_core(self):
        """Query device for all attributes that exist regardless of power state.

        This will force a refresh for all device queries that are valid to
        request at any time.  It's the only safe suite of queries that we can
        make if we do not know the current state (on or off+standby).

        This does not return any data, it just issues the queries.
        """
        self.log.info('Sending out mass query for all attributes')
        for key in ATTR_CORE:
            self.query(key)

    def poweron_refresh(self):
        """Keep requesting all attributes until it works.

        Immediately after a power on event (POW1) the AVR is inconsistent with
        which attributes can be successfully queried.  When we detect that
        power has just been turned on, we loop every second making a bulk
        query for every known attribute.  This continues until we detect that
        values have been returned for at least one input name (this seems to
        be the laggiest of all the attributes)
        """
        if self._poweron_refresh_successful:
            return
        else:
            self.refresh_all()
            self._loop.call_later(2, self.poweron_refresh)


    def refresh_all(self):
        """Query device for all attributes that are known.

        This will force a refresh for all device queries that the module is
        aware of.  In theory, this will completely populate the internal state
        table for all attributes.

        This does not return any data, it just issues the queries.
        """
        self.log.info('refresh_all')
        for key in LOOKUP:
            self.query(key)


    #
    # asyncio network functions
    #

    def connection_made(self, transport):
        """Called when asyncio.Protocol establishes the network connection."""
        self.log.info('Connection established to AVR')
        self.transport = transport

        #self.transport.set_write_buffer_limits(0)
        limit_low, limit_high = self.transport.get_write_buffer_limits()
        self.log.debug('Write buffer limits %d to %d', limit_low, limit_high)

        # self.command('ECH1')
        self.refresh_core()

    def data_received(self, data):
        """Called when asyncio.Protocol detects received data from network."""
        self.buffer += data.decode()
        self.log.debug('Received %d bytes from AVR: %s', len(self.buffer), self.buffer)
        self._assemble_buffer()

    def connection_lost(self, exc):
        """Called when asyncio.Protocol loses the network connection."""
        if exc is None:
            self.log.warning('eof from receiver?')
        else:
            self.log.warning('Lost connection to receiver: %s', exc)

        self.transport = None

        if self._connection_lost_callback:
            self._loop.call_soon(self._connection_lost_callback)

    def _assemble_buffer(self):
        """Split up received data from device into individual commands.

        Data sent by the device is a sequence of datagrams separated by
        semicolons.  It's common to receive a burst of them all in one
        submission when there's a lot of device activity.  This function
        disassembles the chain of datagrams into individual messages which
        are then passed on for interpretation.
        """
        self.transport.pause_reading()

        for message in self.buffer.split(';'):
            if message != '':
                self.log.debug('assembled message '+message)
                self._parse_message(message)

        self.buffer = ""

        self.transport.resume_reading()
        return

    # def _populate_inputs(self, total):
    #     """Request the names for all active, configured inputs on the device.
    #
    #     Once we learn how many inputs are configured, this function is called
    #     which will ask for the name of each active input.
    #     """
    #     total = total + 1
    #     for input_number in range(1, total):
    #         self.query('ISN'+str(input_number).zfill(2))

    def _parse_message(self, data):
        """Interpret each message datagram from device and do the needful.

        This function receives datagrams from _assemble_buffer and inerprets
        what they mean.  It's responsible for maintaining the internal state
        table for each device attribute and also for firing the update_callback
        function (if one was supplied)
        """
        recognized = False
        newdata = False

        if data.startswith('Invalid Command'):
            self.log.warning('Invalid command: %s', data[2:])
            recognized = True
        elif data.startswith('Parameter Out-of-range'):
            self.log.warning('Out-of-range command: %s', data[2:])
            recognized = True
        # elif data.startswith('!E'):
        #     self.log.warning('Cannot execute recognized command: %s', data[2:])
        #     recognized = True
        elif data.startswith('Main Off'):
            self.log.warning('Ignoring command for powered-off zone: %s', data[2:])
            recognized = True

            value = 0
            oldvalue = getattr(self, '_')
            if oldvalue != value:
                changeindicator = 'New Value'
                newdata = True
            else:
                changeindicator = 'Unchanged'

            self.log.info('%s: %s (%s) -> %s (%s)',
                          changeindicator,
                          LOOKUP['P1P']['description'], key,
                          LOOKUP['P1P'][value], value)


        elif data.startswith('Zone2 Off'):
            self.log.warning('Ignoring command for powered-off zone: %s', data[2:])
            recognized = True
        # elif data.startswith('Unit Off'):
        #     self.log.warning('Ignoring command for powered-off zone: %s', data[2:])
        #     recognized = True
        else:

            for key in LOOKUP:
                if data.startswith(key):
                    recognized = True

                    value = data[len(key):]
                    oldvalue = getattr(self, '_'+key)
                    if oldvalue != value:
                        changeindicator = 'New Value'
                        newdata = True
                    else:
                        changeindicator = 'Unchanged'

                    if key in LOOKUP:
                        if 'description' in LOOKUP[key]:
                            if value in LOOKUP[key]:
                                self.log.info('%s: %s (%s) -> %s (%s)',
                                              changeindicator,
                                              LOOKUP[key]['description'], key,
                                              LOOKUP[key][value], value)
                            else:
                                self.log.info('%s: %s (%s) -> %s',
                                              changeindicator,
                                              LOOKUP[key]['description'], key,
                                              value)
                    else:
                        self.log.info('%s: %s -> %s', changeindicator, key, value)

                    setattr(self, '_'+key, value)

                    if key == 'P1P' and value == '1' and oldvalue == '0':
                        self.log.info('Power on detected, refreshing all attributes')
                        self._poweron_refresh_successful = False
                        self._loop.call_later(1, self.poweron_refresh)

                    if key == 'P1P' and value == '0' and oldvalue == '1':
                        self._poweron_refresh_successful = False

                    break

        # if data.startswith('ICN'):
        #     self.log.warning('ICN update received')
        #     recognized = True
        #     self._populate_inputs(int(value))

        # if data.startswith('ISN'):
        #     recognized = True
        #     self._poweron_refresh_successful = True
        #
        #     input_number = int(data[3:5])
        #     value = data[5:]
        #
        #     oldname = self._input_names.get(input_number, '')
        #
        #     if oldname != value:
        #         self._input_numbers[value] = input_number
        #         self._input_names[input_number] = value
        #         self.log.info('New Value: Input %d is called %s', input_number, value)
        #         newdata = True

        if newdata:
            if self._update_callback:
                self._loop.call_soon(self._update_callback, data)
        else:
            self.log.debug('no new data encountered')

        if not recognized:
            self.log.warning('Unrecognized response: %s', data)

    def query(self, item):
        """Issue a raw query to the device for an item.

        This function is used to request that the device supply the current
        state for a data item as described in the Anthem IP protocoal API.
        Normal interaction with this module will not require you to make raw
        device queries with this function, but the method is exposed in case
        there's a need that's not otherwise met by the abstraction methods
        defined elsewhere.

        This function does not return the result, it merely issues the request.

            :param item: Any of the data items from the API
            :type item: str

        :Example:

        >>> query('P1V')

        """
        if item == 'P1VM':
            item = 'P1V?'
        else:
            item = item+'?'

        self.command(item)

    def command(self, command):
        """Issue a raw command to the device.

        This function is used to update a data item on the device.  It's used
        to cause activity or change the configuration of the AVR.  Normal
        interaction with this module will not require you to make raw device
        queries with this function, but the method is exposed in case there's a
        need that's not otherwise met by the abstraction methods defined
        elsewhere.

            :param command: Any command as documented in the Anthem API
            :type command: str

        :Example:

        >>> command('P1V-50')
        """
        command = command+';'
        self.formatted_command(command)

    def formatted_command(self, command):
        """Issue a raw, formatted command to the device.

        This function is invoked by both query and command and is the point
        where we actually send bytes out over the network.  This function does
        the wrapping and formatting required by the Anthem API so that the
        higher-level function can just operate with regular strings without
        the burden of byte encoding and terminating device requests.

            :param command: Any command as documented in the Anthem API
            :type command: str

        :Example:

        >>> formatted_command('P1V-50')
        """
        command = command
        command = command.encode()

        self.log.debug('> %s', command)
        try:
            self.transport.write(command)
            time.sleep(0.01)
        except:
            self.log.warning('No transport found, unable to send command')

    #
    # Volume and Attenuation handlers.  The Anthem tracks volume internally as
    # an attenuation level ranging from -90dB (silent) to 0dB (bleeding ears)
    #
    # We expose this in three methods for the convenience of downstream apps
    # which will almost certainly be doing things their own way:
    #
    #   - attenuation (-90 to 0)
    #   - volume (0-100)
    #   - volume_as_percentage (0-1 floating point)
    #

    def attenuation_to_volume(self, value):
        """Convert a native attenuation value to a volume value.

        Takes an attenuation in dB from the Anthem (-90 to 0) and converts it
        into a normal volume value (0-100).

            :param arg1: attenuation in dB (negative integer from -90 to 0)
            :type arg1: int

        returns an integer value representing volume
        """
        try:
            return round((90.00 + int(value)) / 90 * 100)
        except ValueError:
            return 0

    def volume_to_attenuation(self, value):
        """Convert a volume value to a native attenuation value.

        Takes a volume value and turns it into an attenuation value suitable
        to send to the Anthem AVR.

            :param arg1: volume (integer from 0 to 100)
            :type arg1: int

        returns a negative integer value representing attenuation in dB
        """
        try:
            return round((value / 100) * 90) - 90
        except ValueError:
            return -90

    @property
    def attenuation(self):
        """Current volume attenuation in dB (read/write).

        You can get or set the current attenuation value on the device with this
        property.  Valid range from -90 to 0.

        :Examples:

        >>> attvalue = attenuation
        >>> attenuation = -50
        """
        try:
            return int(self._P1VM)
        except ValueError:
            return -90
        except NameError:
            return -90

    @attenuation.setter
    def attenuation(self, value):
        if isinstance(value, int) and -90 <= value <= 0:
            self.log.debug('Setting attenuation to '+str(value))
            self.command('P1V'+str(value))

    @property
    def volume(self):
        """Current volume level (read/write).

        You can get or set the current volume value on the device with this
        property.  Valid range from 0 to 100.

        :Examples:

        >>> volvalue = volume
        >>> volume = 20
        """
        return self.attenuation_to_volume(self.attenuation)

    @volume.setter
    def volume(self, value):
        if isinstance(value, int) and 0 <= value <= 100:
            self.attenuation = self.volume_to_attenuation(value)

    @property
    def volume_as_percentage(self):
        """Current volume as percentage (read/write).

        You can get or set the current volume value as a percentage.  Valid
        range from 0 to 1 (float).

        :Examples:

        >>> volper = volume_as_percentage
        >>> volume_as_percentage = 0.20
        """
        volume_per = self.volume / 100
        return volume_per

    @volume_as_percentage.setter
    def volume_as_percentage(self, value):
        if isinstance(value, float) or isinstance(value, int):
            if 0 <= value <= 1:
                value = round(value * 100)
                self.volume = value

    #
    # Internal assistant functions for unified handling of boolean
    # properties that are read/write
    #

    def _get_boolean(self, key):
        keyname = '_'+key
        try:
            value = getattr(self, keyname)
            return bool(int(value))
        except ValueError:
            return False
        except AttributeError:
            return False

    def _set_boolean(self, key, value):
        if value is True:
            self.command(key+'1')
        else:
            self.command(key+'0')

    #
    # Boolean properties and corresponding setters
    #

    @property
    def power(self):
        """Report if device powered on or off (read/write).

        Returns and expects a boolean value.
        """
        return self._get_boolean('P1P')

    @power.setter
    def power(self, value):
        self._set_boolean('P1P', value)
        self._set_boolean('P1P', value)

    #
    # @property
    # def arc(self):
    #     """Current ARC (Anthem Room Correction) on or off (read/write)."""
    #     return self._get_boolean('Z1ARC')
    #
    # @arc.setter
    # def arc(self, value):
    #     self._set_boolean('Z1ARC', value)

    @property
    def mute(self):
        """Mute on or off (read/write)."""
        return self._get_boolean('P1M')

    @mute.setter
    def mute(self, value):
        self._set_boolean('P1M', value)


    #
    # Read-only raw numeric properties
    #

    def _get_integer(self, key):
        keyname = '_'+key
        if hasattr(self, keyname):
            value = getattr(self, keyname)
        try:
            return int(value)
        except ValueError:
            return


    #
    # Helper functions for working with raw/text multi-property items
    #
    #
    # def _get_multiprop(self, key, mode='raw'):
    #     keyname = '_'+key
    #
    #     if hasattr(self, keyname):
    #         rawvalue = getattr(self, keyname)
    #         value = rawvalue
    #
    #         if key in LOOKUP:
    #             if rawvalue in LOOKUP[key]:
    #                 value = LOOKUP[key][rawvalue]
    #
    #         if mode == 'raw':
    #             return rawvalue
    #         else:
    #             return value
    #     else:
    #         return

    #
    # Read/write properties with raw and text options
    #
    #

    #
    # Input number and lists
    #

    @property
    def input_list(self):
        """List of all enabled inputs."""
        return list(self._input_numbers.keys())

    @property
    def input_name(self):
        """Name of currently active input (read-write)."""
        return self._input_names.get(self.input_number, "Unknown")

    @input_name.setter
    def input_name(self, value):
        number = self._input_numbers.get(value, 0)
        if number > 0:
            self.input_number = number

    @property
    def input_number(self):
        """Number of currently active input (read-write)."""
        return self._get_integer('P1S')

    @input_number.setter
    def input_number(self, number):
        if isinstance(number, int):
            if 1 <= number <= 99:
                self.log.info('Switching input to '+str(number))
                self.command('P1S'+str(number))

    #
    # Miscellany
    #

    @property
    def dump_rawdata(self):
        """Return contents of transport object for debugging forensics."""
        if hasattr(self, 'transport'):
            attrs = vars(self.transport)
            return ', '.join("%s: %s" % item for item in attrs.items())

    @property
    def test_string(self):
        """I really do."""
        return 'I like cows'
