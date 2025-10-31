# GitHub Actions Workflows

This directory contains GitHub Actions workflows for deploying the Modal application.

## Available Workflows

### 1. `deploy-production.yml` - Production Deployment

**Purpose**: Main production deployment workflow with comprehensive features and security best practices.

**Triggers**:
- Manual dispatch (`workflow_dispatch`) with environment and force redeploy options
- Repository dispatch for service recovery alerts
- Push to `main` branch when relevant files change

**Features**:
- ✅ Concurrency control to prevent simultaneous deployments
- ✅ Least privilege permissions
- ✅ Path filters to trigger only on relevant changes
- ✅ Comprehensive secret validation
- ✅ Health checks post-deployment
- ✅ Detailed logging and status reporting
- ✅ Service recovery automation
- ✅ Environment variable management

**Usage**:
```bash
# Manual deployment (default production)
# Use GitHub Actions UI to trigger with options

# Automatic triggers:
# - Push to main branch with modal_app.py changes
# - Service down alerts via repository dispatch
```

### 2. `deploy-experimental.yml` - Experimental Deployment

**Purpose**: Alternative deployment method for testing new approaches and experimental features.

**Triggers**:
- Manual dispatch (`workflow_dispatch`) with test mode and version options
- Push to `experimental` or `feature/*` branches

**Features**:
- ✅ Alternative deployment method using `deploy.py`
- ✅ Test/sandbox mode support
- ✅ Configurable Modal SDK version
- ✅ Automatic cleanup for test deployments
- ✅ Detailed validation and error handling

**Requirements**:
- `deploy.py` file must exist in repository root
- Modal SDK authentication via token.toml

**Usage**:
```bash
# Test deployment (sandbox mode)
# Use GitHub Actions UI with test_mode=true

# Production experimental deployment
# Use GitHub Actions UI with test_mode=false
```

## Legacy Workflows

The following workflows are deprecated and should be replaced:

- `modal_deploy.yml` → Use `deploy-production.yml`
- `modal_deploy2.yml` → Use `deploy-experimental.yml`

## Configuration

### Required Secrets

Both workflows require these GitHub repository secrets:

| Secret | Description | Example |
|--------|-------------|---------|
| `MODAL_TOKEN_ID` | Modal API token ID | `token_123...` |
| `MODAL_TOKEN_SECRET` | Modal API token secret | `secret_456...` |
| `MODAL_USER_NAME` | Modal username | `your-username` |

### Optional Secrets

| Secret | Description | Default |
|--------|-------------|---------|
| `MODAL_APP_NAME` | Modal app name | `proxy-app` |
| `SUB_PATH` | Subscription path | `sub` |
| `SERVER_PORT` | Server port | `3000` |
| `UUID` | Unique identifier | Auto-generated |
| `ARGO_DOMAIN` | Cloudflare Argo domain | - |
| `ARGO_AUTH` | Cloudflare Argo auth | - |
| `ARGO_PORT` | Cloudflare Argo port | `8001` |
| `NAME` | Display name | `Modal` |
| `CFIP` | Cloudflare IP | `www.visa.com.tw` |
| `CFPORT` | Cloudflare port | `443` |
| `NEZHA_SERVER` | Nezha server URL | - |
| `NEZHA_KEY` | Nezha authentication key | - |
| `NEZHA_PORT` | Nezha port | - |
| `UPLOAD_URL` | Subscription upload URL | - |
| `PROJECT_URL` | Project URL | - |
| `BOT_TOKEN` | Telegram bot token | - |
| `CHAT_ID` | Telegram chat ID | - |

## Security Best Practices

### Implemented
- ✅ Least privilege permissions (`contents: read`, `actions: write`)
- ✅ Concurrency groups to prevent race conditions
- ✅ Secret validation before deployment
- ✅ Path filters to limit unnecessary triggers
- ✅ Timeout controls for jobs

### Recommendations
- 🔒 Regularly rotate Modal tokens
- 🔒 Use environment-specific secrets
- 🔒 Monitor deployment logs for sensitive data exposure
- 🔒 Implement branch protection rules
- 🔒 Use OIDC for authentication when possible

## Deployment Strategies

### Production Deployments
1. Use `deploy-production.yml` for all production deployments
2. Enable automated recovery via repository dispatch
3. Monitor deployment health checks
4. Keep manual dispatch as fallback option

### Experimental Deployments
1. Use `deploy-experimental.yml` for testing new features
2. Always use test/sandbox mode initially
3. Test on feature branches before merging
4. Clean up test resources automatically

### Branch Strategy
```
main                    → Production deployments (deploy-production.yml)
experimental           → Experimental deployments (deploy-experimental.yml)
feature/*              → Feature testing (deploy-experimental.yml)
```

## Troubleshooting

### Common Issues

1. **Missing Secrets**
   ```
   Error: Missing required secrets: MODAL_TOKEN_ID
   ```
   **Solution**: Add required secrets in GitHub repository settings

2. **Modal Authentication Failed**
   ```
   Error: Modal connection failed
   ```
   **Solution**: Verify MODAL_TOKEN_ID and MODAL_TOKEN_SECRET are correct

3. **App Not Responding**
   ```
   Health check failed - app may not be responding correctly
   ```
   **Solution**: Check Modal app logs, verify configuration

4. **Concurrency Conflicts**
   ```
   Workflow cancelled due to concurrency
   ```
   **Solution**: Wait for current deployment to complete or use force option

### Debug Mode

Enable verbose logging by setting inputs in workflow dispatch:
- `environment: staging` (for testing)
- `force_redeploy: true` (to force redeployment)
- `test_mode: true` (for experimental workflow)

## Migration Guide

### From Legacy Workflows

1. **Replace `modal_deploy.yml`**:
   - Update any references to use `deploy-production.yml`
   - Add new required secrets if missing
   - Test with manual dispatch first

2. **Replace `modal_deploy2.yml`**:
   - Ensure `deploy.py` exists in repository
   - Update any branch references
   - Test with sandbox mode first

### Configuration Updates

1. **Update Actions Versions**:
   - `actions/checkout@v4`
   - `actions/setup-python@v5`

2. **Add Concurrency Controls**:
   - Already implemented in new workflows

3. **Update Permissions**:
   - Set least privilege permissions in workflow files

## Monitoring and Alerting

### Deployment Status
- Check GitHub Actions tab for deployment status
- Monitor Modal app health via provided URLs
- Set up notifications for failed deployments

### Service Recovery
- Repository dispatch automatically handles service alerts
- Configure Uptime Kuma or similar monitoring service
- Set up webhook to trigger repository dispatch

## Contributing

When modifying workflows:
1. Test changes in a feature branch first
2. Use dry-run mode when possible
3. Validate YAML syntax
4. Update documentation
5. Test secret validation logic

For questions or issues, please create an issue in the repository.