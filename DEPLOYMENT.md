# Rule Intelligence Engine - Deployment Guide

## 🚀 Quick Start (One-Line Deployment)

```bash
docker-compose up -d
```

That's it! The entire Rule Intelligence Engine stack will be up and running.

## 📋 What Gets Deployed

### Services
- **API Server** (`api`) - FastAPI application on port 8000
- **PostgreSQL** (`db`) - Database on port 5432
- **Redis** (`redis`) - Cache on port 6379
- **Celery Worker** (`celery_worker`) - Background task processing
- **PgAdmin** (`pgadmin`) - Database management UI on port 5050

### Features
✅ Automatic database initialization  
✅ Model training on first run  
✅ Health checks for all services  
✅ Volume persistence for data and models  
✅ Network isolation  
✅ Automatic service restart  

## 📊 Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| **API Dashboard** | http://localhost:8000 | - |
| **API Docs** | http://localhost:8000/docs | - |
| **PgAdmin** | http://localhost:5050 | admin@rie.local / admin_password |
| **PostgreSQL** | localhost:5432 | rie_user / rie_password |
| **Redis** | localhost:6379 | - |

## 🔧 Common Commands

### Start All Services
```bash
docker-compose up -d
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f celery_worker
docker-compose logs -f db
```

### Stop All Services
```bash
docker-compose down
```

### Stop and Remove Volumes (Clean Reset)
```bash
docker-compose down -v
```

### Rebuild Images
```bash
docker-compose build --no-cache
```

### Scale Services
```bash
# Scale Celery workers
docker-compose up -d --scale celery_worker=3
```

### Access Container Shell
```bash
docker-compose exec api bash
docker-compose exec db psql -U rie_user -d rule_intelligence_engine
```

## 📈 Monitoring

### Check Service Status
```bash
docker-compose ps
```

### View Resource Usage
```bash
docker stats
```

### Check Health
```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## 🗄️ Database Management

### Access PostgreSQL
```bash
docker-compose exec db psql -U rie_user -d rule_intelligence_engine
```

### Backup Database
```bash
docker-compose exec db pg_dump -U rie_user rule_intelligence_engine > backup.sql
```

### Restore Database
```bash
docker-compose exec -T db psql -U rie_user rule_intelligence_engine < backup.sql
```

## 🔐 Production Configuration

### Environment Variables
Create a `.env.prod` file:

```env
DATABASE_URL=postgresql://rie_user:secure_password@db:5432/rule_intelligence_engine
REDIS_URL=redis://redis:6379/0
ENV=production
WORKERS=4
DEBUG=false
```

Load it with:
```bash
docker-compose --env-file .env.prod up -d
```

### Port Mapping
Update ports in `docker-compose.yml`:

```yaml
api:
  ports:
    - "80:8000"  # Public HTTP
    - "443:8000" # HTTPS (with reverse proxy)
```

## 🧪 Testing

### Run Tests Inside Container
```bash
docker-compose exec api pytest tests/ -v
```

### Test API Endpoints
```bash
curl -X POST http://localhost:8000/v1/feedback/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "feedback_text": "Revenue should exclude discounts",
    "feedback_id": "test-1",
    "workspace_id": "default",
    "schema_context": {
      "available_tables": ["orders"],
      "available_columns": ["revenue", "discount"]
    }
  }'
```

## 🐛 Troubleshooting

### Service Won't Start
```bash
# Check logs
docker-compose logs api

# Rebuild and restart
docker-compose build --no-cache api
docker-compose up -d api
```

### Database Connection Error
```bash
# Verify database is running
docker-compose ps db

# Check connection
docker-compose exec db pg_isready -U rie_user
```

### Port Already in Use
```bash
# Change port in docker-compose.yml
# Or kill the process:
lsof -i :8000
kill -9 <PID>
```

### Out of Memory
```bash
# Increase Docker memory limit
# Or reduce workers:
sed -i 's/WORKERS=4/WORKERS=2/' .env
docker-compose restart api
```

## 📦 Volumes Explained

| Volume | Purpose | Path |
|--------|---------|------|
| `postgres_data` | Database persistence | `/var/lib/postgresql/data` |
| `redis_data` | Cache persistence | `/data` |
| `./app` | Application code (dev) | `/app/app` |
| `./rie_ml` | ML models & data (dev) | `/app/rie_ml` |
| `./logs` | Application logs | `/app/logs` |

## 🔄 Updating the Application

### Pull Latest Code
```bash
git pull origin main
```

### Rebuild and Restart
```bash
docker-compose build --no-cache api
docker-compose up -d api
```

### Zero-Downtime Update (with load balancer)
```bash
# Start new container on different port
docker-compose up -d --scale api=2
# Route traffic to new container
# Stop old container
docker-compose down api_1
```

## 📊 Performance Tuning

### Database Optimization
```sql
CREATE INDEX idx_feedback_workspace ON feedback(workspace_id);
CREATE INDEX idx_suggestion_status ON rule_suggestions(status);
CREATE INDEX idx_rules_term ON rules(business_term);
```

### Redis Cache Optimization
```bash
docker-compose exec redis redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### API Worker Optimization
Update Dockerfile:
```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

## 🔐 Security Best Practices

1. **Change Default Passwords**
   - Update `docker-compose.yml` credentials
   - Use `.env` files for sensitive data
   - Never commit credentials to version control

2. **Enable SSL/TLS**
   - Use reverse proxy (Nginx, Traefik)
   - Configure HTTPS certificates

3. **Network Security**
   - Only expose necessary ports
   - Use VPC/network isolation
   - Implement firewall rules

4. **Database Security**
   - Enable SQL encryption
   - Use strong passwords
   - Implement connection pooling
   - Regular backups

## 📝 Logging

### View Structured Logs
```bash
docker-compose logs --tail=100 api | grep ERROR
```

### Save Logs to File
```bash
docker-compose logs > logs_$(date +%Y%m%d_%H%M%S).txt
```

## 🚀 Deployment Checklist

- [ ] Clone repository
- [ ] Install Docker & Docker Compose
- [ ] Configure `.env` file with production values
- [ ] Run `docker-compose up -d`
- [ ] Verify all services are running: `docker-compose ps`
- [ ] Test API: `curl http://localhost:8000/health`
- [ ] Access dashboard: `http://localhost:8000`
- [ ] Configure backups
- [ ] Set up monitoring
- [ ] Configure logging aggregation
- [ ] Test disaster recovery

## 📞 Support

For issues or questions:
1. Check logs: `docker-compose logs -f`
2. Review troubleshooting section above
3. Consult documentation at `/docs/specification/`
4. Open an issue on GitLab

---

**Last Updated:** August 24, 2026  
**Version:** 1.0.0  
**Status:** Production Ready ✅
