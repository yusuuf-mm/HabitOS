# 🚀 QUICK START GUIDE

**Get the Behavioral Optimization Platform running in 5 minutes**

---

## 1️⃣ Start PostgreSQL

```bash
docker run -d \
  --name postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=behaviordb \
  -p 5432:5432 \
  postgres:15-alpine
```

Or use docker-compose:
```bash
cd backend
make docker-up
```

---

## 2️⃣ Setup Backend

```bash
cd backend

# Install dependencies
make install
make dev

# Configure environment
cp .env.example .env

# Setup database
make db-upgrade

# Run server
make run
```

✅ **Backend running at:** http://localhost:8000

---

## 3️⃣ Access API

### **Swagger UI (Interactive)**
```
http://localhost:8000/docs
```

### **ReDoc (Alternative)**
```
http://localhost:8000/redoc
```

### **OpenAPI JSON**
```
http://localhost:8000/openapi.json
```

---

## 4️⃣ Test the API

### **Register User**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "TestPassword123",
    "first_name": "Test",
    "last_name": "User"
  }'
```

### **Login**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPassword123"
  }'
```

### **Create Behavior**
```bash
# Get access token from login response, then:
curl -X POST "http://localhost:8000/api/v1/behaviors" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Morning Exercise",
    "category": "health",
    "min_duration": 20,
    "typical_duration": 30,
    "max_duration": 45,
    "impacts": {
      "health": 0.9,
      "productivity": 0.3,
      "learning": 0.0,
      "wellness": 0.8,
      "social": 0.1
    }
  }'
```

### **Run Optimizer**
```bash
curl -X POST "http://localhost:8000/api/v1/optimization/solve" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2026-01-27",
    "end_date": "2026-02-03",
    "time_periods": 7
  }'
```

---

## 5️⃣ Setup Frontend (Optional)

```bash
cd frontend

# Install dependencies
npm install
# or
bun install

# Run development server
npm run dev
```

✅ **Frontend running at:** http://localhost:5173

---

## 🔧 Common Commands

### **Backend**
```bash
cd backend

# Development
make run               # Start dev server
make test             # Run tests
make lint             # Check code
make format           # Format code

# Database
make db-upgrade       # Apply migrations
make db-downgrade     # Rollback migrations
make db-reset         # Reset database

# Docker
make docker-build     # Build image
make docker-up        # Start services
make docker-down      # Stop services
make docker-logs      # View logs
```

### **Frontend**
```bash
cd frontend

npm run dev           # Start dev server
npm run build         # Build for production
npm run test          # Run tests
npm run lint          # Lint code
```

---

## 📋 API Endpoints

### **Authentication**
```
POST   /api/v1/auth/register         Register user
POST   /api/v1/auth/login            Login user
POST   /api/v1/auth/refresh          Refresh token
```

### **Behaviors**
```
GET    /api/v1/behaviors             List behaviors
POST   /api/v1/behaviors             Create behavior
GET    /api/v1/behaviors/{id}        Get behavior
PUT    /api/v1/behaviors/{id}        Update behavior
DELETE /api/v1/behaviors/{id}        Delete behavior
```

### **Optimization**
```
POST   /api/v1/optimization/solve    Run optimizer
GET    /api/v1/optimization/history  Get past runs
```

### **Health**
```
GET    /health                       Health check
GET    /                             API info
```

---

## 🎯 Architecture Overview

```
Frontend (React)
      ↓
      ↓ (HTTP/REST)
      ↓
Backend (FastAPI)
      ↓
      ↓ (SQLAlchemy ORM)
      ↓
Database (PostgreSQL)

Optimization Engine (PuLP)
      ↓
     └→ Linear Programming Solver
```

---

## 🔑 Key Features

✅ **Authentication**
- JWT tokens
- Bcrypt hashing
- Refresh tokens

✅ **Optimization**
- Linear programming
- Multi-objective
- Constraint satisfaction

✅ **Database**
- PostgreSQL
- SQLAlchemy ORM
- Migrations (Alembic)

✅ **API**
- REST endpoints
- OpenAPI spec
- Error handling

---

## 📚 Documentation

- **Main README:** See `/README.md`
- **Backend README:** See `/backend/README.md`
- **Implementation Summary:** See `/IMPLEMENTATION_SUMMARY.md`
- **Complete Checklist:** See `/COMPLETE_CHECKLIST.md`

---

## 🆘 Troubleshooting

### **Port Already in Use**
```bash
# Find and kill process
lsof -i :8000
kill -9 PID

# Or use different port
make run PORT=8001
```

### **Database Connection Error**
```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Check DATABASE_URL in .env
cat backend/.env | grep DATABASE_URL
```

### **Import Errors**
```bash
cd backend
pip install -r requirements.txt --force-reinstall
```

### **Migration Issues**
```bash
cd backend
alembic current        # Check current version
alembic history        # View migration history
make db-reset          # Reset and upgrade
```

---

## 🎉 You're Ready!

1. Backend running? ✅ http://localhost:8000/docs
2. Database ready? ✅ Created with schema
3. API working? ✅ Try the endpoints
4. Frontend ready? ✅ (Optional) http://localhost:5173

**Start building!** 🚀

---

## 💡 Pro Tips

### **Use Swagger UI for Testing**
Visit http://localhost:8000/docs to test endpoints interactively

### **Check Database**
```bash
# Connect to PostgreSQL
psql -h localhost -U user -d behaviordb

# List tables
\dt

# Query users
SELECT * FROM users;
```

### **View Logs**
```bash
# Backend logs (when running)
# They'll appear in the terminal

# Docker logs
make docker-logs
```

### **Reset Everything**
```bash
# Stop all services
make docker-down

# Reset database
make db-reset

# Restart
make docker-up
make run
```

---

**Questions? Check the README files or API documentation!** 📚
