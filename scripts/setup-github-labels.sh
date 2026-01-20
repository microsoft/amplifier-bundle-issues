#!/bin/bash
# Setup GitHub labels for amplifier issue tracking
# Usage: ./setup-github-labels.sh [repo]
# Default repo: microsoft-amplifier/amplifier-shared

set -e

REPO="${1:-microsoft-amplifier/amplifier-shared}"

echo "Setting up issue tracking labels for $REPO"
echo ""

# Check gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) not found"
    echo "Install with: brew install gh (macOS) or see https://cli.github.com/"
    exit 1
fi

# Check authentication
if ! gh auth status &> /dev/null; then
    echo "Error: Not authenticated with GitHub"
    echo "Run: gh auth login"
    exit 1
fi

echo "✓ GitHub CLI authenticated"
echo ""

# Create labels (will skip if already exists)
echo "Creating status labels..."
gh label create "status:open" --color "0E8A16" --description "Issue is open and ready to work" --repo "$REPO" 2>/dev/null || echo "  status:open already exists"
gh label create "status:in-progress" --color "FBCA04" --description "Work is actively being done" --repo "$REPO" 2>/dev/null || echo "  status:in-progress already exists"
gh label create "status:blocked" --color "D93F0B" --description "Waiting on dependencies or external factors" --repo "$REPO" 2>/dev/null || echo "  status:blocked already exists"
gh label create "status:closed" --color "6F42C1" --description "Issue is completed" --repo "$REPO" 2>/dev/null || echo "  status:closed already exists"

echo ""
echo "Creating priority labels..."
gh label create "priority:critical" --color "B60205" --description "Urgent - highest priority" --repo "$REPO" 2>/dev/null || echo "  priority:critical already exists"
gh label create "priority:high" --color "D93F0B" --description "Important - high priority" --repo "$REPO" 2>/dev/null || echo "  priority:high already exists"
gh label create "priority:normal" --color "FBCA04" --description "Standard priority" --repo "$REPO" 2>/dev/null || echo "  priority:normal already exists"
gh label create "priority:low" --color "0E8A16" --description "Low priority" --repo "$REPO" 2>/dev/null || echo "  priority:low already exists"
gh label create "priority:deferred" --color "C5DEF5" --description "Deferred for later" --repo "$REPO" 2>/dev/null || echo "  priority:deferred already exists"

echo ""
echo "Creating area labels..."
gh label create "area:core" --color "1D76DB" --description "Core/kernel work" --repo "$REPO" 2>/dev/null || echo "  area:core already exists"
gh label create "area:foundation" --color "5319E7" --description "Foundation library work" --repo "$REPO" 2>/dev/null || echo "  area:foundation already exists"
gh label create "area:bundles" --color "BFD4F2" --description "Bundle development" --repo "$REPO" 2>/dev/null || echo "  area:bundles already exists"
gh label create "area:modules" --color "D4C5F9" --description "Module development" --repo "$REPO" 2>/dev/null || echo "  area:modules already exists"
gh label create "area:cli" --color "C2E0C6" --description "CLI application" --repo "$REPO" 2>/dev/null || echo "  area:cli already exists"
gh label create "area:docs" --color "FEF2C0" --description "Documentation" --repo "$REPO" 2>/dev/null || echo "  area:docs already exists"

echo ""
echo "✓ Labels created successfully!"
echo ""
echo "View labels at: https://github.com/$REPO/labels"
