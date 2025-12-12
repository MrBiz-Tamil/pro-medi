# CI/CD Pipeline Setup Guide

## Overview
This project uses GitHub Actions for automated testing and deployment to your production server.

## Workflows

### 1. `deploy.yml` - Production Deployment
**Triggers**: Push to `main`, `master`, or `development` branches
**Steps**:
1. Run tests
2. Build Docker images
3. Deploy to server via SSH
4. Verify deployment

### 2. `test.yml` - Testing & Build Validation
**Triggers**: Pull requests and pushes
**Steps**:
1. Lint code
2. Run unit tests
3. Build Docker images
4. Run integration tests

## Setup Instructions

### Step 1: Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add the following secrets:

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `SERVER_HOST` | Your server IP or domain | `123.45.67.89` or `server.example.com` |
| `SERVER_USER` | SSH username | `ubuntu` or `root` |
| `SSH_PRIVATE_KEY` | SSH private key for authentication | Contents of `~/.ssh/id_rsa` |
| `SERVER_PORT` | SSH port (optional, default: 22) | `22` |
| `DEPLOY_PATH` | Path to project on server | `/home/ubuntu/pro-medi` |

### Step 2: Generate SSH Key for Deployment

On your **local machine**:

```bash
# Generate SSH key pair
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_deploy_key

# Copy public key to server
ssh-copy-id -i ~/.ssh/github_deploy_key.pub user@your-server-ip

# Display private key (copy this to GitHub secret)
cat ~/.ssh/github_deploy_key
```

### Step 3: Prepare Server

On your **server**:

```bash
# Clone repository
cd /home/ubuntu  # or your preferred directory
git clone https://github.com/MrBiz-Tamil/pro-medi.git
cd pro-medi

# Create .env file with production values
cp .env.production.example .env
nano .env  # Edit with your production credentials

# Test manual deployment
docker compose up -d db redis api livekit
```

### Step 4: Test the Pipeline

1. **Make a change** to your code
2. **Commit and push** to development branch:
   ```bash
   git add .
   git commit -m "Test CI/CD pipeline"
   git push origin development
   ```
3. **Watch the workflow** in GitHub Actions tab
4. **Verify deployment** on your server

## Workflow Details

### Deploy Workflow (`deploy.yml`)

```yaml
# Runs on push to main/development branches
on:
  push:
    branches: [main, development]
```

**What it does**:
1. ✅ Runs tests
2. ✅ Builds Docker images
3. ✅ SSHs into your server
4. ✅ Pulls latest code
5. ✅ Rebuilds and restarts containers
6. ✅ Verifies deployment health

### Test Workflow (`test.yml`)

```yaml
# Runs on pull requests
on:
  pull_request:
    branches: [main, development]
```

**What it does**:
1. ✅ Lints Python code
2. ✅ Runs unit tests
3. ✅ Builds Docker images
4. ✅ Runs integration tests
5. ✅ Validates API health

## Deployment Process

### Automatic Deployment
```bash
# On your local machine
git add .
git commit -m "Your changes"
git push origin development

# GitHub Actions will automatically:
# 1. Run tests
# 2. Build images
# 3. Deploy to server
# 4. Verify deployment
```

### Manual Deployment Trigger
You can also trigger deployment manually from GitHub:
1. Go to Actions tab
2. Select "Deploy to Production Server"
3. Click "Run workflow"
4. Choose branch and run

## Monitoring Deployments

### View Workflow Status
- GitHub → Actions tab
- Click on workflow run to see details
- View logs for each step

### Check Server Deployment
```bash
# SSH into server
ssh user@your-server-ip

# Check running containers
docker compose ps

# View logs
docker compose logs -f api

# Test API
curl http://localhost:8000/health
```

## Rollback Procedure

If deployment fails or has issues:

```bash
# SSH into server
ssh user@your-server-ip
cd /home/ubuntu/pro-medi

# Rollback to previous commit
git log --oneline  # Find previous commit hash
git reset --hard <previous-commit-hash>

# Restart services
docker compose down
docker compose up -d db redis api livekit
```

## Environment-Specific Deployments

### Development Branch → Staging Server
```yaml
# In deploy.yml, add staging environment
deploy-staging:
  if: github.ref == 'refs/heads/development'
  # Deploy to staging server
```

### Main Branch → Production Server
```yaml
deploy-production:
  if: github.ref == 'refs/heads/main'
  # Deploy to production server
```

## Customization

### Add More Tests
Edit `.github/workflows/test.yml`:
```yaml
- name: Run tests
  run: |
    pytest tests/ --cov=. --cov-report=xml
```

### Add Database Migrations
Edit `.github/workflows/deploy.yml`:
```yaml
- name: Run migrations
  run: |
    docker compose exec -T api alembic upgrade head
```

### Add Slack Notifications
```yaml
- name: Slack notification
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

## Troubleshooting

### SSH Connection Failed
- Verify `SSH_PRIVATE_KEY` is correct
- Check server firewall allows SSH
- Ensure public key is in `~/.ssh/authorized_keys` on server

### Docker Build Failed
- Check Dockerfile syntax
- Verify all dependencies in requirements.txt
- Review build logs in GitHub Actions

### Deployment Verification Failed
- Check if services started: `docker compose ps`
- View logs: `docker compose logs api`
- Verify .env file has correct values

### Permission Denied
```bash
# On server, ensure user has Docker permissions
sudo usermod -aG docker $USER
```

## Best Practices

1. **Always test locally first**
   ```bash
   docker compose up -d --build
   ```

2. **Use pull requests** for code review before merging to main

3. **Monitor deployments** in GitHub Actions

4. **Keep secrets secure** - never commit .env files

5. **Regular backups**
   ```bash
   # Backup database before deployment
   docker compose exec db pg_dump -U medhub_user medhub_db > backup.sql
   ```

6. **Use staging environment** for testing before production

## Next Steps

- [ ] Set up GitHub secrets
- [ ] Generate and configure SSH keys
- [ ] Test deployment to development branch
- [ ] Configure production deployment
- [ ] Set up monitoring and alerts
- [ ] Configure database backups
- [ ] Add Slack/email notifications
