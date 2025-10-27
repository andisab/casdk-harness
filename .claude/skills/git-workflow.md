---
title: Git Workflow Operations
description: Comprehensive Git operations including branching, merging, rebasing, and collaboration best practices
tags: [skill, git, version-control, workflow, collaboration]
type: skill
version: "1.0.0"
category: development-tools
---

# Git Workflow Operations

## Overview

This skill provides comprehensive Git workflow capabilities for version control, collaboration, and code management. Use this skill for branching strategies, conflict resolution, commit management, and team collaboration workflows.

**When to use this skill:**
- Managing feature branches and releases
- Resolving merge conflicts
- Creating and reviewing pull requests
- Managing Git history and commits
- Setting up repository workflows

## Key Concepts

### Branching Strategies

**Feature Branch Workflow:**
- Main branch (`main` or `master`) is always production-ready
- Feature branches created from main: `feature/user-authentication`
- Merge back to main via pull request after review

**GitFlow Workflow:**
- `main` - Production releases
- `develop` - Integration branch
- `feature/*` - New features
- `release/*` - Release preparation
- `hotfix/*` - Production fixes

**Trunk-Based Development:**
- Single main branch with short-lived feature branches
- Frequent integration (multiple times per day)
- Feature flags for incomplete features

### Commit Message Conventions

Follow Conventional Commits standard:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style/formatting
- `refactor`: Code refactoring
- `test`: Test additions/modifications
- `chore`: Maintenance tasks

**Examples:**
```
feat(auth): add JWT token refresh mechanism

Implement automatic token refresh using refresh tokens.
Tokens are refreshed 5 minutes before expiration.

Closes #123
```

```
fix(api): resolve race condition in user login

Added mutex lock to prevent concurrent login attempts
from the same user creating duplicate sessions.

Fixes #456
```

## Implementation

### Basic Workflow Operations

#### 1. Starting a New Feature

```bash
# Update main branch
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/user-dashboard

# Make changes, then commit
git add .
git commit -m "feat(dashboard): add user statistics widget"

# Push to remote
git push -u origin feature/user-dashboard
```

#### 2. Keeping Feature Branch Updated

```bash
# Option A: Merge (preserves history)
git checkout feature/user-dashboard
git merge main

# Option B: Rebase (linear history, cleaner)
git checkout feature/user-dashboard
git rebase main

# If conflicts, resolve them, then:
git add .
git rebase --continue

# Force push after rebase (only if not shared)
git push --force-with-lease origin feature/user-dashboard
```

#### 3. Creating Pull Request

```bash
# Ensure branch is up to date
git checkout feature/user-dashboard
git rebase main
git push --force-with-lease origin feature/user-dashboard

# Use GitHub CLI to create PR
gh pr create \
  --title "Add user dashboard with statistics" \
  --body "Implements #123\n\nChanges:\n- User stats widget\n- Chart visualizations\n- Real-time updates" \
  --base main \
  --head feature/user-dashboard
```

### Advanced Operations

#### Interactive Rebase

Clean up commit history before PR:

```bash
# Rebase last 3 commits
git rebase -i HEAD~3

# In editor, you can:
# pick - keep commit
# squash - combine with previous commit
# fixup - combine but discard message
# reword - change commit message
# edit - pause to amend commit
# drop - remove commit

# Example:
pick a1b2c3d feat(dashboard): add basic layout
squash d4e5f6g feat(dashboard): add styling
squash g7h8i9j feat(dashboard): fix responsive issues
# Results in single commit with first message
```

#### Cherry-Pick Commits

Apply specific commits to another branch:

```bash
# Get commit hash from source branch
git log feature/source-branch

# Switch to target branch
git checkout feature/target-branch

# Cherry-pick specific commit
git cherry-pick abc123def

# Cherry-pick range of commits
git cherry-pick abc123..def456

# Cherry-pick without committing (to modify)
git cherry-pick -n abc123def
git add modified-files
git commit -m "cherry-picked and modified: description"
```

#### Resolving Merge Conflicts

```bash
# When merge/rebase conflicts occur:
git status  # Shows conflicted files

# Open conflicted files, look for:
<<<<<<< HEAD
Your changes
=======
Their changes
>>>>>>> branch-name

# After resolving conflicts:
git add resolved-file.ts
git rebase --continue  # if rebasing
git merge --continue   # if merging

# Or abort if needed:
git rebase --abort
git merge --abort
```

#### Stashing Changes

Temporarily save uncommitted work:

```bash
# Stash current changes
git stash save "WIP: user dashboard styling"

# List stashes
git stash list

# Apply most recent stash
git stash apply

# Apply and remove stash
git stash pop

# Apply specific stash
git stash apply stash@{2}

# Clear all stashes
git stash clear
```

### Git Hooks

Automate checks before commits/pushes:

```bash
# .git/hooks/pre-commit
#!/bin/bash
# Run linting before commit
npm run lint || exit 1
npm run typecheck || exit 1

# .git/hooks/pre-push
#!/bin/bash
# Run tests before push
npm run test || exit 1
```

### Git Aliases

Add to `.gitconfig` for efficiency:

```ini
[alias]
  co = checkout
  br = branch
  ci = commit
  st = status
  unstage = reset HEAD --
  last = log -1 HEAD
  visual = log --graph --oneline --decorate --all
  amend = commit --amend --no-edit
  pushf = push --force-with-lease
  sync = !git fetch origin && git rebase origin/main
  undo = reset --soft HEAD~1
```

Usage:
```bash
git co feature/new-branch
git visual  # See branch graph
git amend  # Add to last commit
git sync   # Update with main
```

## Best Practices

### Commit Hygiene

**Do:**
- ✅ Commit early and often (small, logical units)
- ✅ Write descriptive commit messages
- ✅ Keep commits focused on single concerns
- ✅ Use conventional commit format
- ✅ Reference issue numbers

**Don't:**
- ❌ Commit large, unrelated changes together
- ❌ Use vague messages like "fix bug" or "update"
- ❌ Commit commented-out code
- ❌ Commit secrets or credentials
- ❌ Rewrite public history (shared branches)

### Branch Management

**Do:**
- ✅ Delete feature branches after merging
- ✅ Keep branch names descriptive: `feature/add-user-auth`
- ✅ Regularly sync with main/develop
- ✅ Use branch protection rules on main
- ✅ Require PR reviews before merging

**Don't:**
- ❌ Leave stale branches unmerged
- ❌ Work directly on main/master
- ❌ Use cryptic branch names: `fix1`, `test`
- ❌ Let branches diverge too far from main
- ❌ Force push to shared branches

### Pull Request Workflow

**Before Creating PR:**
1. Rebase on target branch (main/develop)
2. Run full test suite locally
3. Run linting and type checking
4. Review your own changes first
5. Write clear PR description

**PR Description Template:**
```markdown
## Summary
Brief description of changes

## Changes Made
- Added feature X
- Fixed bug Y
- Updated documentation Z

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests passing
- [ ] Manual testing completed

## Screenshots (if UI changes)
[Add screenshots]

## Related Issues
Closes #123
Fixes #456
```

### Conflict Resolution

**Strategies:**
1. **Communicate**: Talk to teammate if major conflicts
2. **Understand both sides**: Review changes from both branches
3. **Test after resolution**: Ensure functionality isn't broken
4. **Keep atomic**: Resolve conflicts in small, logical chunks
5. **Document**: Add comments explaining complex resolutions

### Security & Privacy

**Do:**
- ✅ Use `.gitignore` to exclude sensitive files
- ✅ Add secrets to environment variables, not code
- ✅ Use `git-secrets` or similar tools to scan for credentials
- ✅ Sign commits with GPG (for security-critical projects)
- ✅ Use SSH keys for authentication

**Don't:**
- ❌ Commit `.env` files with real credentials
- ❌ Commit API keys, passwords, or tokens
- ❌ Commit customer data or PII
- ❌ Push directly to production branches

## Examples

### Complete Feature Development Workflow

```bash
# 1. Start feature
git checkout main
git pull origin main
git checkout -b feature/payment-integration

# 2. Develop feature (multiple commits)
git add src/payment/
git commit -m "feat(payment): add Stripe payment integration"

git add tests/payment/
git commit -m "test(payment): add payment integration tests"

git add docs/payment.md
git commit -m "docs(payment): add payment integration guide"

# 3. Sync with main before PR
git fetch origin main
git rebase origin/main

# 4. Clean up commits (squash related commits)
git rebase -i HEAD~3
# Squash test and doc commits into feature commit

# 5. Push and create PR
git push -u origin feature/payment-integration
gh pr create --title "Add Stripe payment integration" \
  --body "$(cat <<'EOF'
## Summary
Integrate Stripe for payment processing

## Changes
- Add Stripe SDK integration
- Implement payment flow (checkout → confirmation)
- Add webhook handling for payment events
- Add comprehensive test coverage

## Testing
- [x] Unit tests for payment service
- [x] Integration tests with Stripe test mode
- [x] Manual testing with test credit cards

## Security
- [x] No API keys in code (uses env vars)
- [x] Webhook signature verification
- [x] PCI compliance review

Closes #234
EOF
)"

# 6. Address PR feedback
git add src/payment/stripe.ts
git commit -m "fix(payment): add proper error handling for declined cards"
git push origin feature/payment-integration

# 7. After PR approved and merged
git checkout main
git pull origin main
git branch -d feature/payment-integration
git push origin --delete feature/payment-integration
```

### Hotfix Workflow (Production Bug)

```bash
# 1. Create hotfix from main/production
git checkout main
git pull origin main
git checkout -b hotfix/critical-auth-bug

# 2. Fix bug
git add src/auth/jwt.ts
git commit -m "fix(auth): resolve token expiration race condition

Critical fix for production issue where concurrent requests
could cause authentication failures.

Fixes #789"

# 3. Create PR with high priority
gh pr create --title "🚨 HOTFIX: Auth token race condition" \
  --body "Critical production bug fix" \
  --label "priority:critical,type:hotfix"

# 4. After approval, merge and deploy immediately
git checkout main
git pull origin main  # Should include the hotfix
git tag -a v1.2.1 -m "Hotfix: Auth token race condition"
git push origin v1.2.1

# 5. Backport to develop if using GitFlow
git checkout develop
git cherry-pick <hotfix-commit-hash>
git push origin develop

# 6. Clean up
git branch -d hotfix/critical-auth-bug
git push origin --delete hotfix/critical-auth-bug
```

## Related Skills & Conventions

- [Code Review Techniques](./code-review-techniques.md) - PR review best practices
- [Testing Strategies](./testing-strategies.md) - Test-driven development workflow
- [Deployment Operations](./deployment-operations.md) - Release and deployment workflows
- [Workflow: Bug Fix & Debugging](../workflows/bug-fix-debugging.md) - Bug investigation and fixes

## Common Issues & Solutions

**Issue: "Detached HEAD state"**
```bash
# Solution: Create a branch from current state
git checkout -b rescue-branch
git push -u origin rescue-branch
```

**Issue: "Accidentally committed to wrong branch"**
```bash
# Solution: Move commits to correct branch
git checkout correct-branch
git cherry-pick wrong-branch~1..wrong-branch
git checkout wrong-branch
git reset --hard HEAD~1
```

**Issue: "Want to undo last commit (not pushed)"**
```bash
# Keep changes, undo commit
git reset --soft HEAD~1

# Discard changes and commit
git reset --hard HEAD~1
```

**Issue: "Accidentally committed sensitive data"**
```bash
# Remove from history (use with caution)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch path/to/sensitive/file" \
  --prune-empty --tag-name-filter cat -- --all

# Or use BFG Repo-Cleaner (faster)
bfg --delete-files sensitive-file.txt
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
