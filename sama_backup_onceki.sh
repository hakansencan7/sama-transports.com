#!/bin/bash
set -e

BACKUP_DIR="$HOME/sama_backups"
DB="$HOME/public_html/sevkiyat.db"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

STAMP=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_FILE="$BACKUP_DIR/sevkiyat_auto_${STAMP}.db"

cp "$DB" "$BACKUP_FILE"
chmod 600 "$BACKUP_FILE"

sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" | grep -qx "ok"

find "$BACKUP_DIR" -type f -name 'sevkiyat_auto_*.db' -mtime +30 -delete

echo "OTOMATIK YEDEK BASARILI: $BACKUP_FILE"
