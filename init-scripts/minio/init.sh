#!/bin/sh

sleep 10
wget -q https://dl.min.io/client/mc/release/linux-amd64/mc -O /usr/local/bin/mc
chmod +x /usr/local/bin/mc

mc alias set myminio http://minio:9000 minioadmin minioadmin

mc mb myminio/data-contracts --ignore-existing

mc mkdir myminio/data-contracts/users
mc mkdir myminio/data-contracts/orders
mc mkdir myminio/data-contracts/users2

if [ -f /init-data/openmetadata.json ]; then
    mc cp /init-data/openmetadata.json myminio/data-contracts/
fi

if [ -f /init-data/users.csv ]; then
    mc cp /init-data/users.csv myminio/data-contracts/users/
    mc cp /init-data/users.csv myminio/data-contracts/users2/
fi

if [ -f /init-data/orders.csv ]; then
    mc cp /init-data/orders.csv myminio/data-contracts/orders/
fi
