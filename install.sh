#!/bin/bash
# Installs look-mouse on a Raspberry Pi 4 (Raspberry Pi OS, 64-bit). Run from the repository folder:
#   bash install.sh
set -euo pipefail
cd "$(dirname "$0")"
DIR="$PWD"
MODEL_URL=https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task

echo "== System packages"
# Accept changed release labels (e.g. Debian renaming a release to "oldstable"), which otherwise stop the update.
sudo apt-get update --allow-releaseinfo-change
sudo apt-get install -y python3-venv python3-picamera2 python3-gpiozero libegl1 libgles2 curl

echo "== Python environment"
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt

echo "== Face tracking model"
mkdir -p models
[ -s models/face_landmarker.task ] || curl -fL -o models/face_landmarker.task "$MODEL_URL"

echo "== USB device mode"
BOOT=/boot/firmware/config.txt
[ -f "$BOOT" ] || BOOT=/boot/config.txt
if ! grep -q '^dtoverlay=dwc2,dr_mode=peripheral' "$BOOT"; then
  printf '\n[all]\ndtoverlay=dwc2,dr_mode=peripheral\n' | sudo tee -a "$BOOT" > /dev/null
fi

echo "== Services (start on every boot)"
sudo tee /etc/systemd/system/look-mouse-gadget.service > /dev/null <<UNIT
[Unit]
Description=look-mouse USB devices
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash $DIR/scripts/setup_gadget.sh
[Install]
WantedBy=multi-user.target
UNIT
sudo tee /etc/systemd/system/look-mouse.service > /dev/null <<UNIT
[Unit]
Description=look-mouse
After=look-mouse-gadget.service network.target
Wants=look-mouse-gadget.service
[Service]
User=$USER
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python -m look_mouse
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable look-mouse-gadget.service look-mouse.service

echo
echo "Done. Reboot the Pi (sudo reboot), then open http://$(hostname).local:8080 on the main computer."
