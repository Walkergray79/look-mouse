#!/bin/bash
# Makes a Raspberry Pi 4 appear to the main computer as:
#   /dev/hidg0  an absolute pointer ("jump to X,Y")
#   /dev/hidg1  a keyboard that never types; used only to hear Scroll Lock toggles
#
# One-time preparation (then reboot):
#   add  dtoverlay=dwc2,dr_mode=peripheral  under [all] in /boot/firmware/config.txt
# Run as root on every boot, with the Pi's USB-C port cabled to the main computer.
set -euo pipefail

G=/sys/kernel/config/usb_gadget/gazemouse
modprobe libcomposite
[ -d "$G" ] && { echo "gadget already set up"; exit 0; }

mkdir -p "$G" && cd "$G"
echo 0x1d6b > idVendor      # Linux Foundation
echo 0x0104 > idProduct     # multifunction composite gadget
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB
mkdir -p strings/0x409
echo "gazemouse0001" > strings/0x409/serialnumber
echo "DIY"           > strings/0x409/manufacturer
echo "Gaze Mouse"    > strings/0x409/product

# Absolute pointer. Report = 5 bytes: buttons, X low, X high, Y low, Y high (0..32767)
mkdir -p functions/hid.usb0
echo 0 > functions/hid.usb0/protocol
echo 0 > functions/hid.usb0/subclass
echo 5 > functions/hid.usb0/report_length
printf '\x05\x01\x09\x02\xa1\x01\x09\x01\xa1\x00\x05\x09\x19\x01\x29\x03\x15\x00\x25\x01\x95\x03\x75\x01\x81\x02\x95\x01\x75\x05\x81\x03\x05\x01\x09\x30\x09\x31\x15\x00\x26\xff\x7f\x75\x10\x95\x02\x81\x02\xc0\xc0' \
  > functions/hid.usb0/report_desc

# Standard keyboard. Report = 8 bytes in; the host sends 1 byte of lock-key LEDs out.
mkdir -p functions/hid.usb1
echo 1 > functions/hid.usb1/protocol
echo 1 > functions/hid.usb1/subclass
echo 8 > functions/hid.usb1/report_length
printf '\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x03\x95\x05\x75\x01\x05\x08\x19\x01\x29\x05\x91\x02\x95\x01\x75\x03\x91\x03\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0' \
  > functions/hid.usb1/report_desc

mkdir -p configs/c.1/strings/0x409
echo "Gaze Mouse" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower
ln -s functions/hid.usb0 configs/c.1/
ln -s functions/hid.usb1 configs/c.1/

ls /sys/class/udc > UDC
chmod 666 /dev/hidg0 /dev/hidg1
echo "gadget ready: /dev/hidg0 (pointer), /dev/hidg1 (lock-key listener)"
