import argparse
import asyncio
from collections import defaultdict

from evdev import ecodes
from munch import munchify
import yaml
import numpy as np #TODO: remove?

from joycontrol.protocol import controller_protocol_factory
from joycontrol.server import create_hid_server
from joycontrol.memory import FlashMemory
from joycontrol.controller import Controller

from mkb_listener import MKBListener

with open("config.yaml", "r") as f:
    config = munchify(yaml.safe_load(f))

#TODO: how to automatically reconnect if disconnected?
#   await controller_state.connect() doesn't seem to work (maybe just returns if already connected once, even if currently disconnected?)

#TODO: see if we can reconnect without repairing by pressing l+r on the change grip/order screen

#TODO: cli args
#TODO: reconnect_bt_addr
#   if not found in config, start server in pair mode with None
#   once paired, save to config
#TODO: custom(izeable) pro controller color ;^) (modify default flash memory bytes)

#TODO: grab devices once stuff works

#TODO: emulate sticks

#meh
def find_button(code, obj):
    for key, value in obj.items():
        if ecodes.ecodes[key] == code:
            return value
    return None

async def veemotion(controller_state):
    #TODO: think of a better way to do this
    lstick = defaultdict(bool)

    def on_key_down(code):
        print(code, "down")
        if code == ecodes.KEY_ESC:
            listener.ungrab_devices()
            exit(0)

        button = find_button(code, config.buttons)
        if button is not None:
            print("got", code, "pressing", button)
            controller_state.button_state.set_button(button, True)

        stick_dir = find_button(code, config.left_stick)
        if stick_dir is not None:
            lstick[stick_dir] = True

    def on_key_up(code):
        print(code, "up")

        button = find_button(code, config.buttons)
        if button is not None:
            print("got", code, "releasing", button)
            controller_state.button_state.set_button(button, False)

        stick_dir = find_button(code, config.left_stick)
        if stick_dir is not None:
            lstick[stick_dir] = False

    listener = MKBListener(on_key_down, on_key_up, grab_devices=True)
    listener.listen()

    # wait for connection
    await controller_state.connect()

    while True:
        delta = np.array(listener.get_mouse_delta())
        delta = delta * config.motion.sensitivity
        delta = np.clip(delta, -2000, 2000)
        print("gyro", delta)
        controller_state.imu_state.set_imu(0, 0, 0, 0, delta[1], delta[0])
        #TODO: off by 1? oh well...
        lstick_h = (int(lstick["right"]) - int(lstick["left"])) * 0x7ff + 0x800
        lstick_v = (int(lstick["up"]) - int(lstick["down"])) * 0x7ff + 0x800
        print("stick", lstick_h, lstick_v)
        controller_state.l_stick_state.set_h(lstick_h)
        controller_state.l_stick_state.set_v(lstick_v)

        try:
            await controller_state.send()
        except NotConnectedError:
            #attempt reconnect if disconnected
            logger.info('Connection was lost.')
            logger.info("Please open the Change Grip/Order screen to reconnect...")
            #TODO: how to reconnect? this might just return true if previously connected
            await controller_state.connect()
            logger.info("Connection re-established.")

async def main(args):
    switch_mac = config.switch_mac if "switch_mac" in config else None
    factory = controller_protocol_factory(Controller.PRO_CONTROLLER, spi_flash=FlashMemory())
    transport, protocol = await create_hid_server(factory, reconnect_bt_addr=switch_mac, interactive=True)
    # transport, protocol = await create_hid_server(factory, reconnect_bt_addr="auto", interactive=True)
    controller_state = protocol.get_controller_state()

    try:
        await veemotion(controller_state)
    except Exception as e:
        print(e)
        print("TODO: HANDLE THIS EXCEPTION")
    finally:
        await transport.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    asyncio.get_event_loop().run_until_complete(
        main(args)
    )
