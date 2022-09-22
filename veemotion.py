import argparse
import asyncio
from collections import defaultdict
import time
from math import degrees

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

#TODO: make y button reset pitch to 0

#TODO: cli args
#TODO: reconnect_bt_addr
#   if not found in config, start server in pair mode with None
#   once paired, save to config
#TODO: custom(izeable) pro controller color ;^) (modify default flash memory bytes)

#--attempted shenanigans with titan 2 splatoon 2 script--
MAXGX = 45.0
DEFAULT_MMY = 0.0
MAXR = 212.5
mmy = DEFAULT_MMY
y_toggle = False

def gyro_aim(imu, mouse_x, mouse_y):
    global mmy, y_toggle
    #i think for this consoletuner script, mouse x/y are bound to switch_RX/RY

    #TODO: dont completely zero imu every frame (modify controller_state to not do this)
    #   and commit that change to joycontrol repo

    # set_val(SWITCH_ACCZ,0.0 );
    imu.set_z(0)
    # set_val(SWITCH_ACCY,0.0 );
    imu.set_y(0)
    # set_val(SWITCH_GYROZ, 0.0 );
    imu.set_yaw(0)
    # set_val(SWITCH_GYROY, 0.0 );
    imu.set_pitch(0)
    # set_val(SWITCH_GYROX, 0.0 );
    imu.set_roll(0)
    # set_val(SWITCH_ACCX, 0.0);
    imu.set_x(0)

    #TODO: what units are the consoletuner gyro values in...?

    # if(event_active(SWITCH_Y)) {
    #     y_toggle = !y_toggle;
    #     mmy = DEFAULT_MMY;
    # }
    # if(y_toggle) {
    #     set_val(SWITCH_Y, 100.0);
    # }

    # SWITCH_RY = 0
    SWITCH_RY = mouse_y
    #fix32 my = rad2deg(get_val(SWITCH_RY) / 200.0 * PI) / MAXGX;
    my = degrees(SWITCH_RY / 200.0 * np.pi) / MAXGX;
    # mmy = clamp( mmy + my , -MAXGX , MAXGX );
    mmy = np.clip(mmy + my, -MAXGX, MAXGX);
    # set_val(SWITCH_ACCY, mmy );
    imu.set_y(mmy); #TODO: units?
    # if( abs(mmy) != MAXGX ){
    if abs(mmy) != MAXGX:
        # set_val(SWITCH_GYROX, my * MAXR );
        my_maxr = my * MAXR
        my_maxr = np.clip(my_maxr, -2000, 1999)
        imu.set_roll(my_maxr)
    # else {
    else:
        #i think GYRO_1_X is the same as SWITCH_GYROX
        # set_val(GYRO_1_X,0.0);
        imu.set_roll(0.0)
    # }

    # set_val(SWITCH_ACCZ, abs(get_val(SWITCH_ACCY)) - 25.0  );
    imu.set_z(abs(imu.y) - 25.0)
    # fix32 gyroz = rad2deg(get_val(SWITCH_RX) / 200.0 * PI) / 45.0 * MAXR;
    # SWITCH_RX = 0
    SWITCH_RX = mouse_x
    gyroz = degrees(SWITCH_RX / 200.0 * np.pi) / 45.0 * MAXR
    # set_val(SWITCH_GYROZ, gyroz * -get_val(SWITCH_ACCZ) / 25.0 );
    yaw = gyroz * -imu.z / 25.0
    yaw = np.clip(yaw, -2000, 1999)
    imu.set_yaw(yaw)
    # set_val(SWITCH_GYROY, gyroz * -get_val(SWITCH_ACCY) / 25.0 );
    pitch = gyroz * -imu.y / 25.0
    pitch = np.clip(pitch, -2000, 1999)
    imu.set_pitch(pitch)
    # set_val(SWITCH_ACCX, 0.0 );
    imu.set_x(0.0)
    # set_val(SWITCH_RY, 0.0);
    # set_val(SWITCH_RX, 0.0);
#--end attempted shenanigans with titan 2 splatoon 2 script--

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
    pitch = 0

    while True:
        delta = np.array(listener.get_mouse_delta())
        delta = delta * config.motion.sensitivity

        #setting last value seems to affect yaw a lot, and pitch some?
        #setting second to last value seems to not do anything (wrong axis?)
        #it seems either the only value that changes gyro at all is the last one
        #   but maybe gyro controls don't activate until some nonzero yaw is sent (which would normally happen immediately with a regular controller)

        #pitch = np.sin(time.time()) * np.pi / 4 #auto pitch up/down +-45 degrees
        pitch += delta[1] #mouse y based pitch up/down (NOTE: sensitivity weird)
        pitch = np.clip(pitch, -45, 45)
        acc_z = np.cos(pitch) * -1000
        acc_x = np.sin(pitch) * -1000

        #attempts at mouse x yaw movement
        #fake_yaw = np.sin(time.time() / 5) * 10 #automatic
        fake_yaw = delta[0] #mouse-based
        yaw_z = np.cos(pitch) * fake_yaw
        yaw_x = np.sin(pitch) * fake_yaw

        #comment out any set_imu lines below and uncomment this next line to test titan 2 script shenans
        # gyro_aim(controller_state.imu_state, delta[0], delta[1])

        # controller_state.imu_state.set_imu(0, 0, -1000, 0, 0, 0)
        controller_state.imu_state.set_imu(acc_x, 0, acc_z, 0, 0, 100)#huzzah it looks up and down
        # controller_state.imu_state.set_imu(acc_x, 0, acc_z, yaw_x, 0, yaw_z) #attempt at yawing
        # controller_state.imu_state.set_imu(0, 0, -1000, yaw_x, 0, yaw_z)

        # controller_state.imu_state.set_imu(0, 0, 1000, 0, 0, delta[0] * 100) #flips out
        # controller_state.imu_state.set_imu(50, 10, 1000, -30, 5, delta[0] * 100) #doesnt move at all
        # controller_state.imu_state.set_imu(np.random.normal(), np.random.normal(), 1000, np.random.normal(), np.random.normal(), delta[0] * 1000)
        #controller_state.imu_state.set_imu(acc_x, 0, acc_z, 0, 0, 90)
        # controller_state.imu_state.set_imu(0, 0, -1000, 0, 0, 90)
        # controller_state.imu_state.set_imu(0, 0, -1000, 0, 0, 90)

        # controller_state.imu_state.set_imu(acc_x, 0, acc_z, yaw_x, 0, yaw_z)
        # controller_state.imu_state.set_imu(1000, 0, 0, fake_yaw, 0, 1000)
        # controller_state.imu_state.set_imu(0, 0, 1000, 0, 0, 6.3)
        # controller_state.imu_state.set_imu(0, 0, -1000, 0, 0, 200)
        # controller_state.imu_state.set_imu(*[np.random.normal() for _ in range(6)]) #spazzes out
        # controller_state.imu_state.set_imu(0, 0, 0, *[np.random.normal() for _ in range(3)]) #does not spaz out
        # controller_state.imu_state.set_imu(*[np.random.normal() for _ in range(3)], 0, 100, 0) #does not spaz out (maybe because no pyr)
        # controller_state.imu_state.set_imu(acc_x, 0, acc_z, 0, 0, 100)

        gyro_aim(controller_state.imu_state, delta[0], delta[1])

        #TODO: off by 1? oh well...
        lstick_h = (int(lstick["right"]) - int(lstick["left"])) * 0x7ff + 0x800
        lstick_v = (int(lstick["up"]) - int(lstick["down"])) * 0x7ff + 0x800
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
