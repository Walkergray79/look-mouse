# look-mouse

Look at a screen, press a key, and the mouse cursor jumps to where you are looking.
Your normal mouse then takes over as usual.

## Design

- A Raspberry Pi 4 with a camera tracks where your head (later, your eyes) is pointing.
- The Pi plugs into the main Windows computer by USB and appears as an ordinary pointing
  device, so nothing is installed on the main computer.
- The normal mouse stays connected to the main computer separately.
- The trigger is Scroll Lock on the normal keyboard: Windows reports lock-key changes to
  every keyboard, and the Pi poses as one to hear them.
- Target layout: portrait monitor on the left, landscape monitors in front and on the right.

## Build order

1. **USB link (this commit, no camera needed).** Check where Windows places an absolute
   pointer across three screens, and that the Pi hears Scroll Lock.
2. Camera and head tracking, with a look-and-press calibration per screen.
3. Trigger jumps to the last cursor position on the screen you are facing.
4. Finer positioning within a screen, then eye tracking for the portrait monitor.

## Step 1: running the test

One-time on the Pi: add `dtoverlay=dwc2,dr_mode=peripheral` under `[all]` in
`/boot/firmware/config.txt`, then reboot.

Cable the Pi's USB-C port to the Windows computer, then:

```
sudo bash setup_gadget.sh        # needed after every boot
python3 test_pointer.py sweep    # cursor visits centre and four corners; note which screens
python3 test_pointer.py listen   # prints a line per Scroll Lock press
python3 test_pointer.py jump     # Scroll Lock jumps the cursor
```

Status: the scripts are syntax-checked only and have not yet been run on hardware.

Note: the USB-C port is also the Pi 4's power input. Power from the computer's USB port is
enough for this test but probably not once the camera and tracking are running.
