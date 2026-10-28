#!/bin/bash
# One-time Let's Encrypt certificate setup for INE.
# Run once before starting the full stack:
#   bash scripts/init-letsencrypt.sh
# After this, docker compose up handles auto-renewal via the certbot service.

set -euo pipefail

DOMAIN="${CERTBOT_DOMAIN:-neomedia.dynv6.net}"
EMAIL="${CERTBOT_EMAIL:?Set CERTBOT_EMAIL in .env or export it}"
STAGING="${CERTBOT_STAGING:-0}"

CERT_DIR="/etc/letsencrypt/live/$DOMAIN"
RSA_KEY_SIZE=4096

echo "=== INE SSL initialisation ==="
echo "  Domain : $DOMAIN"
echo "  Email  : $EMAIL"
echo "  Staging: $STAGING"

# ── 1. TLS parameters (downloaded once, reused on renewal) ──────────────
echo "→ Downloading recommended TLS parameters..."
docker compose run --rm --entrypoint sh certbot -c "
  if [ ! -f /etc/letsencrypt/options-ssl-nginx.conf ]; then
    wget -q -O /etc/letsencrypt/options-ssl-nginx.conf \
      'https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf'
  fi
  if [ ! -f /etc/letsencrypt/ssl-dhparams.pem ]; then
    wget -q -O /etc/letsencrypt/ssl-dhparams.pem \
      'https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem'
  fi
"

# ── 2. Dummy self-signed cert so nginx can start before the real cert ────
echo "→ Creating temporary self-signed certificate..."
docker compose run --rm --entrypoint sh certbot -c "
  mkdir -p '$CERT_DIR'
  openssl req -x509 -nodes -newkey rsa:$RSA_KEY_SIZE -days 1 \
    -keyout '$CERT_DIR/privkey.pem' \
    -out    '$CERT_DIR/fullchain.pem' \
    -subj   '/CN=localhost' 2>/dev/null
"

# ── 3. Start nginx with the dummy cert ──────────────────────────────────
echo "→ Starting nginx..."
docker compose up --force-recreate -d nginx
sleep 5

# ── 4. Obtain real certificate ──────────────────────────────────────────
echo "→ Requesting Let's Encrypt certificate..."
STAGING_FLAG=""
[ "$STAGING" = "1" ] && STAGING_FLAG="--staging"

docker compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  --email "$EMAIL" --agree-tos --no-eff-email \
  $STAGING_FLAG \
  -d "$DOMAIN"

# ── 5. Reload nginx with the real cert ──────────────────────────────────
echo "→ Reloading nginx..."
docker compose exec nginx nginx -s reload

echo ""
echo "=== SSL setup complete ==="
echo "  Run 'docker compose up -d' to start the full stack."
echo "  Certificates auto-renew every 12 hours via the certbot service."
