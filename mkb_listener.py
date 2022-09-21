import asyncio, evdev
from evdev import InputDevice, categorize, ecodes

#TODO: opportunity to support absolute devices (eg in a VM.. but for now i'll skip this)

class MKBListener:
    def __init__(self, on_key_down=lambda x: None, on_key_up=lambda x: None, grab_devices=False):
        #mouse delta accumulators
        self.dx = 0
        self.dy = 0

        #keypress callbacks
        self.on_key_down = on_key_down
        self.on_key_up = on_key_up

        self.grabbed_devices = grab_devices
        self.devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        #TODO: filter devices by capabilities (EV_KEY, EV_ABS, EV_REL)

    def get_mouse_delta(self):
        delta = [self.dx, self.dy]
        self.dx = self.dy = 0
        return delta

    def on_move_x(self, value):
        self.dx += value

    def on_move_y(self, value):
        self.dy += value

    def listen(self):
        for device in self.devices:
            print("Listening for events from", device)
            asyncio.ensure_future(self.listen_on_device(device))
        pass

    def ungrab_devices(self):
        for dev in self.grabbed_devices:
            dev.ungrab()

    async def listen_on_device(self, device):
        async for event in device.async_read_loop():
            if event.type == ecodes.EV_KEY:
                #grab the device
                if self.grab_devices and device not in self.grabbed_devices:
                    device.grab()
                    self.grabbed_devices.append(device)
                #key releases
                if event.value == 0:
                    self.on_key_up(event.code)
                #key presses
                elif event.value == 1:
                    self.on_key_down(event.code)
            elif event.type == ecodes.EV_ABS:
                #TODO
                pass
            elif event.type == ecodes.EV_REL:
                #grab the device
                if self.grab_devices and device not in self.grabbed_devices:
                    device.grab()
                    self.grabbed_devices.append(device)
                #x movement
                if event.code == 0:
                    self.on_move_x(event.value)
                #y movement
                if event.code == 1:
                    self.on_move_y(event.value)
