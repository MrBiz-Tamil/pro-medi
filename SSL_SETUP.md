# SSL Setup Guide for Production Domains

## Domains Configuration
- **API Domain**: api.medihub.mrbiz.in
- **LiveKit Domain**: rtc.mrbiz.in
- **Frontend Domain**: medihub.mrbiz.in (optional)

## Prerequisites

1. **DNS Configuration**
   Point your domains to your server IP:
   ```
   api.medihub.mrbiz.in    → A record → YOUR_SERVER_IP
   rtc.mrbiz.in           → A record → YOUR_SERVER_IP
   medihub.mrbiz.in       → A record → YOUR_SERVER_IP (optional)
   ```

2. **Firewall Configuration**
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw allow 22/tcp
   ```

## Step 1: Install Certbot

```bash
# Update packages
sudo apt update

# Install Certbot and Nginx plugin
sudo apt install certbot python3-certbot-nginx -y
```

## Step 2: Update Docker Compose for SSL

Add Certbot volume to docker-compose.yml:

```yaml
nginx:
  image: nginx:alpine
  container_name: medhub_nginx
  restart: always
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx/conf.d:/etc/nginx/conf.d
    - ./certbot/conf:/etc/letsencrypt
    - ./certbot/www:/var/www/certbot
  depends_on:
    - client
    - api
  networks:
    - medhub-network
```

## Step 3: Get SSL Certificates

### For API Domain (api.medihub.mrbiz.in)

```bash
# Stop nginx temporarily
docker compose stop nginx

# Get certificate
sudo certbot certonly --standalone \
  -d api.medihub.mrbiz.in \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email

# Start nginx
docker compose up -d nginx
```

### For LiveKit Domain (rtc.mrbiz.in)

LiveKit needs its own SSL configuration. You have two options:

**Option 1: Use Certbot for LiveKit**
```bash
sudo certbot certonly --standalone \
  -d rtc.mrbiz.in \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email
```

**Option 2: Use LiveKit Cloud**
If using LiveKit Cloud, they provide SSL automatically.

## Step 4: Copy Certificates to Docker

```bash
# Create certificate directories
mkdir -p certbot/conf
mkdir -p certbot/www

# Copy certificates
sudo cp -r /etc/letsencrypt/* certbot/conf/

# Set permissions
sudo chown -R $USER:$USER certbot/
```

## Step 5: Update Nginx Configuration

The Nginx configuration has been updated to:
- Redirect HTTP to HTTPS
- Use SSL certificates
- Proxy to backend services

## Step 6: Restart Services

```bash
# Restart nginx with new configuration
docker compose restart nginx

# Verify SSL
curl https://api.medihub.mrbiz.in/api/health
```

## Step 7: Auto-Renewal Setup

```bash
# Test renewal
sudo certbot renew --dry-run

# Add cron job for auto-renewal
sudo crontab -e

# Add this line:
0 3 * * * certbot renew --quiet && docker compose restart nginx
```

## Verification

### Test API Domain
```bash
# HTTP should redirect to HTTPS
curl -I http://api.medihub.mrbiz.in

# HTTPS should work
curl https://api.medihub.mrbiz.in/api/health

# Check SSL certificate
openssl s_client -connect api.medihub.mrbiz.in:443 -servername api.medihub.mrbiz.in
```

### Test LiveKit Domain
```bash
# Check if domain resolves
nslookup rtc.mrbiz.in

# Test WebSocket connection (if LiveKit is running)
wscat -c wss://rtc.mrbiz.in
```

## LiveKit Configuration

### Update LiveKit Config

Edit `livekit/livekit.yaml`:

```yaml
port: 7880
rtc:
  port_range_start: 50000
  port_range_end: 51000
  use_external_ip: true
  
# Add your domain
turn:
  enabled: true
  domain: rtc.mrbiz.in
  tls_port: 5349
  
# SSL certificates
keys:
  api_key: YOUR_LIVEKIT_API_KEY
  api_secret: YOUR_LIVEKIT_API_SECRET
```

### Update Environment Variables

In `.env`:
```bash
LIVEKIT_HOST=wss://rtc.mrbiz.in
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
```

## Troubleshooting

### Certificate Not Found
```bash
# Check if certificate exists
sudo ls -la /etc/letsencrypt/live/api.medihub.mrbiz.in/

# Regenerate if needed
sudo certbot certonly --standalone -d api.medihub.mrbiz.in --force-renewal
```

### Nginx Won't Start
```bash
# Check nginx configuration
docker compose exec nginx nginx -t

# View logs
docker compose logs nginx
```

### SSL Certificate Expired
```bash
# Renew certificates
sudo certbot renew

# Restart nginx
docker compose restart nginx
```

### Mixed Content Warnings
Ensure all API calls use HTTPS:
```javascript
// In frontend code
const API_URL = 'https://api.medihub.mrbiz.in/api'
```

## Security Checklist

- [ ] SSL certificates installed for api.medihub.mrbiz.in
- [ ] SSL certificates installed for rtc.mrbiz.in
- [ ] HTTP redirects to HTTPS
- [ ] Auto-renewal configured
- [ ] Firewall allows ports 80, 443
- [ ] Strong SSL ciphers configured
- [ ] HSTS header enabled (optional)
- [ ] CORS configured for production domains

## Next Steps

1. **Update Frontend**: Point frontend to `https://api.medihub.mrbiz.in/api`
2. **Test Video Calls**: Verify LiveKit works with `wss://rtc.mrbiz.in`
3. **Monitor Logs**: Check for SSL-related errors
4. **Set Up Monitoring**: Use tools like UptimeRobot to monitor uptime
