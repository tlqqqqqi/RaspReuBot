#!/usr/bin/env bash
# Ставит Xray-core + systemd-сервис.
# Конфиг сервис читает из /usr/local/etc/xray/config.json
set -e

bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

echo
echo "=== Xray установлен. ==="
echo "Дальше положи свой config.json в /usr/local/etc/xray/config.json"
echo "и выполни:  sudo systemctl enable --now xray"
