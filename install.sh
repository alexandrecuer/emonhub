#!/bin/bash
# -------------------------------------------------------------
# emonHub install script
# -------------------------------------------------------------
# Assumes emonhub repository installed via git:
# git clone https://github.com/openenergymonitor/emonhub.git

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
usrdir=${DIR/\/emonhub/}

emonSD_pi_env=$1
if [ "$emonSD_pi_env" = "" ]; then
    read -sp 'Apply raspberrypi serial configuration? 1=yes, 0=no: ' emonSD_pi_env
    echo 
    echo "You entered $emonSD_pi_env"
    echo
fi

sudo apt-get install -y python-serial python-configobj
sudo pip install paho-mqtt requests

if [ "$emonSD_pi_env" = "1" ]; then
    # RaspberryPi Serial configuration
    # disable Pi3 Bluetooth and restore UART0/ttyAMA0 over GPIOs 14 & 15;
    # Review should this be: dtoverlay=pi3-miniuart-bt?
    sudo sed -i -n '/dtoverlay=pi3-disable-bt/!p;$a dtoverlay=pi3-disable-bt' /boot/config.txt

    # We also need to stop the Bluetooth modem trying to use UART
    sudo systemctl disable hciuart

    # Remove console from /boot/cmdline.txt
    sudo sed -i "s/console=serial0,115200 //" /boot/cmdline.txt

    # stop and disable serial service??
    sudo systemctl stop serial-getty@ttyAMA0.service
    sudo systemctl disable serial-getty@ttyAMA0.service
    sudo systemctl mask serial-getty@ttyAMA0.service
fi

sudo useradd -M -r -G dialout,tty -c "emonHub user" emonhub

# ---------------------------------------------------------
# EmonHub config file
# ---------------------------------------------------------
if [ ! -d /etc/emonhub ]; then
    sudo mkdir /etc/emonhub
fi

if [ ! -f /etc/emonhub/emonhub.conf ]; then
    sudo cp $usrdir/emonhub/conf/emonpi.default.emonhub.conf /etc/emonhub/emonhub.conf

    # Temporary: replace with update to default settings file
    sed -i "s/loglevel = DEBUG/loglevel = WARNING/" /etc/emonhub/emonhub.conf
fi
sudo chmod 666 /etc/emonhub/emonhub.conf

# ---------------------------------------------------------
# Install service
# ---------------------------------------------------------
echo "- installing emonhub.service"

# Install default emonhub.env service path settings
if [ ! -f /etc/emonhub/emonhub.env ]; then
    sudo cp $usrdir/emonhub/service/emonhub.env /etc/emonhub/emonhub.env
fi

sudo ln -sf $usrdir/emonhub/service/emonhub.service /lib/systemd/system
sudo systemctl enable emonhub.service
sudo systemctl restart emonhub.service

state=$(systemctl show emonhub | grep ActiveState)
echo "- Service $state"
# ---------------------------------------------------------
# Instal pymodbus
# ---------------------------------------------------------
echo "- instaling pymodbus"

sudo apt-get install python-dev
cd /
sudo git clone https://github.com/riptideio/pymodbus
cd pymodbus
sudo python setup.py install
# ---------------------------------------------------------


