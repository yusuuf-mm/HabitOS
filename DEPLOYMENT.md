# 🚀 HabitOS Production Deployment Guide

This guide explains how to deploy HabitOS using the unified production container.

## 📋 Prerequisites

- Docker Engine 20.10+
- Docker Compose V2
- At least 2GB free RAM
- At least 10GB free disk space

## 🔧 Setup Instructions

### 1. Configure Environment Variables

Create a production environment file:

```bash
cp .env.production.template .env.production
```

Edit `.env.production` and set the following **critical** values:

```bash
# Generate secure random strings for these:
SECRET_KEY=<use: openssl rand -hex 32>
JWT_SECRET_KEY=<use: openssl rand -hex 32>
DB_PASSWORD=<strong-database-password>

# Update with your actual domain:
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### 2. Build the Production Container

Build the unified container image:

```bash
docker build -f Dockerfile.production -t habitos-production:latest .
```

This will:
- Build the React frontend
- Package the FastAPI backend
- Configure Nginx and Supervisord
- Create a single deployable image

**Build time**: Approximately 3-5 minutes depending on your machine.

### 3. Start the Production Stack

Using the production compose file:

```bash
docker-compose -f docker-compose.production.yml --env-file .env.production up -d
```

This starts:
- `habitos-app-prod`: The unified web application container
- `habitos-db-prod`: PostgreSQL database
- `habitos-redis-prod`: Redis cache

### 4. Run Database Migrations

Initialize the database schema:

```bash
docker-compose -f docker-compose.production.yml exec app alembic upgrade head
```

### 5. (Optional) Seed the Database

If you want to populate with sample data:

```bash
docker-compose -f docker-compose.production.yml exec app python scripts/seed_db.py
```

### 6. Verify Deployment

Check that all services are running:

```bash
docker-compose -f docker-compose.production.yml ps
```

All services should show status `Up`.

Test the application:

```bash
# Test frontend
curl -I http://localhost:80

# Test backend API
curl http://localhost:80/api/health
```

Open your browser to `http://localhost:80` (or your configured domain).

## 📊 Monitoring

### View Container Logs

All services:
```bash
docker-compose -f docker-compose.production.yml logs -f
```

Just the app container:
```bash
docker-compose -f docker-compose.production.yml logs -f app
```

Nginx logs specifically:
```bash
docker-compose -f docker-compose.production.yml exec app tail -f /var/log/supervisor/nginx.out.log
```

Backend logs specifically:
```bash
docker-compose -f docker-compose.production.yml exec app tail -f /var/log/supervisor/uvicorn.out.log
```

### Check Resource Usage

```bash
docker stats
```

## 🔄 Updates and Maintenance

### Update the Application

1. Pull latest code
2. Rebuild the container:
   ```bash
   docker-compose -f docker-compose.production.yml build app
   ```
3. Restart services:
   ```bash
   docker-compose -f docker-compose.production.yml up -d
   ```
4. Run any new migrations:
   ```bash
   docker-compose -f docker-compose.production.yml exec app alembic upgrade head
   ```

### Backup Database

```bash
docker-compose -f docker-compose.production.yml exec postgres pg_dump -U habituser habitdb > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore Database

```bash
cat backup_file.sql | docker-compose -f docker-compose.production.yml exec -T postgres psql -U habituser habitdb
```

## 🛑 Stopping the Application

```bash
docker-compose -f docker-compose.production.yml down
```

To also remove volumes (⚠️ this deletes all data):
```bash
docker-compose -f docker-compose.production.yml down -v
```

## 🌐 Production Deployment Notes

### Using a Reverse Proxy (Recommended)

For production with HTTPS, place the HabitOS container behind a reverse proxy like:
- **Nginx** on the host
- **Caddy** (automatic HTTPS)
- **Traefik**

Example Nginx configuration snippet:

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Scaling Considerations

The current setup uses:
- 2 Uvicorn workers for the backend
- Single Nginx instance

For higher traffic:
1. Increase Uvicorn workers in `supervisord.conf`
2. Consider using Docker Swarm or Kubernetes for horizontal scaling
3. Set up database connection pooling

### Security Hardening

- [ ] Change all default passwords
- [ ] Use strong SECRET_KEY and JWT_SECRET_KEY
- [ ] Configure firewall rules (only expose port 80/443)
- [ ] Regular security updates for base images
- [ ] Enable PostgreSQL SSL connections
- [ ] Consider removing `/docs` endpoint in production (edit `nginx.production.conf`)

## 🐛 Troubleshooting

### Container won't start

Check logs:
```bash
docker-compose -f docker-compose.production.yml logs app
```

### Frontend loads but API fails

1. Check if Uvicorn is running:
   ```bash
   docker-compose -f docker-compose.production.yml exec app supervisorctl status
   ```

2. Verify database connection:
   ```bash
   docker-compose -f docker-compose.production.yml exec app python -c "from app.core.database import engine; print('DB OK')"
   ```

### Permission errors

Ensure proper ownership:
```bash
docker-compose -f docker-compose.production.yml exec app chown -R www-data:www-data /var/www/html
```

## 📞 Support

For issues and support, please check:
- [GitHub Issues](https://github.com/yusuuf-mm/HabitOS/issues)
- Documentation in `/docs`
