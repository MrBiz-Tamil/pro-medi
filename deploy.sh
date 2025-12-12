# Deploy script for server
# This script should be placed on your server

#!/bin/bash

set -e  # Exit on error

PROJECT_DIR="/home/ubuntu/pro-medi"  # Change this to your project path
BRANCH="${1:-development}"

echo "🚀 Starting deployment..."

# Navigate to project directory
cd "$PROJECT_DIR"

# Pull latest changes
echo "📥 Pulling latest changes from $BRANCH..."
git fetch origin
git reset --hard origin/$BRANCH

# Stop services
echo "🛑 Stopping services..."
docker compose down

# Build and start services
echo "🔨 Building and starting services..."
docker compose up -d --build db redis api livekit

# Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 15

# Verify deployment
echo "✅ Verifying deployment..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API is healthy!"
else
    echo "❌ API health check failed!"
    docker compose logs api
    exit 1
fi

# Clean up old images
echo "🧹 Cleaning up old Docker images..."
docker image prune -f

# Show running containers
echo "📊 Running containers:"
docker compose ps

echo "🎉 Deployment completed successfully!"
