# SSH Key Setup for Claude Agent SDK Harness

This directory contains SSH keys for authenticating with GitHub and GitLab from within the harness containers.

**Important**: This directory is mounted **read-only** into containers, so `known_hosts` must be pre-populated on the host before containers can use SSH.

## Quick Start

The easiest way is to use the Makefile targets:

```bash
# Initialize the directory (already done)
make ssh-init

# Generate dedicated keys
make ssh-keygen-github
make ssh-keygen-gitlab

# Pre-populate known_hosts (REQUIRED for containers)
make ssh-known-hosts

# Test connections from host
make ssh-test

# Test connections from inside container
make ssh-test-container
```

## Option A: Generate New Dedicated Keys (Recommended)

Generate separate keys for each service. This provides better security isolation.

### GitHub Key

```bash
ssh-keygen -t ed25519 -C "harness-github" -f .ssh/id_ed25519_github -N ""
```

Add the public key to GitHub:
1. Copy the output of: `cat .ssh/id_ed25519_github.pub`
2. Go to GitHub > Settings > SSH and GPG keys > New SSH key
3. Title: "Claude Agent SDK Harness"
4. Paste the key and save

### GitLab Key

```bash
ssh-keygen -t ed25519 -C "harness-gitlab" -f .ssh/id_ed25519_gitlab -N ""
```

Add the public key to GitLab:
1. Copy the output of: `cat .ssh/id_ed25519_gitlab.pub`
2. Go to GitLab > Preferences > SSH Keys
3. Paste the key and save

## Option B: Copy Existing Keys

If you prefer to use your existing SSH keys:

```bash
# Copy your existing key (adjust filenames as needed)
cp ~/.ssh/id_ed25519 .ssh/id_ed25519_github
cp ~/.ssh/id_ed25519.pub .ssh/id_ed25519_github.pub

# For a single key used for both services, update .ssh/config:
# Change IdentityFile lines to point to the same key
```

## Testing

Test SSH connections from your host machine:

```bash
# Test GitHub
ssh -i .ssh/id_ed25519_github -T git@github.com

# Test GitLab
ssh -i .ssh/id_ed25519_gitlab -T git@gitlab.com
```

Or from inside the container:

```bash
make shell
ssh -T git@github.com
ssh -T git@gitlab.com
```

## Files in This Directory

| File | Purpose |
|------|---------|
| `config` | SSH host configuration (already created) |
| `id_ed25519_github` | GitHub private key (you create) |
| `id_ed25519_github.pub` | GitHub public key (you create) |
| `id_ed25519_gitlab` | GitLab private key (you create) |
| `id_ed25519_gitlab.pub` | GitLab public key (you create) |
| `known_hosts` | Host key fingerprints - **run `make ssh-known-hosts` to create** |
| `config` | SSH host configuration with `UpdateHostKeys no` for read-only mount |
| `netrc` | Git HTTPS credentials (you create from netrc.example) |
| `netrc.example` | Template for HTTPS credentials |
| `README.md` | This file |

## Security Notes

- This directory is gitignored - keys will never be committed
- Keys are mounted read-only into containers
- `UpdateHostKeys no` in config prevents SSH from trying to update the read-only known_hosts
- Dedicated keys are revocable without affecting your host SSH identity
- Keys have no passphrase for simplicity (consider passphrases for higher security)
- File permissions: directory 700, files 600

## Troubleshooting

### Permission denied (publickey)

1. Verify the key was added to GitHub/GitLab
2. Check file permissions: `chmod 600 .ssh/id_ed25519_*`
3. Verify the config file points to correct key files

### Host key verification failed

**Inside containers**: The `.ssh/` directory is mounted read-only, so known_hosts cannot be auto-populated. Run on the **host** first:

```bash
make ssh-known-hosts
```

This fetches and stores GitHub/GitLab host keys. The container will then be able to verify hosts.

**On host machine**: If you encounter this on the host, run `make ssh-test` which automatically updates known_hosts.

### Connection refused inside container

Ensure containers are rebuilt after adding SSH volume mount:

```bash
make build
make dev
```
