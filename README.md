# Veemotion
*You lip-synch, we drip ink.*

Mouse-and-keyboard-to-pro-controller adapter. Connects via bluetooth. Uses https://github.com/tehZevo/joycontrol (thanks to upstream devs mart1nro and Poohl!)

## Developers
* [tehZevo](https://github.com/tehZevo): implementation
* [Chrono](https://github.com/Chrono-byte): came up with the repo name :^)
* [Kaydax](https://github.com/Kaydax): debugging/testing and *finding the final piece of the gyro puzzle*

## TODO
* docs
* actually test this darn thing
* automatically reconnect when disconnected
  * or quit program when disconnected until we have auto reconnect working...
* load/save switch mac address from/to config
* add pro controller color customization?
* right joycon only mode so you can joycon + mouse (gl binding enough buttons though)
* improve keybindings
  * consider booyah!ing
* fix create_future crash on python 3.10 (upstream joycontrol bug) (might be fixed now?)
* create OS image that autolaunches veemotion for raspberry pi usage
* rename pitch/yaw/roll to gyro x/y/z and x/y/z to accel x/y/z?

## Notes
* may need to install python(3.9)-dev
* you may need to keep a "safety mouse" around

## Quotes
tehZevo: What about gyro?
Kaydax: I can't get into the menu to enable gyro!!!
