# look-mouse

Look at a screen, press a key, and the mouse cursor jumps to where you are looking.
Your normal mouse then carries on as usual.

- A Raspberry Pi 4 with a camera tracks your head and eyes.
- The Pi plugs into the main Windows computer by USB and appears as ordinary input
  devices. Nothing is installed on the main computer, and your normal mouse and keyboard
  stay plugged into it as they are.
- The trigger is Scroll Lock on your normal keyboard (Windows tells every keyboard about
  lock keys, and the Pi poses as one to listen). A push button on a GPIO pin also works.
- Everything else (screen layout, pointer check, calibration, behaviour) is done in a
  web page served by the Pi.

## Install on the Pi

Raspberry Pi 4, Raspberry Pi OS 64-bit, with a Pi camera or USB webcam, on your network.

```
git clone https://github.com/Walkergray79/look-mouse
cd look-mouse
bash install.sh
sudo reboot
```

Cable the Pi's USB-C port to the Windows computer, then open `http://<pi-name>.local:8080`
in a browser on the Windows computer.

The USB-C port is also the Pi 4's power input, so the Pi is powered by the computer's USB
port. If the Pi shows low-voltage warnings or restarts, use a USB-C power/data splitter or
power it through the GPIO header.

## Set up, in the web page

1. **Screens**: enter your Windows display layout.
2. **Pointer check**: click each screen in the diagram and watch where the cursor goes.
   If it only ever reaches the primary screen, switch the pointer option and measure the
   stepping distance. Stepping is only repeatable with Windows' "Enhance pointer precision"
   switched off.
3. **Calibrate**: put the browser on each screen in turn, look at the dot, press Space.
   One point per screen is enough to jump between screens; nine points per screen lets
   the cursor land where you look.

Then press Scroll Lock while looking at a screen.

## Try it without a Pi

```
pip install numpy
python3 -m look_mouse --simulate
```

Open `http://localhost:8080`. Sliders stand in for your head and nothing is sent over USB.
The page is read from disk on every refresh, so interface edits show immediately.

## Layout of the code

| File | What it does |
|---|---|
| `look_mouse/tracker.py` | Camera and face tracking (MediaPipe); produces head and eye measurements |
| `look_mouse/gaze.py` | Calibration maths: measurements to "which screen, where on it" |
| `look_mouse/hid.py` | USB output (jump, step, key tap) and the lock-key listener |
| `look_mouse/app.py` | Ties it together: trigger, estimate, jump |
| `look_mouse/server.py`, `look_mouse/web/index.html` | The web interface and its API |
| `look_mouse/config.py` | Settings and calibration, saved in `~/.config/look-mouse/config.json` |
| `scripts/setup_gadget.sh` | Makes the Pi appear as USB devices (run at boot by the installer) |

Tests: `python3 -m unittest discover -s tests`

## What has and hasn't been tested

Tested on a desktop Linux machine: the calibration maths, jump logic, trigger logic, web
interface (in simulation), and the face tracker against a sample photo (MediaPipe 1.2.3).

Not yet run on a Pi: the installer, the USB device setup, the Pi camera capture, and how
Windows places the pointer across three screens. The pointer check in the web page exists
to settle that last one.

## Notes

- The web page has no password. Anyone on your network can open it and see the camera
  preview.
- Camera frames are processed on the Pi and are not stored or sent anywhere else.
