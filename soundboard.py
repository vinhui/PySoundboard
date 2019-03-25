import json
import threading
from os import path

import config

if not config.NO_PI:
    import RPi.GPIO as GPIO
    import atexit
    from subprocess import call
else:
    from playsound import playsound


class Soundboard:
    def __init__(self, sounds_config=config.SOUNDS_CONFIG):
        self.sounds_config = sounds_config
        self.sounds = []
        self.run_gpio_thread = False
        self.load_from_config(sounds_config)
        if not config.NO_PI:
            self.setup_gpio()
            atexit.register(self.cleanup)

    def reload_config(self):
        print("Reloading config ('{0}')".format(self.sounds_config))
        self.load_from_config(self.sounds_config)
        if not config.NO_PI:
            self.setup_gpio()

    @staticmethod
    def cleanup():
        if config.VERBOSE_LOGGING:
            print("Cleaning up the GPIO")

        GPIO.cleanup()

    def load_from_config(self, sounds_config):
        if config.VERBOSE_LOGGING:
            print("Loading sound config '{0}'".format(sounds_config))

        with open(sounds_config) as f:
            self.sounds = json.load(f)

    def setup_gpio(self):
        if config.NO_PI:
            return

        if config.VERBOSE_LOGGING:
            print("Setting up the GPIO")

        GPIO.setmode(GPIO.BOARD)
        if not config.VERBOSE_LOGGING:
            GPIO.setwarnings(False)

        for item in self.sounds:
            if "GPIO_pin" not in item:
                continue

            pin = item["GPIO_pin"]
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            GPIO.add_event_detect(pin, GPIO.RISING, callback=lambda: self.on_button_pressed(pin))

    def on_button_pressed(self, pin):
        if config.VERBOSE_LOGGING:
            print("Button on pin {0} was pressed".format(pin))

        self.play_sound_from_pin(pin)
        pass

    @staticmethod
    def play_sound_file(file_path):
        full_path = path.join(config.SOUNDS_DIR, file_path)

        if path.isfile(full_path):
            print("Playing sound {0}".format(full_path))
            if config.NO_PI:
                try:
                    playsound(full_path, False)
                except NotImplementedError:
                    if config.VERBOSE_LOGGING:
                        print("Could not use the 'non blocking mode' from playsound, running it in a different thread")
                    threading.Thread(target=playsound, args=(full_path,)).start()
            else:
                threading.Thread(target=lambda: call(["aplay", "-q", file_path])).start()

            return True
        else:
            print("Could not find sound at '{0}'".format(full_path))
            return False

    def play_sound_by_name(self, name):
        if config.VERBOSE_LOGGING:
            print("Attempting to play sound by name ('{0}')".format(name))

        sound = self.get_sound_by_name(name)
        if sound is not False:
            return self.play_sound_file(sound["file"])
        else:
            print("Could not find sound '{0}'".format(name))
            return False

    def play_sound_from_pin(self, pin):
        if config.VERBOSE_LOGGING:
            print("Playing sound from pin ({0})".format(pin))

        sound = self.get_sound_by_pin(pin)
        if sound is not False:
            self.play_sound_file(sound["file"])
        else:
            print("There is no sound bound to GPIO pin {0}".format(pin))

    def get_sound_by_name(self, name):
        for item in self.sounds:
            if item["file"] == name:
                return item
            if path.splitext(item["file"])[0] == name:
                return item
            if "aliases" not in item:
                continue
            for alias in item["aliases"]:
                if alias == name:
                    return item

        return False

    def get_sound_by_pin(self, pin):
        for item in self.sounds:
            if "GPIO_pin" not in item:
                print("no attr")
                continue

            if item["GPIO_pin"] == pin:
                return item

        return False

    def add_sound(self, file, aliases, gpio_pin=None):
        if self.contains_sound_file(file):
            print("Sound file '{0}' already registered".format(file))
            return

        s = {"file": file, "aliases": aliases}
        if gpio_pin is not None:
            s["gpio_pin"] = gpio_pin
        self.sounds.append(s)
        self.write_to_config()

    def write_to_config(self):
        print("Updating sound config file '{0}'".format(config.SOUNDS_CONFIG))
        serialized = json.dumps(self.sounds, indent=4)
        f = open(config.SOUNDS_CONFIG, "w")
        f.write(serialized)
        f.close()

    def contains_sound_file(self, file):
        for item in self.sounds:
            if item["file"] == file:
                return True
        return False

    def contains_sound(self, name):
        return self.get_sound_by_name(name) is not False


from time import sleep

if __name__ == '__main__':
    soundboard = Soundboard()
    soundboard.play_sound_from_pin(10)
    sleep(3)
    soundboard.play_sound_by_name("mySound")
    sleep(3)
    soundboard.play_sound_by_name("beep")
