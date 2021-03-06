"""
This module is used to auto-detect the type of a device in order to automatically create a
Netmiko connection.

The will avoid to hard coding the 'device_type' when using the ConnectHandler factory function
from Netmiko.
"""
from __future__ import unicode_literals

import re
import time
from netmiko.ssh_dispatcher import ConnectHandler
from netmiko.base_connection import BaseConnection


# 'dispatch' key is the SSHDetect method to call. dispatch key will be popped off dictionary
# remaining keys indicate kwargs that will be passed to dispatch method.
SSH_MAPPER_BASE = {
    'arista_eos': {
        "cmd": "show version | inc rist",
        "search_patterns": ["Arista"],
        "priority": 99,
        "dispatch": "_autodetect_std",
    },
    'cisco_ios': {
        "cmd": "show version | inc Cisco",
        "search_patterns": [
           "Cisco IOS Software",
           "Cisco Internetwork Operating System Software",
        ],
        "priority": 99,
        "dispatch": "_autodetect_std",
    },
    'cisco_asa': {
        "cmd": "show version | inc Cisco",
        "search_patterns": ["Cisco Adaptive Security Appliance", "Cisco ASA"],
        "priority": 99,
        "dispatch": "_autodetect_std",
    },
    'cisco_nxos': {
        "cmd": "show version | inc Cisco",
        "search_patterns": ["Cisco Nexus Operating System", "NX-OS"],
        "priority": 99,
        "dispatch": "_autodetect_std",
    },
    'cisco_xr': {
        "cmd": "show version | inc Cisco",
        "search_patterns": ["Cisco IOS XR"],
        "priority": 99,
        "dispatch": "_autodetect_std",
    },
    'huawei': {
        "cmd": "display version | inc Huawei",
        "search_patterns": ["Huawei Technologies"],
        "priority": 99,
        "dispatch": "_autodetect_std",
    },
    'juniper_junos': {
        "cmd": "show version | match JUNOS",
        "search_patterns": ["JUNOS Software Release"],
        "priority": 99,
        "dispatch": "_autodetect_std",
    },
}


class SSHDetect(object):
    """
    The SSHDetect class tries to automatically guess the device type running on the SSH remote end.

    Parameters
    ----------
    *args : list
        The same *args that you might provide to the netmiko.ssh_dispatcher.ConnectHandler.
    *kwargs : dict
        The same *kwargs that you might provide to the netmiko.ssh_dispatcher.ConnectHandler.

    Attributes
    ----------
    connection : netmiko.terminal_server.TerminalServer
        A basic connection to the remote SSH end.
    potential_matches: dict
        Dict of (device_type, accuracy) that is populated through an interaction with the
        remote end.

    Methods
    -------
    autodetect()
        Try to determine the device type.
    """

    def __init__(self, *args, **kwargs):
        """
        Constructor of the SSHDetect class
        """
        if kwargs['device_type'] != "terminal_server":
            raise ValueError("The connection device_type must be of 'terminal_server'")
        self.connection = ConnectHandler(*args, **kwargs)
        # Call the _test_channel_read() in base to clear initial data
        output = BaseConnection._test_channel_read(self.connection)
        self.initial_buffer = output
        self.potential_matches = {}
        self._results_cache = {}

    def autodetect(self):
        """
        Try to guess the best 'device_type' based on patterns defined in SSH_MAPPER_BASE

        Returns
        -------
        best_match : str or None
            The device type that is currently the best to use to interact with the device
        """
        for device_type, autodetect_dict in SSH_MAPPER_BASE.items():
            call_method = autodetect_dict.pop("dispatch")
            autodetect_method = getattr(self, call_method)
            accuracy = autodetect_method(**autodetect_dict)
            if accuracy:
                self.potential_matches[device_type] = accuracy

        if not self.potential_matches:
            self.connection.disconnect()
            return None

        best_match = sorted(self.potential_matches.items(), key=lambda t: t[1], reverse=True)
        self.connection.disconnect()
        return best_match[0][0]

    def _send_command(self, cmd=''):
        """Handle reading/writing channel directly."""
        self.connection.write_channel(cmd + "\n")
        time.sleep(1)
        output = self.connection._read_channel_timing()
        output = self.connection.strip_ansi_escape_codes(output)
        output = self.connection.strip_backspaces(output)
        return output

    def _send_command_wrapper(self, cmd):
        """Cache results for the same exact command."""
        cached_results = self._results_cache.get(cmd)
        if not cached_results:
            response = self._send_command(cmd)
            self._results_cache[cmd] = response
            return response
        else:
            return cached_results

    def _autodetect_std(self, cmd="", search_patterns=None, re_flags=re.I, priority=99):
        invalid_responses = [
            '% Invalid input detected',
            'syntax error, expecting',
        ]
        if not cmd or not search_patterns:
            return 0
        try:
            response = self._send_command_wrapper(cmd)
            # Look for error conditions in output
            for pattern in invalid_responses:
                match = re.search(pattern, response, flags=re.I)
                if match:
                    return 0
            for pattern in search_patterns:
                match = re.search(pattern, response, flags=re.I)
                if match:
                    return priority
        except Exception:
            return 0
        return 0
