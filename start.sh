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

# Run database migrations
echo "Running database migrations..."
if alembic upgrade head; then
    echo "Database migrations applied successfully."
else
    echo "Error applying database migrations."
    exit 1
fi

# Start supervisord
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
