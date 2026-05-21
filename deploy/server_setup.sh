#!/bin/bash
# Run this once on a fresh Ubuntu 24.04 server as root.
# Usage: bash server_setup.sh

set -e

echo "=== Creating twbshop user ==="
useradd -m -s /bin/bash twbshop

echo "=== Installing system packages ==="
apt-get update
apt-get install -y python3 python3-pip python3-venv git

echo "=== Cloning repo ==="
sudo -u twbshop git clone https://github.com/aaaeeeaaarrr/TWBshop.git /home/twbshop/TWBshop

echo "=== Installing Python packages ==="
cd /home/twbshop/TWBshop
sudo -u twbshop pip3 install -r requirements.txt

echo "=== Creating photos and logs directories ==="
sudo -u twbshop mkdir -p /home/twbshop/TWBshop/photos
sudo -u twbshop mkdir -p /home/twbshop/TWBshop/logs

echo "=== Installing systemd services ==="
cp deploy/twbshop-retail.service /etc/systemd/system/
cp deploy/twbshop-b2b.service    /etc/systemd/system/
systemctl daemon-reload
systemctl enable twbshop-retail twbshop-b2b

echo ""
echo "=== DONE ==="
echo ""
echo "Next steps:"
echo "  1. Create /home/twbshop/TWBshop/secrets.py with your tokens and DATABASE_URL"
echo "  2. Then run: systemctl start twbshop-retail twbshop-b2b"
echo "  3. Check logs: journalctl -u twbshop-retail -f"
echo "               journalctl -u twbshop-b2b -f"
