# Pre-Commit Checklist

Use this checklist before pushing code to ensure the CI/CD pipeline will pass.

## ✅ Before Every Commit

### 1. Code Quality
- [ ] No debugging code left (console.log, print statements)
- [ ] No commented-out code blocks
- [ ] No TODO comments without issue references
- [ ] Code follows project style guide

### 2. Frontend Checks
```bash
cd frontend

# Lint check
npm run lint

# Run tests
npm test

# Build verification
npm run build
```

- [ ] ESLint passes with no errors
- [ ] All frontend tests pass
- [ ] Frontend builds without errors
- [ ] No TypeScript type errors

### 3. Backend Checks
```bash
cd backend

# Lint check (optional warning)
python -m ruff check app/

# Unit tests
make test-fast

# Integration tests
python -m pytest tests_integration/ -v
```

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] No import errors
- [ ] Database migrations applied locally

### 4. Environment Files
- [ ] `.env` not committed (in .gitignore)
- [ ] `.env.example` updated if new variables added
- [ ] No secrets in code or config files

### 5. Documentation
- [ ] README updated if public API changed
- [ ] Comments added for complex logic
- [ ] OpenAPI spec updated if endpoints changed

---

## ⚡ Quick Test All

From project root:
```bash
# Run all tests at once
npm test

# Or run them separately
npm run test:frontend
npm run test:backend:unit
npm run test:backend:integration
```

---

## 🚨 Common Issues

### "Module not found" error
```bash
# Frontend
cd frontend && npm install

# Backend
cd backend && pip install -r requirements.txt -r requirements-dev.txt
```

### Database migration errors
```bash
cd backend
make db-upgrade  # Apply latest migrations
```

### Test database issues
```bash
# Integration tests use isolated test DB
# If tests fail with DB errors, check DATABASE_URL in .env
```

---

## 📝 Commit Message Format

Use conventional commits:
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```bash
git commit -m "feat(auth): add password reset functionality"
git commit -m "fix(optimization): resolve time slot constraint bug"
git commit -m "docs(api): update OpenAPI spec for behaviors endpoint"
git commit -m "test(frontend): add dashboard component tests"
```

---

## 🔄 Branch Strategy

### Feature Development
```bash
# 1. Create feature branch
git checkout -b feat/your-feature-name

# 2. Make changes and commit
git add .
git commit -m "feat: your feature description"

# 3. Push to GitHub
git push origin feat/your-feature-name

# 4. Create Pull Request
# GitHub will run tests automatically

# 5. After PR approval, merge to main
# GitHub will run tests + deploy to production
```

### Hotfix
```bash
# 1. Create hotfix branch from main
git checkout main
git pull
git checkout -b hotfix/issue-description

# 2. Fix and test locally
# ... make fixes ...

# 3. Run tests
npm test

# 4. Commit and push
git commit -m "fix: issue description"
git push origin hotfix/issue-description

# 5. Create PR for immediate review
```

---

## 🎯 Pull Request Checklist

Before creating a PR:

- [ ] All tests pass locally
- [ ] Code reviewed by yourself first
- [ ] Branch is up to date with main
- [ ] PR description explains what and why
- [ ] Screenshots added (if UI changes)
- [ ] Breaking changes documented

---

## 🚀 Ready to Push?

If all checkboxes above are ✅, you're good to push!

```bash
git push origin your-branch-name
```

Then create a Pull Request on GitHub and watch the CI/CD pipeline work its magic! 🎉

---

## 📚 Resources

- [GitHub Actions Workflow](.github/workflows/ci-cd.yml)
- [CI/CD Setup Guide](.github/CI_CD_SETUP.md)
- [Contributing Guidelines](../CONTRIBUTING.md) *(if exists)*
