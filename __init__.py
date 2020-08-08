"""
mycroft-chromecast-controll : A Mycroft skill for contolling media playing on a Chromecast

Copyright (C) 2016  Christopher Rogers

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from typing import Dict
import time

from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill, intent_handler
from mycroft.util.log import getLogger
from mycroft.util.parse import extract_duration

import pychromecast
import logging
import json

__author__ = 'ChristopherRogers1991'

LOGGER = getLogger(__name__)
logging.getLogger('zeroconf').setLevel(logging.ERROR)
logging.getLogger('pychromecast').setLevel(logging.WARNING)


SETTINGS_FILE="internal_settings.json"
DEFAULT_DEVICE="default_device"


class CaseInsensitiveDict(dict):
    @classmethod
    def _k(cls, key):
        return key.lower() if isinstance(key, str) else key

    def __init__(self, *args, **kwargs):
        super(CaseInsensitiveDict, self).__init__(*args, **kwargs)
        self._convert_keys()

    def __getitem__(self, key):
        return super(CaseInsensitiveDict, self).__getitem__(self.__class__._k(key))

    def __setitem__(self, key, value):
        super(CaseInsensitiveDict, self).__setitem__(self.__class__._k(key), value)

    def __delitem__(self, key):
        return super(CaseInsensitiveDict, self).__delitem__(self.__class__._k(key))

    def __contains__(self, key):
        return super(CaseInsensitiveDict, self).__contains__(self.__class__._k(key))

    def pop(self, key, *args, **kwargs):
        return super(CaseInsensitiveDict, self).pop(self.__class__._k(key), *args, **kwargs)

    def get(self, key, *args, **kwargs):
        return super(CaseInsensitiveDict, self).get(self.__class__._k(key), *args, **kwargs)

    def setdefault(self, key, *args, **kwargs):
        return super(CaseInsensitiveDict, self).setdefault(self.__class__._k(key), *args, **kwargs)

    def update(self, E=None, **F):
        if E is None:
            E = {}
        super(CaseInsensitiveDict, self).update(self.__class__(E))
        super(CaseInsensitiveDict, self).update(self.__class__(**F))

    def _convert_keys(self):
        for k in list(self.keys()):
            v = super(CaseInsensitiveDict, self).pop(k)
            self.__setitem__(k, v)


def cache(func):
    """
    Decorator to cache a function's result.
    This sets a property of the function itself
    to the result of the function call. This avoids
    the need to keep state in another object.
    This adds a `use_cache` parameter to the function.
    If set to False, the result will be regenerated. It
    is True by default.
    """
    func.cached_result = None

    def new_func(self, use_cache: bool = True):
        if not use_cache or not func.cached_result:
            func.cached_result = func(self)
        return func.cached_result

    return new_func


def device_user(intent_function):
    def new_function(self, message):
        device_name = message.data.get("Device", self._default_devicename())
        if not device_name:
            self.speak_dialog('no.device')
            return
        proper_name = self._devices_by_name.get(device_name)
        devices, browser = pychromecast.get_listed_chromecasts([proper_name])

        if not devices:
            self.speak_dialog("device.not.found", {"device": device_name})
            return

        device = list(devices)[0]
        device.wait()
        controller = device.media_controller
        controller.block_until_active(10)

        intent_function(self, message, controller)

        pychromecast.discovery.stop_discovery(browser)
        device.disconnect()

    return new_function


class ChromecastControllerSkill(MycroftSkill):

    def __init__(self):
        super(ChromecastControllerSkill, self).__init__(name="ChromecastControllerSkill")

    def initialize(self):
        self._default_duration = int(self.settings.get('default_duration', 30))
        self._devices_by_name = dict()
        self.refresh_devices()
        self.schedule_repeating_event(self.refresh_devices, None, 600)
        for name, device in self._devices_by_name.items():
            self.register_vocabulary(name, "Device")

    @cache
    def _default_devicename(self):
        return self._internal_settings.get(DEFAULT_DEVICE)

    @property
    def _internal_settings(self):
        try:
            with self.file_system.open(SETTINGS_FILE, 'r') as settings_file:
                return json.loads(settings_file.read()) or dict()
        except FileNotFoundError:
            return dict()
        except json.decoder.JSONDecodeError:
            LOGGER.warn("Could not decode settings. Returning empty dict.")
            return dict()

    def _write_settings(self, **kwargs):
        settings = self._internal_settings
        settings.update(kwargs)
        LOGGER.info("new settings: {}".format(settings))
        with self.file_system.open(SETTINGS_FILE, 'w') as settings_file:
            return settings_file.write(json.dumps(settings))

    def refresh_devices(self):
        chromecasts, browser = pychromecast.get_chromecasts()
        pychromecast.discovery.stop_discovery(browser)
        devices = {cc.device.friendly_name: cc.device.friendly_name for cc in chromecasts}
        self._devices_by_name = CaseInsensitiveDict(devices)


    @intent_handler(IntentBuilder("PauseChromecast")
                    .require("Pause")
                    .require("Chromecast")
                    .optionally("Device"))
    @device_user
    def _pause(self, _message, controller):
        controller.pause()

    @intent_handler(IntentBuilder("PlayChromecast")
                    .require("Play")
                    .require("Chromecast")
                    .optionally("Device"))
    @device_user
    def _play(self, _message, controller):
        controller.play()

    @intent_handler(IntentBuilder("SeekRelativeChromecast")
                    .require("Seek")
                    .one_of("Forward", "Backward")
                    .optionally("Chromecast")
                    .optionally("Device"))
    @device_user
    def _seek_relative(self, message, controller):
        direction = 1 if "Forward" in message.data else -1

        duration = extract_duration(message.utterance_remainder())[0]
        duration = duration.seconds if duration else self._default_duration
        duration *= direction

        current_time = controller.status.current_time
        controller.seek(current_time + duration)
        LOGGER.info("Seek {duration} on {device}".format(duration=duration, device=controller))

    @intent_handler(IntentBuilder("BeginningChromecast")
                    .require("Beginning")
                    .optionally("Chromecast")
                    .optionally("Device"))
    @device_user
    def _beginning(self, _message, controller):
        controller.rewind()

    @intent_handler(IntentBuilder("SubtitlesDisableChromecast")
                    .require("Subtitles")
                    .require("Disable")
                    .optionally("Chromecast")
                    .optionally("Device"))
    def _disable_subtitles(self, _message, controller):
        controller.disable_subtitle()

    @intent_handler(IntentBuilder("ListChromecasts")
                    .require("List")
                    .one_of("Chromecasts", "Chromecast"))
    def _list_devices(self, _message):
        devices = ", ".join(self._devices_by_name.values())
        self.speak_dialog("list.devices", {"devices": devices})

    @intent_handler(IntentBuilder("SetDefaultChromecasts")
                    .require("set")
                    .require("Device")
                    .require("Default")
                    .require("Chromecast"))
    def _set_default_device(self, message):
        device_name = message.data.get("Device")
        proper_name = self._devices_by_name.get(device_name)
        if not proper_name:
            self.speak_dialog("device.not.found", {"device", device_name})
        self._write_settings(default_device=proper_name)
        self.speak_dialog("default.set", {"device": proper_name})
        self._default_devicename(use_cache=False)


def create_skill():
    return ChromecastControllerSkill()
