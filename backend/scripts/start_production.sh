#!/bin/bash
set -e

# Default to port 80 if PORT is not set
PORT=${PORT:-80}

echo "Starting HabitOS..."
echo "Configuring Nginx to listen on port $PORT..."

# Update Nginx configuration to listen on the correct port
sed -i "s/listen 80;/listen $PORT;/g" /etc/nginx/sites-enabled/default

# Start supervisord to manage processes
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
