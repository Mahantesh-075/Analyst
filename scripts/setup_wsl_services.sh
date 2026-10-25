#!/bin/bash
set -euo pipefail

# 1. Configure PostgreSQL
PG_CONF=$(find /etc/postgresql -name postgresql.conf | head -n 1)
PG_HBA=$(find /etc/postgresql -name pg_hba.conf | head -n 1)

if [ -n "$PG_CONF" ]; then
    sed -i "s/^port = .*/port = 5432/" "$PG_CONF"
    sed -i "s/^#*listen_addresses = .*/listen_addresses = '*'/" "$PG_CONF"
fi

if [ -n "$PG_HBA" ]; then
    if ! grep -q "0.0.0.0/0" "$PG_HBA"; then
        echo "host all all 0.0.0.0/0 md5" >> "$PG_HBA"
        echo "host all all ::0/0 md5" >> "$PG_HBA"
    fi
fi

systemctl restart postgresql

# Ensure analyst user and analyst db exist
sudo -u postgres psql -p 5432 -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analyst') THEN CREATE USER analyst WITH PASSWORD 'analyst' SUPERUSER; END IF; END \$\$;"
sudo -u postgres psql -p 5432 -tc "SELECT 1 FROM pg_database WHERE datname = 'analyst'" | grep -q 1 || sudo -u postgres createdb -p 5432 -O analyst analyst

# Apply db/schema.sql to analyst database
sudo -u postgres psql -p 5432 -d analyst -f /mnt/c/Users/mahan/.gemini/analyst/db/schema.sql 2>/dev/null || true

# 2. Configure Redis
REDIS_CONF=/etc/redis/redis.conf
if [ -f "$REDIS_CONF" ]; then
    sed -i "s/^bind .*/bind 0.0.0.0/" "$REDIS_CONF"
    sed -i "s/^protected-mode yes/protected-mode no/" "$REDIS_CONF"
    systemctl restart redis-server
fi

# 3. Configure MinIO
mkdir -p /var/lib/minio/data
cat << 'EOF' > /etc/systemd/system/minio.service
[Unit]
Description=MinIO Object Storage
After=network.target

[Service]
Type=simple
User=root
Environment=MINIO_ROOT_USER=minio
Environment=MINIO_ROOT_PASSWORD=minio12345
ExecStart=/usr/local/bin/minio server /var/lib/minio/data --address 0.0.0.0:9000 --console-address 0.0.0.0:9001
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now minio.service
systemctl restart minio.service

echo "=== SERVICE STATUS ==="
systemctl is-active postgresql redis-server minio
ss -tulpn | grep -E '5432|6379|9000'
