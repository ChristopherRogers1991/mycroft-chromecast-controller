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


def device_user(intent_function: callable):
    def new_function(self: ChromecastControllerSkill, message: Message):
        device = message.data.get("Device", self._default_devicename)
        if not device:
            self.speak_dialog('no.device')
            return
        device_name = self._devices_by_name[device].device.friendly_name
        controller = get_controller_by_name(device_name)
        intent_function(self, message, controller)
    return new_function



class ChromecastControllerSkill(MycroftSkill):

    def __init__(self):
        super(ChromecastControllerSkill, self).__init__(name="ChromecastControllerSkill")

    def initialize(self):
        self._default_devicename = self.settings.get('default_device')
        self._default_duration = int(self.settings.get('default_duration', 30))

        # Would be used to set the subtitle track, but enabling subtitles does
        # not currently work
        # self._subtitle_language = "en"

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
    def _seek_relative(self, message: Message, controller):
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

    # Enabling subtitles does not currently work
    # @intent_handler(IntentBuilder("SubtitlesEnableChromecast")
    #                 .require("Subtitles")
    #                 .require("Enable")
    #                 .optionally("Chromecast")
    #                 .optionally("Device"))
    # def _enable_subtitles(self, message):
    #     device = message.data.get("Device", self._default_devicename)
    #     controller = get_controller_by_name(device)
    #     tracks = filter(lambda t: t['language'] == self._subtitle_language, controller.status.subtitle_tracks)
    #     track_id = next(tracks)["trackId"]
    #     controller.enable_subtitle(track_id)

    # previous/next in queue don't seem to work
    # @intent_handler(IntentBuilder("NextChromecast")
    #                 .require("Next")
    #                 .optionally("Chromecast")
    #                 .optionally("Device"))
    # @device_user
    # def _next(self, _message, controller):
    #     controller.queue_next()

    # @intent_handler(IntentBuilder("PreviousChromecast")
    #                 .require("Previous")
    #                 .optionally("Chromecast")
    #                 .optionally("Device"))
    # @device_user
    # def _previous(self, _message, controller):
    #     controller.queue_prev()



def create_skill():
    return ChromecastControllerSkill()
