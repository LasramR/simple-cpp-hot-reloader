#!/usr/bin/sh

sudo apt update
sudo apt install pipx -y
pipx install -e ~/.schr
chmod +x ~/.schr/_uninstall.sh
