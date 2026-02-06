#!/bin/bash
set -e

# Default to port 10000 if PORT is not set
PORT="${PORT:-10000}"

echo "Starting application on port $PORT..."

# Replace port 80 with the actual PORT in nginx config
sed -i "s/listen[[:space:]]\+80;/listen $PORT;/g" /etc/nginx/sites-enabled/default

# Verify the change in logs
echo "Nginx configuration after port update:"
grep "listen" /etc/nginx/sites-enabled/default

# Start supervisord
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
