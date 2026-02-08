# GitHub Actions CI/CD Pipeline Setup

This document explains how to set up and use the GitHub Actions CI/CD pipeline for HabitOS.

## 📋 Overview

The CI/CD pipeline automatically:
1. ✅ **Runs frontend tests** (linting + unit tests + build verification)
2. ✅ **Runs backend unit tests** (with coverage reporting)
3. ✅ **Runs backend integration tests** (against PostgreSQL + Redis)
4. 🚀 **Deploys to Render** (only on successful builds to `main` branch)
5. 🏥 **Performs health checks** (verifies deployment is successful)

## 🏗️ Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Trigger: Push to main/develop OR Pull Request              │
└─────────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────┴────────────────────┐
        │  PARALLEL EXECUTION (3 jobs)           │
        │                                         │
  ┌─────┴─────┐    ┌──────────────┐    ┌────────┴────────┐
  │ Frontend  │    │   Backend    │    │    Backend      │
  │   Tests   │    │  Unit Tests  │    │  Integration    │
  │           │    │              │    │     Tests       │
  └─────┬─────┘    └──────┬───────┘    └────────┬────────┘
        │                 │                      │
        └─────────────────┴──────────────────────┘
                            ↓
              ┌─────────────────────────┐
              │  All tests passed?      │
              └─────────────────────────┘
                     ↓ YES (main branch only)
              ┌─────────────────────────┐
              │  Deploy to Render       │
              └─────────────────────────┘
                            ↓
              ┌─────────────────────────┐
              │  Health Check           │
              └─────────────────────────┘
```

## 🔧 Setup Instructions

### Step 1: Enable GitHub Actions

GitHub Actions is enabled by default for all repositories. The workflow will automatically run when you push the `.github/workflows/ci-cd.yml` file.

### Step 2: Configure GitHub Secrets

To enable deployment to Render, you need to add two secrets to your GitHub repository:

1. **Navigate to Repository Settings**:
   - Go to your GitHub repository
   - Click **Settings** → **Secrets and variables** → **Actions**
   - Click **New repository secret**

2. **Add Required Secrets**:

   **Secret 1: `RENDER_DEPLOY_HOOK_URL`** (Required for deployment)
   - **How to get it**:
     1. Go to your Render dashboard: https://dashboard.render.com
     2. Select your `habitos` web service
     3. Go to **Settings** → **Deploy Hook**
     4. Click **Create Deploy Hook**
     5. Copy the URL (looks like: `https://api.render.com/deploy/srv-xxxxx?key=xxxxx`)
   - **Add to GitHub**:
     - Name: `RENDER_DEPLOY_HOOK_URL`
     - Value: `<paste the deploy hook URL>`

   **Secret 2: `RENDER_APP_URL`** (Optional, for health checks)
   - **How to get it**:
     - It's your Render app URL: `https://habitos-bnnl.onrender.com`
   - **Add to GitHub**:
     - Name: `RENDER_APP_URL`
     - Value: `https://habitos-bnnl.onrender.com` (or your custom domain)

### Step 3: Verify Service Configuration

The integration tests require PostgreSQL and Redis. These are automatically provided by GitHub Actions using Docker containers (see the `services` section in the workflow).

No additional configuration is needed!

### Step 4: Test the Pipeline

1. **Push to a feature branch**:
   ```bash
   git checkout -b test-ci
   git add .github/workflows/ci-cd.yml
   git commit -m "Add CI/CD pipeline"
   git push origin test-ci
   ```

2. **Create a Pull Request**:
   - The pipeline will run all tests but **skip deployment**

3. **Merge to main**:
   - After merging, the pipeline will run tests **and deploy** to Render

4. **Monitor the pipeline**:
   - Go to your GitHub repository
   - Click the **Actions** tab
   - You'll see all workflow runs and their status

## 📊 Pipeline Jobs Explained

### 1. Frontend Tests (`frontend-tests`)

**What it does**:
- Installs Node.js dependencies
- Runs ESLint for code quality
- Executes Vitest unit tests
- Builds the production frontend bundle
- Uploads build artifacts

**Runs in**: ~2-3 minutes

**Example output**:
```
✓ src/test/App.test.tsx (3 tests)
✓ src/test/Login.test.tsx (5 tests)
✓ src/test/Dashboard.test.tsx (4 tests)

Tests: 12 passed (12 total)
```

### 2. Backend Unit Tests (`backend-unit-tests`)

**What it does**:
- Installs Python dependencies
- Runs Ruff linter
- Executes pytest unit tests (tests/ folder)
- Generates coverage report
- Uploads coverage to Codecov (optional)

**Runs in**: ~1-2 minutes

**Example output**:
```
tests/test_api_v1.py::test_health_check PASSED
tests/test_api_v1.py::test_auth_flow PASSED

---------- coverage: platform linux, python 3.11 -----------
Name                      Stmts   Miss  Cover
---------------------------------------------
app/main.py                  45      2    96%
app/auth/service.py          89      5    94%
...
TOTAL                       892     38    96%
```

### 3. Backend Integration Tests (`backend-integration-tests`)

**What it does**:
- Spins up PostgreSQL and Redis containers
- Installs Python dependencies
- Runs database migrations (Alembic)
- Executes integration tests (tests_integration/ folder)
- Tests real API flows against live databases

**Runs in**: ~3-5 minutes

**Services**:
- **PostgreSQL 15** on port 5432
- **Redis 7** on port 6379

**Example output**:
```
tests_integration/test_auth.py::test_register_login_flow PASSED
tests_integration/test_behaviors.py::test_create_behavior PASSED
tests_integration/test_optimization.py::test_solve_optimization PASSED
tests_integration/test_schedule.py::test_generate_schedule PASSED
tests_integration/test_analytics.py::test_dashboard_stats PASSED

Tests: 28 passed (28 total)
```

### 4. Deploy (`deploy`)

**What it does**:
- **Only runs on**: Push to `main` branch
- **Only runs if**: All tests passed
- Triggers Render deployment via webhook
- Waits for deployment to complete
- Performs health check (retries for up to 5 minutes)

**Runs in**: ~5-10 minutes (Render build time)

**Example output**:
```
🚀 Triggering deployment to Render...
✅ Deployment triggered successfully!
⏳ Waiting 30 seconds for deployment to start...
🏥 Performing health check on https://habitos-bnnl.onrender.com/api/health...
✅ Health check passed! Application is healthy.
```

### 5. Summary (`summary`)

**What it does**:
- Runs after all jobs complete
- Reports overall pipeline status
- Fails if any test job failed

## 🎯 Workflow Triggers

The pipeline runs on:

### Push Events
- **Branches**: `main`, `develop`
- **Behavior**: Runs all tests + deploys (main only)

### Pull Request Events
- **Target branches**: `main`, `develop`
- **Behavior**: Runs all tests, skips deployment

### Manual Trigger (Optional)
You can manually trigger the workflow:
1. Go to **Actions** tab
2. Select **CI/CD Pipeline** workflow
3. Click **Run workflow**

## 🔍 Monitoring and Debugging

### Viewing Logs

1. **Go to Actions tab** in GitHub
2. **Click on a workflow run**
3. **Click on a job** to see logs
4. **Expand steps** to see detailed output

### Common Issues

#### ❌ Frontend tests failing
- **Cause**: ESLint errors or test failures
- **Fix**: Run `npm run lint` and `npm test` locally to debug

#### ❌ Backend unit tests failing
- **Cause**: Import errors or test assertion failures
- **Fix**: Run `make test` in backend/ locally

#### ❌ Integration tests failing
- **Cause**: Database connection issues or migration errors
- **Fix**: Check `DATABASE_URL` is correct, run migrations locally

#### ❌ Deployment failing
- **Cause**: `RENDER_DEPLOY_HOOK_URL` not set or invalid
- **Fix**: Verify the secret is correctly configured in GitHub Settings

#### ❌ Health check failing
- **Cause**: Application not starting on Render
- **Fix**: Check Render logs for errors, verify environment variables

## 🔐 Security Best Practices

### Secrets Management

- ✅ **Never commit secrets** to the repository
- ✅ Store all sensitive data in **GitHub Secrets**
- ✅ Use different secrets for **production** vs **CI/CD**
- ✅ Rotate deploy hooks periodically

### Test Environment Isolation

- Integration tests use **isolated test databases**
- Test credentials are **not used in production**
- Each test run gets a **fresh database**

## 📈 Code Coverage

### Viewing Coverage Reports

Coverage reports are automatically uploaded to Codecov (if configured):

1. **Sign up at**: https://codecov.io
2. **Connect your repository**
3. **View coverage**: https://codecov.io/gh/yusuuf-mm/HabitOS

### Coverage Badges

Add to your README:
```markdown
[![codecov](https://codecov.io/gh/yusuuf-mm/HabitOS/branch/main/graph/badge.svg)](https://codecov.io/gh/yusuuf-mm/HabitOS)
```

## 🚀 Advanced Configuration

### Customizing Test Timeouts

Edit `.github/workflows/ci-cd.yml`:
```yaml
- name: Run integration tests
  timeout-minutes: 15  # Add this line
  run: python -m pytest tests_integration/ -v
```

### Running Tests in Parallel

Backend tests already run in parallel by default. To adjust:
```yaml
- name: Run backend tests
  run: |
    pytest tests/ -v -n auto  # Uses all CPU cores
```

### Deployment Notifications

Add Slack/Discord notifications on deployment:
```yaml
- name: Notify Slack
  uses: slackapi/slack-github-action@v1
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK }}
    payload: |
      {
        "text": "✅ HabitOS deployed to production!"
      }
```

## 🎓 Next Steps

1. ✅ **Verify pipeline works**: Push a commit and watch the Actions tab
2. ✅ **Add branch protection**: Require passing tests before merging PRs
3. ✅ **Enable Codecov**: Track test coverage over time
4. ✅ **Add status badges**: Show build status in README.md

### Branch Protection

1. Go to **Settings** → **Branches**
2. Add rule for `main` branch:
   - ✅ Require status checks to pass before merging
   - ✅ Select: `Frontend Tests`, `Backend Unit Tests`, `Backend Integration Tests`
   - ✅ Require branches to be up to date

This ensures no code is merged to `main` without passing all tests!

## 📚 Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Render Deploy Hooks](https://render.com/docs/deploy-hooks)
- [Pytest Documentation](https://docs.pytest.org/)
- [Vitest Documentation](https://vitest.dev/)

---

**Questions?** Check the [GitHub Actions logs](https://github.com/yusuuf-mm/HabitOS/actions) or open an issue!
