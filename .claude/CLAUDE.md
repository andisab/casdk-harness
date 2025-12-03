# Agent Runtime Context

This file is loaded automatically on agent startup as the system prompt.
Edit this file to change agent behavior without modifying Python code.

---

## Working Directory Instructions

Your current working directory (cwd) is /app for system configuration access.
ALL development work MUST be done in the /workspace directory.

### Directory Structure
- /app/.claude/ - System configuration (skills, agents, specs) - READ-ONLY
- /workspace/ - Your blank canvas for development work

### File Operations
Use ABSOLUTE paths starting with /workspace/:
- ✓ Read("/workspace/myfile.txt")
- ✓ Write("/workspace/output.txt", content)
- ✓ Glob("/workspace/**/*.py")
- ✗ Read("myfile.txt") - Would look in /app, not /workspace

### Shell Commands
Always cd to /workspace first:
- ✓ Bash("cd /workspace && git clone https://github.com/user/repo")
- ✓ Bash("cd /workspace/projects/myrepo && npm install")
- ✓ Bash("ls /workspace")

### Repository Cloning
Always clone to /workspace/projects/:
- ✓ Clone to: /workspace/projects/{repo-name}/
- ✓ Example: cd /workspace/projects && git clone repo

---

## Git Authentication

SSH keys are pre-configured at /home/claude/.ssh/ for GitHub and GitLab:
- github.com uses: id_ed25519_github
- gitlab.provectus.com uses: id_ed25519_gitlab

For git operations, use HTTPS URLs:
- ✓ git clone https://github.com/user/repo.git
- ✓ git clone https://gitlab.provectus.com/user/repo.git

### CLI Tools Available
- **git**: Version control (SSH auth configured)
- **gh**: GitHub CLI (run `gh auth login` if needed, or set GITHUB_PERSONAL_ACCESS_TOKEN)
- **glab**: GitLab CLI (run `glab auth login` if needed, or set GITLAB_PERSONAL_ACCESS_TOKEN)

---

## Important Rules

1. The /workspace directory is your blank canvas for development
2. NEVER write files to /app (read-only system configuration)
3. Use absolute paths for all file operations
4. Prefer SSH URLs for git clone operations
