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
from mycroft.messagebus.message import Message
from mycroft.util.log import getLogger
from mycroft.util.parse import extract_duration

import pychromecast

__author__ = 'ChristopherRogers1991'

LOGGER = getLogger(__name__)


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


def get_controller_by_name(name: str):
    cc: pychromecast.Chromecast = list(pychromecast.get_listed_chromecasts([name])[0])[0]
    cc.wait()
    cc.media_controller.block_until_active(10)
    return cc.media_controller


class ChromecastControllerSkill(MycroftSkill):

    def __init__(self):
        super(ChromecastControllerSkill, self).__init__(name="ChromecastControllerSkill")

    def initialize(self):
        self._default_devicename = "TV"
        self._default_duration = 30
        self._subtitle_language = "en"

        chromecasts, browser = pychromecast.get_chromecasts()
        pychromecast.discovery.stop_discovery(browser)
        self._devices_by_name = {cc.device.friendly_name: cc for cc in chromecasts}
        self._devices_by_name: Dict[str, pychromecast.Chromecast] = CaseInsensitiveDict(self._devices_by_name)
        for name in self._devices_by_name.keys():
            self.register_vocabulary(name, "Device")

    @intent_handler(IntentBuilder("PauseChromecast")
                    .require("Pause")
                    .require("Chromecast")
                    .optionally("Device"))
    def _pause(self, message):
        device = message.data.get("Device", self._default_devicename)
        controller = get_controller_by_name(device)
        controller.pause()

    @intent_handler(IntentBuilder("PlayChromecast")
                    .require("Play")
                    .require("Chromecast")
                    .optionally("Device"))
    def _play(self, message):
        device = message.data.get("Device", self._default_devicename)
        controller = get_controller_by_name(device)
        controller.play()

    @intent_handler(IntentBuilder("SeekRelativeChromecast")
                    .require("Seek")
                    .one_of("Forward", "Backward")
                    .optionally("Chromecast")
                    .optionally("Device"))
    def _seek_relative(self, message: Message):
        device = message.data.get("Device", self._default_devicename)
        direction = 1 if "Forward" in message.data else -1

        duration = extract_duration(message.utterance_remainder())[0]
        duration = duration.seconds if duration else self._default_duration
        duration *= direction

        controller = get_controller_by_name(device)
        current_time = controller.status.current_time
        controller.seek(current_time + duration)
        LOGGER.info("Seek {duration} on {device}".format(duration=duration, device=device))

    @intent_handler(IntentBuilder("BeginningChromecast")
                    .require("Beginning")
                    .optionally("Chromecast")
                    .optionally("Device"))
    def _beginning(self, message):
        device = message.data.get("Device", self._default_devicename)
        controller = get_controller_by_name(device)
        controller.rewind()

    @intent_handler(IntentBuilder("NextChromecast")
                    .require("Next")
                    .optionally("Chromecast")
                    .optionally("Device"))
    def _next(self, message):
        device = message.data.get("Device", self._default_devicename)
        controller = get_controller_by_name(device)
        controller.queue_next()

    @intent_handler(IntentBuilder("PreviousChromecast")
                    .require("Previous")
                    .optionally("Chromecast")
                    .optionally("Device"))
    def _previous(self, message):
        device = message.data.get("Device", self._default_devicename)
        controller = get_controller_by_name(device)
        controller.queue_prev()

    @intent_handler(IntentBuilder("SubtitlesDisableChromecast")
                    .require("Subtitles")
                    .require("Disable")
                    .optionally("Chromecast")
                    .optionally("Device"))
    def _disable_subtitles(self, message):
        device = message.data.get("Device", self._default_devicename)
        controller = get_controller_by_name(device)
        controller.disable_subtitle()

    @intent_handler(IntentBuilder("SubtitlesEnableChromecast")
                    .require("Subtitles")
                    .require("Enable")
                    .optionally("Chromecast")
                    .optionally("Device"))
    def _enable_subtitles(self, message):
        device = message.data.get("Device", self._default_devicename)
        controller = get_controller_by_name(device)
        tracks = filter(lambda t: t['language'] == self._subtitle_language, controller.status.subtitle_tracks)
        track_id = next(tracks)["trackId"]
        controller.enable_subtitle(track_id)


def create_skill():
    return ChromecastControllerSkill()
