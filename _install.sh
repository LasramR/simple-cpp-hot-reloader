#!/usr/bin/sh

sudo apt update
sudo apt install git -y
git clone https://github.com/LasramR/simple-cpp-hot-reloader.git ~/.schr
sudo apt install pipx -y
pipx install -e ~/.schr
