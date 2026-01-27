# Backend README

## Behavioral Optimization Platform - Backend

Production-grade Operations Research + AI Engineering platform for behavioral optimization.

### 🏆 Features

- **Real Mathematical Optimization**: Linear programming with PuLP
- **Multi-Objective Optimization**: Balance multiple life goals
- **Complete REST API**: FastAPI with OpenAPI documentation
- **Production-Ready Database**: PostgreSQL with SQLAlchemy ORM
- **Type-Safe**: Full Python type hints and Pydantic validation
- **Async/Await**: Built on asyncio for high performance
- **Docker Support**: Easy deployment with docker-compose

### 📋 Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 6+ (optional)
- Docker & Docker Compose (for containerized deployment)

### 🚀 Quick Start

#### 1. Setup Environment

```bash
# Clone repository
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
make install
make dev

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

#### 2. Database Setup

```bash
# Using Docker (recommended)
docker run -d \
  --name postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=behaviordb \
  -p 5432:5432 \
  postgres:15-alpine

# Run migrations
make db-upgrade
```

#### 3. Run Development Server

```bash
make run
```

Server runs at `http://localhost:8000`

- API Docs: `http://localhost:8000/docs`
- Alternative Docs: `http://localhost:8000/redoc`

### 📚 API Endpoints

#### Authentication
- `POST /api/v1/auth/register` - Create account
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/refresh` - Refresh token

#### Behaviors
- `GET /api/v1/behaviors` - List user's behaviors
- `POST /api/v1/behaviors` - Create behavior
- `GET /api/v1/behaviors/{id}` - Get behavior
- `PUT /api/v1/behaviors/{id}` - Update behavior
- `DELETE /api/v1/behaviors/{id}` - Delete behavior

#### Optimization
- `POST /api/v1/optimization/solve` - Run optimizer
- `GET /api/v1/optimization/history` - Get past runs

#### Health
- `GET /health` - Health check
- `GET /` - API info

### 🧪 Testing

```bash
# Run all tests with coverage
make test

# Run fast (no coverage)
make test-fast

# Run specific test
pytest tests/test_auth.py -v
```

### 🔧 Code Quality

```bash
# Lint code
make lint

# Format code
make format

# Type checking
mypy app/
```

### 🐳 Docker Deployment

```bash
# Build and start services
make docker-build
make docker-up

# View logs
make docker-logs

# Stop services
make docker-down
```

### 📁 Project Structure

```
backend/
├── app/
│   ├── core/               # Configuration, security, exceptions
│   ├── db/                 # Database setup and schema
│   ├── models/             # SQLAlchemy models
│   ├── schemas/            # Pydantic schemas
│   ├── optimization/       # OR engine
│   │   └── solvers/        # Solver implementations
│   ├── api/
│   │   └── v1/             # API routes
│   ├── main.py             # FastAPI app
│   └── __init__.py
├── alembic/                # Database migrations
├── tests/                  # Test suite
├── .env.example            # Environment template
├── requirements.txt        # Dependencies
├── requirements-dev.txt    # Dev dependencies
├── Dockerfile              # Container image
├── docker-compose.yml      # Multi-container setup
├── Makefile                # Development commands
└── README.md               # This file
```

### 🎯 Development Workflow

```bash
# Start development
make setup

# Make changes to code
vim app/models/behavior.py

# Run tests
make test

# Format code
make format

# Commit changes
git add .
git commit -m "feat: add new feature"
```

### 📊 Database Schema

**12 Core Tables:**
- `users` - User accounts
- `behaviors` - User behaviors/habits
- `objectives` - Life goals (health, productivity, etc)
- `constraints` - Optimization constraints
- `optimization_runs` - Solver executions
- `scheduled_behaviors` - Optimization results
- `completion_logs` - Actual completions

**Indexes & Views:**
- Optimized indexes on foreign keys and queries
- Analytics views for reporting
- Automatic updated_at triggers

### 🔐 Security

- JWT token-based authentication
- Bcrypt password hashing
- CORS configuration
- Environment-based secrets
- SQL injection prevention (parameterized queries)
- Rate limiting ready

### 🚧 What's Next

- [ ] Additional constraint types (precedence, mutual exclusion)
- [ ] Non-linear solver (scipy)
- [ ] Heuristic solver (evolutionary algorithms)
- [ ] Advanced analytics
- [ ] AI/MCP server integration
- [ ] Recommendation engine
- [ ] Performance optimizations
- [ ] Comprehensive test suite (>80% coverage)

### 📖 API Documentation

Once running, visit `http://localhost:8000/docs` for interactive API documentation.

### 🤝 Contributing

1. Create feature branch: `git checkout -b feature/name`
2. Make changes and test: `make test`
3. Format code: `make format`
4. Commit: `git commit -am 'Add feature'`
5. Push: `git push origin feature/name`

### 📝 License

MIT License - See LICENSE file for details

### 🆘 Troubleshooting

**Database connection error:**
```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Check DATABASE_URL in .env
```

**Migration issues:**
```bash
# Reset database
make db-reset

# Check Alembic status
alembic current
alembic history
```

**Import errors:**
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### 📧 Support

For issues and questions, open an issue on GitHub.
