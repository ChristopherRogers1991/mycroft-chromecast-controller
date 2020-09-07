# mycroft-chromecast-controller
A Mycroft skill for controlling media playback on a Chromecast

## Short Demo
https://youtu.be/4Sd6X-ae0dI

## Sample Phrases
1. Play Chromecast
2. Pause Chromecast
3. Skip forward
4. Go back
5. Go back 1 minute
6. Go to the beginning
7. List Chromecasts
8. Set default Chromcast <device name>

## Notes

When you seek forward or backward, and do not supply a duration, the skill will jump by a default amount of time. The amount of time it skips is configurable in your Mycroft settings (it is initially set to 30 seconds).

Mycroft core ships with an outdated version of the `pychromecast` library (apparently to optionally stream audio from the device to a chromecast - doesn't seem to be widely used, if it's used at all). If you experience issues with this skill, run `pip uninstall pychromecast` and then `pip install -r requirements.txt` from within the install directory of this skill. This will remove the outdated version, and install the version required by this skill. If you are using a virtual environment, be sure to activate it before running the `pip` commands.
