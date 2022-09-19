#!/usr/bin/env python3

#based off of https://github.com/Poohl/joycontrol

import argparse
import asyncio
import logging
import os

from aioconsole import ainput

import joycontrol.debug as debug
from joycontrol import logging_default as log, utils
from joycontrol.command_line_interface import ControllerCLI
from joycontrol.controller import Controller
from joycontrol.controller_state import ControllerState, button_push, button_press, button_release
from joycontrol.memory import FlashMemory
from joycontrol.protocol import controller_protocol_factory
from joycontrol.server import create_hid_server
from joycontrol.transport import NotConnectedError

logger = logging.getLogger(__name__)

async def veemotion(controller_state):
    # waits until controller is fully connected
    await controller_state.connect()

    while True:
        print("hello veemo")
        await asyncio.sleep(1)
        print("goodby veemo")
        controller_state.button_state.set_button("b", True)

        try:
            await controller_state.send()
        except NotConnectedError:
            #attempt reconnect if disconnected
            logger.info('Connection was lost.')
            logger.info("Please open the Change Grip/Order screen to reconnect...")
            await controller_state.connect()
            logger.info("Connection re-established.")

CONTROLLER_TYPE = "PRO_CONTROLLER"

async def _main(args):
    # Get controller name to emulate from arguments
    controller = Controller.from_arg(CONTROLLER_TYPE)

    # parse the spi flash
    if args.spi_flash:
        with open(args.spi_flash, 'rb') as spi_flash_file:
            spi_flash = FlashMemory(spi_flash_file.read())
    else:
        # Create memory containing default controller stick calibration
        spi_flash = FlashMemory()

    with utils.get_output(path=args.log, default=None) as capture_file:
        # prepare the the emulated controller
        factory = controller_protocol_factory(controller, spi_flash=spi_flash, reconnect = args.reconnect_bt_addr)
        ctl_psm, itr_psm = 17, 19
        transport, protocol = await create_hid_server(factory, reconnect_bt_addr=args.reconnect_bt_addr,
                                                      ctl_psm=ctl_psm,
                                                      itr_psm=itr_psm, capture_file=capture_file,
                                                      device_id=args.device_id,
                                                      interactive=True)

        controller_state = protocol.get_controller_state()

        # run veemotion
        try:
            await veemotion(controller_state)
        finally:
            logger.info('Stopping communication...')
            await transport.close()


if __name__ == '__main__':
    # check if root
    if not os.geteuid() == 0:
        raise PermissionError('Script must be run as root!')

    # setup logging
    #log.configure(console_level=logging.ERROR)
    log.configure()

    parser = argparse.ArgumentParser()
    parser.add_argument('controller', help='JOYCON_R, JOYCON_L or PRO_CONTROLLER')
    parser.add_argument('-l', '--log', help="BT-communication logfile output")
    parser.add_argument('-d', '--device_id', help='not fully working yet, the BT-adapter to use')
    parser.add_argument('--spi_flash', help="controller SPI-memory dump to use")
    parser.add_argument('-r', '--reconnect_bt_addr', type=str, default=None,
                        help='The Switch console Bluetooth address (or "auto" for automatic detection), for reconnecting as an already paired controller.')
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        _main(args)
    )
