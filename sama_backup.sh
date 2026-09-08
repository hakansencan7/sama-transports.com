#!/bin/bash
set -e

BACKUP_DIR="$HOME/sama_backups"
MONTHLY_DIR="$BACKUP_DIR/monthly"
DB="$HOME/public_html/sevkiyat.db"

mkdir -p "$BACKUP_DIR" "$MONTHLY_DIR"
chmod 700 "$BACKUP_DIR" "$MONTHLY_DIR"

STAMP=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_FILE="$BACKUP_DIR/sevkiyat_auto_${STAMP}.db"

sqlite3 "$DB" ".backup '$BACKUP_FILE'"
chmod 600 "$BACKUP_FILE"

sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" | grep -qx "ok"

if [ "$(date +%d)" = "01" ]; then
    MONTHLY_FILE="$MONTHLY_DIR/sevkiyat_monthly_$(date +%Y-%m).db"
    sqlite3 "$DB" ".backup '$MONTHLY_FILE'"
    chmod 600 "$MONTHLY_FILE"
    sqlite3 "$MONTHLY_FILE" "PRAGMA integrity_check;" | grep -qx "ok"
    echo "AYLIK ARSIV BASARILI: $MONTHLY_FILE"
fi

find "$BACKUP_DIR" -maxdepth 1 -type f -name 'sevkiyat_auto_*.db' -mtime +30 -delete
find "$MONTHLY_DIR" -type f -name 'sevkiyat_monthly_*.db' -mtime +1825 -delete

if ! "$HOME/bin/rclone" copy "$BACKUP_FILE" 'google_drive:SAMA TRACK YEDEKLER'; then
    echo "GOOGLE DRIVE YEDEK HATASI"
    exit 1
fi

echo "GOOGLE DRIVE YEDEK BASARILI: $BACKUP_FILE"
echo "OTOMATIK YEDEK BASARILI: $BACKUP_FILE"
