import struct
import logging
from copy import deepcopy
from abc import ABC

logger = logging.getLogger(__name__)


class MessageABC(ABC):

    # The length of the message. Should be overwritten in child class
    msg_length = 0

    # The message command code. Should be overwritten in child class
    command_code = 0x00

    # Templet that is specific to each message type. Should be overwritten in child class
    msg_specific_templet = {}

    # Base message templet that is common for all messasges
    base_templet = {
        'header': {
            'format': '<Q',
            'start_byte': 0,
            'value': 0x11DDDDDDDDDDDDDD
        },
        'msg_length': {
            'format': '<L',
            'start_byte': 8,
            'value': 0
        },
        'command_code': {
            'format': '<L',
            'start_byte': 12,
            'value': 0x00000000
        },
        'extended_command_code': {
            'format': '<L',
            'start_byte': 16,
            'value': 0x00000000
        },
    }

    @classmethod
    def parse(cls, msg: bytearray) -> dict:
        """
        Parses the passed message and decodes it with the msg_encoding dict.
        Each key in the output message will have name of the key from the 
        msg_encoding dictionary.

        Parameters
        ----------
        msg : bytearry
            The message to parse.

        Returns
        -------
        decoded_msg_dict : dict
            The message items decoded into a dictionary.
        """
        decoded_msg_dict = {}

        # Create a templet to parse message with
        templet = {**deepcopy(cls.base_templet),
                   **deepcopy(cls.msg_specific_templet)}

        for item_name, item in templet.items():
            start_idx = item['start_byte']
            end_idx = item['start_byte'] + struct.calcsize(item['format'])
            decoded_msg_dict[item_name] = struct.unpack(
                item['format'], msg[start_idx:end_idx])[0]

            # Decode and strip trailing 0x00s from strings.
            if item['format'].endswith('s'):
                decoded_msg_dict[item_name] = decoded_msg_dict[item_name].decode(
                    item['text_encoding']).rstrip('\x00')

        if decoded_msg_dict['command_code'] != cls.command_code:
            logger.warning(
                f'Decoded command code {decoded_msg_dict["command_code"]} does not match what was expcected!')

        if decoded_msg_dict['msg_length'] != cls.msg_length:
            logger.warning(
                f'Decoded message length {decoded_msg_dict["msg_length"]} does not match what was expcected!')

        return decoded_msg_dict

    @classmethod
    def pack(cls, msg_values={}) -> bytearray:
        """
        Packs a message based on the message encoding given in the msg_specific_templet
        dictionary. Values can be substituted for default values if they are included 
        in the `msg_values` argument.

        Parameters
        ----------
        msg_values : dict
            A dictionary detailing which default values in the messtage temple should be 
            updated.

        Returns
        -------
        msg : bytearray
            Packed response message.
        """
        # Create a template to build messages from
        templet = {**deepcopy(cls.base_templet),
                   **deepcopy(cls.msg_specific_templet)}

        # Update the templet with message specific length and command code
        templet['msg_length']['value'] = cls.msg_length
        templet['command_code']['value'] = cls.command_code

        # Create a message bytearray that will be loaded with message contents
        msg = bytearray(templet['msg_length']['value'])

        # Update default message values with those in the passed msg_values dict
        for key in msg_values.keys():
            if key in templet.keys():
                templet[key]['value'] = msg_values[key]
            else:
                logger.warning(
                    f'Key name {key} was not found in msg_encoding!')

        # Pack each item in templet. If packing any item fails, then abort the packing the message.
        for item_name, item in templet.items():
            logger.debug(f'Packing item {item_name}')
            try:
                if item['format'].endswith('s'):
                    packed_item = struct.pack(
                        item['format'],
                        item['value'].encode(item['text_encoding']))
                else:
                    packed_item = struct.pack(
                        item['format'], item['value'])
            except struct.error as e:
                logger.error(
                    f'Error packing {item_name} with fields {item}!')
                logger.error(e)
                msg = bytearray([])
                break

            start_idx = item['start_byte']
            end_idx = item['start_byte'] + struct.calcsize(item['format'])
            msg[start_idx:end_idx] = packed_item

        # Append a checksum to the end of the message
        if msg:
            msg += struct.pack('<H', sum(msg))

        return msg


class Msg:
    class Login:
        '''
        Message for logging into Arbin cycler. See
        CTI_REQUEST_LOGIN/CTI_REQUEST_LOGIN_FEEDBACK 
        in Arbin docs for more info.
        '''
        class Client(MessageABC):
            msg_length = 74
            command_code = 0xEEAB0001

            msg_specific_templet = {
                'username': {
                    'format': '32s',
                    'start_byte': 20,
                    'text_encoding': 'utf-8',
                    'value': 'not a username'
                },
                'password': {
                    'format': '32s',
                    'start_byte': 52,
                    'text_encoding': 'utf-8',
                    'value': 'not a password'
                },
            }

        class Server(MessageABC):
            msg_length = 8678
            command_code = 0xEEBA0001

            msg_specific_templet = {
                'result': {
                    'format': 'I',
                    'start_byte': 20,
                    'value': 0
                },
                'cycler_sn': {
                    'format': '16s',
                    'start_byte': 28,
                    'text_encoding': 'ascii',
                    'value': '00000000'
                },
            }

            # Used to decode the login result
            login_result_decoder = [
                "should not see this", "success", "fail", "aleady logged in"]

            @classmethod
            def parse(cls, msg: bytearray) -> dict:
                """
                Same as the parrent method, but converts the result based on the
                login_result_decoder.

                Parameters
                ----------
                msg : bytearry
                    The message to parse.

                Returns
                -------
                msg_dict : dict
                    The message with items decoded into a dictionary
                """
                msg_dict = super().parse(msg)
                msg_dict['result'] = cls.login_result_decoder[msg_dict['result']]
                return msg_dict

    class ChannelInfo:
        '''
        Message for getting channel info from cycler. See
        CTI_REQUEST_GET_CHANNELS_INFO/CTI_REQUEST_GET_CHANNELS_INFO_FEED_BACK 
        in Arbin docs for more info.
        '''
        class Client(MessageABC):
            msg_length = 50
            command_code = 0xEEAB0003

            msg_specific_templet = {
                'channel': {
                    'format': '<h',
                    'start_byte': 20,
                    'value': 0
                },
                'channe_selection': {
                    'format': '<h',
                    'start_byte': 22,
                    'value': 1
                },
                'aux_options': {
                    'format': '<I',
                    'start_byte': 24,
                    'value': 0x00
                },
                'reseved': {
                    'format': '32s',
                    'start_byte': 28,
                    'value': ''.join(['\0' for i in range(32)]),
                    'text_encoding': 'utf-8',
                },
            }

        class Server(MessageABC):

            # Message length will vary based on number of aux readings.
            msg_length = 1779
            command_code = 0xEEBA0003

            # Used to determine index positions in THIRD_PARTY_AUX_VALUE struct
            __aux_voltage_count = 0
            __aux_temperature_count = 0
            __aux_pressure_count = 0
            __aux_external_count = 0
            __aux_flow_count = 0
            __aux_ao_count = 0
            __aux_di_count = 0
            __aux_do_count = 0 
            __aux_humidity_count = 0
            __aux_safety_count = 0
            __aux_ph_count = 0
            __aux_density_count = 0

            msg_specific_templet = {
                'number_of_channels': {
                    'format': '<I',
                    'start_byte': 20,
                    'value': 1
                },
                'channel': {
                    'format': '<I',
                    'start_byte': 24,
                    'value': 0
                },
                'status': {
                    'format': '<h',
                    'start_byte': 28,
                    'value': 0x00
                },
                'comm_failure': {
                    'format': '<B',
                    'start_byte': 30,
                    'value': 0
                },
                'schedule': {
                    # Stored as wchar_t[200]. Each wchar_t is 2 bytes, twice as big as standard char in Python
                    'format': '400s',
                    'start_byte': 31,
                    'value': 'fake_schedule',
                    'text_encoding': 'utf-16',
                },
                'testname': {
                    # Stored as wchar_t[72]
                    'format': '144s',
                    'start_byte': 431,
                    'value': 'fake_testname',
                    'text_encoding': 'utf-16',
                },
                'exit_condition': {
                    'format': '100s',
                    'start_byte': 575,
                    'value': 'none',
                    'text_encoding': 'utf-8',
                },
                'step_and_cycle_format': {
                    'format': '64s',
                    'start_byte': 675,
                    'value': 'none',
                    'text_encoding': 'utf-8',
                },
                # Stored as wchar_t[72]
                'barcode': {
                    'format': '144s',
                    'start_byte': 739,
                    'value': 'none',
                    'text_encoding': 'utf-16',
                },
                # Stored as wchar_t[72]
                'can_config_name': {
                    'format': '400s',
                    'start_byte': 883,
                    'value': 'none',
                    'text_encoding': 'utf-16',
                },
                # Stored as wchar_t[72]
                'smb_config_name': {
                    'format': '400s',
                    'start_byte': 1283,
                    'value': 'none',
                    'text_encoding': 'utf-16',
                },
                'master_channel': {
                    'format': '<H',
                    'start_byte': 1683,
                    'value': 0,
                },
                'test_time_s': {
                    'format': '<d',
                    'start_byte': 1685,
                    'value': 0,
                },
                'step_time_s': {
                    'format': '<d',
                    'start_byte': 1693,
                    'value': 0,
                },
                'voltage_v': {
                    'format': '<f',
                    'start_byte': 1701,
                    'value': 0,
                },
                'current_a': {
                    'format': '<f',
                    'start_byte': 1705,
                    'value': 0,
                },
                'power_w': {
                    'format': '<f',
                    'start_byte': 1709,
                    'value': 0,
                },
                'charge_capacity_ah': {
                    'format': '<f',
                    'start_byte': 1713,
                    'value': 0,
                },
                'discharge_capacity_ah': {
                    'format': '<f',
                    'start_byte': 1717,
                    'value': 0,
                },
                'charge_energy_wh': {
                    'format': '<f',
                    'start_byte': 1721,
                    'value': 0,
                },
                'discharge_energy_wh': {
                    'format': '<f',
                    'start_byte': 1725,
                    'value': 0,
                },
                'internal_resistance_ohm': {
                    'format': '<f',
                    'start_byte': 1729,
                    'value': 0,
                },
                'dvdt_vbys': {
                    'format': '<f',
                    'start_byte': 1733,
                    'value': 0,
                },
                'acr_ohm': {
                    'format': '<f',
                    'start_byte': 1737,
                    'value': 0,
                },
                'aci_ohm': {
                    'format': '<f',
                    'start_byte': 1741,
                    'value': 0,
                },
                'aci_phase_degrees': {
                    'format': '<f',
                    'start_byte': 1745,
                    'value': 0,
                },
                'aux_voltage_count': {
                    'format': '<H',
                    'start_byte': 1749,
                    'value': 0,
                },
                'aux_temperature_count': {
                    'format': '<H',
                    'start_byte': 1751,
                    'value': 0,
                },
                'aux_pressure_count': {
                    'format': '<H',
                    'start_byte': 1753,
                    'value': 0,
                },
                'aux_external_count': {
                    'format': '<H',
                    'start_byte': 1755,
                    'value': 0,
                },
                'aux_flow_count': {
                    'format': '<H',
                    'start_byte': 1757,
                    'value': 0,
                },
                'aux_ao_count': {
                    'format': '<H',
                    'start_byte': 1759,
                    'value': 0,
                },
                'aux_di_count': {
                    'format': '<H',
                    'start_byte': 1761,
                    'value': 0,
                },
                'aux_do_count': {
                    'format': '<H',
                    'start_byte': 1763,
                    'value': 0,
                },
                'aux_humidity_count': {
                    'format': '<H',
                    'start_byte': 1765,
                    'value': 0,
                },
                'aux_safety_count': {
                    'format': '<H',
                    'start_byte': 1767,
                    'value': 0,
                },
                'aux_ph_count': {
                    'format': '<H',
                    'start_byte': 1769,
                    'value': 0,
                },
                'aux_density_count': {
                    'format': '<H',
                    'start_byte': 1771,
                    'value': 0,
                },
                'bms_count': {
                    'format': '<H',
                    'start_byte': 1773,
                    'value': 0,
                },
                'smb_count': {
                    'format': '<H',
                    'start_byte': 1775,
                    'value': 0,
                },
            }
