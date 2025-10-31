#!/bin/bash

# Workflow validation script
# Validates GitHub Actions workflow syntax and checks for common issues

set -e

echo "🔍 Validating GitHub Actions workflows..."
echo "========================================="

# Check if yamllint is available
if ! command -v yamllint &> /dev/null; then
    echo "⚠️  yamllint not found. Skipping yamllint checks."
    echo "   Install with: pip install yamllint (in virtual environment)"
fi

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo "⚠️  jq not found. Skipping JSON checks."
    echo "   Install with: sudo apt-get install jq"
fi

WORKFLOW_DIR=".github/workflows"
VALIDATION_PASSED=true

# Function to validate YAML syntax
validate_yaml() {
    local file=$1
    echo "📋 Validating $file..."
    
    if python3 -c "import yaml; yaml.safe_load(open('$file'))" 2>/dev/null; then
        echo "✅ YAML syntax valid"
    else
        echo "❌ YAML syntax error in $file"
        VALIDATION_PASSED=false
    fi
    
    # Check with yamllint if available
    if command -v yamllint &> /dev/null; then
        if yamllint -d relaxed "$file" 2>/dev/null; then
            echo "✅ yamllint passed"
        else
            echo "⚠️  yamllint warnings (non-critical)"
        fi
    fi
}

# Function to check workflow-specific issues
check_workflow_issues() {
    local file=$1
    echo "🔎 Checking workflow-specific issues in $file..."
    
    # Check for required fields
    if ! grep -q "^name:" "$file"; then
        echo "❌ Missing 'name' field"
        VALIDATION_PASSED=false
    fi
    
    if ! grep -q "^on:" "$file"; then
        echo "❌ Missing 'on:' field (triggers)"
        VALIDATION_PASSED=false
    fi
    
    if ! grep -q "^jobs:" "$file"; then
        echo "❌ Missing 'jobs:' field"
        VALIDATION_PASSED=false
    fi
    
    # Check for deprecated actions
    if grep -q "actions/checkout@v[12]" "$file"; then
        echo "⚠️  Using deprecated checkout action version"
    fi
    
    if grep -q "actions/setup-python@v[1-3]" "$file"; then
        echo "⚠️  Using deprecated setup-python action version"
    fi
    
    # Check for secrets exposure (only flag if secrets are directly echoed)
    if grep -q "echo.*\${{ secrets\." "$file"; then
        echo "❌ Potential secret exposure in echo statements"
        VALIDATION_PASSED=false
    fi
    
    # Check for missing concurrency
    if ! grep -q "^concurrency:" "$file"; then
        echo "⚠️  Missing concurrency control (recommended for deployment workflows)"
    fi
    
    # Check for missing permissions
    if ! grep -q "^permissions:" "$file"; then
        echo "⚠️  Missing permissions (recommended for security)"
    fi
    
    echo "✅ Workflow-specific checks completed"
}

# Function to validate secrets reference
validate_secrets() {
    local file=$1
    echo "🔐 Validating secrets references in $file..."
    
    # Extract all secrets references
    local secrets=$(grep -o 'secrets\.[A-Z_][A-Z0-9_]*' "$file" | sort | uniq)
    
    if [[ -n "$secrets" ]]; then
        echo "📋 Found secrets references:"
        echo "$secrets" | sed 's/secrets\./  - /'
        
        # Check for common required secrets
        local required_secrets=("MODAL_TOKEN_ID" "MODAL_TOKEN_SECRET" "MODAL_USER_NAME")
        local missing_secrets=""
        
        for secret in "${required_secrets[@]}"; do
            if ! grep -q "secrets\.$secret" "$file"; then
                missing_secrets="$missing_secrets $secret"
            fi
        done
        
        if [[ -n "$missing_secrets" ]]; then
            echo "⚠️  Missing recommended secrets:$missing_secrets"
        fi
    else
        echo "ℹ️  No secrets references found"
    fi
    
    echo "✅ Secrets validation completed"
}

# Main validation loop
if [[ -d "$WORKFLOW_DIR" ]]; then
    for workflow in "$WORKFLOW_DIR"/*.yml; do
        if [[ -f "$workflow" ]]; then
            echo ""
            echo "========================================="
            basename "$workflow"
            echo "========================================="
            
            validate_yaml "$workflow"
            check_workflow_issues "$workflow"
            validate_secrets "$workflow"
        fi
    done
else
    echo "❌ Workflow directory not found: $WORKFLOW_DIR"
    exit 1
fi

echo ""
echo "========================================="
if [[ "$VALIDATION_PASSED" == true ]]; then
    echo "🎉 All workflow validations passed!"
    exit 0
else
    echo "❌ Some validations failed. Please review the issues above."
    exit 1
fi