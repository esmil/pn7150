#!/bin/sh
# vim: set ts=2 sw=2 et:

# root@stitch~# cat /etc/udev/rules.d/99-circuitpython.rules
# SUBSYSTEM=="block", ENV{DEVTYPE}=="partition", ENV{ID_FS_LABEL}=="RPI-RP2", GROUP="users"
# SUBSYSTEM=="block", ENV{DEVTYPE}=="partition", ENV{ID_FS_LABEL}=="CIRCUITPY", GROUP="users"

set -e

RP2040_LABEL='RPI-RP2'
CIRCUITPYTHON_LABEL='CIRCUITPY'

RP2040_DEV="/dev/disk/by-label/$RP2040_LABEL"
CIRCUITPYTHON_DEV="/dev/disk/by-label/$CIRCUITPYTHON_LABEL"

while true; do
  echo "Waiting for $RP2040_DEV"
  while ! [ -b "$RP2040_DEV" ]; do
    echo -n '.'
    sleep 0.2
  done
  echo
  mcopy -vQi "$RP2040_DEV" firmware.uf2 ::

  echo "Waiting for $CIRCUITPYTHON_DEV"
  while ! [ -b "$CIRCUITPYTHON_DEV" ]; do
    echo -n '.'
    sleep 0.2
  done
  echo
  mcopy -voQi "$CIRCUITPYTHON_DEV" PN7150.py NT3H2.py code.py ::
done
