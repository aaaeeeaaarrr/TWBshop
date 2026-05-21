#!/bin/bash
# Run this once on a fresh Ubuntu 24.04 server as root.
# Usage: bash server_setup.sh

set -e

echo "=== Installing system packages ==="
apt-get update
apt-get install -y python3 python3-pip python3-venv git

echo "=== Cloning repo ==="
git clone https://github.com/aaaeeeaaarrr/TWBshop.git /root/TWBshop

echo "=== Creating Python venv and installing packages ==="
python3 -m venv /root/venv
/root/venv/bin/pip install -r /root/TWBshop/requirements.txt

echo "=== Creating photos and logs directories ==="
mkdir -p /root/TWBshop/photos
mkdir -p /root/TWBshop/logs

echo "=== Installing systemd services ==="
cp /root/TWBshop/deploy/twbshop-retail.service /etc/systemd/system/
cp /root/TWBshop/deploy/twbshop-b2b.service    /etc/systemd/system/
systemctl daemon-reload
systemctl enable twbshop-retail twbshop-b2b

echo ""
echo "=== DONE ==="
echo ""
echo "Next steps:"
echo "  1. Create /root/TWBshop/secrets.py with your tokens and DATABASE_URL"
echo "  2. Then run: systemctl start twbshop-retail twbshop-b2b"
echo "  3. Check logs: journalctl -u twbshop-retail -f"
echo "               journalctl -u twbshop-b2b -f"
