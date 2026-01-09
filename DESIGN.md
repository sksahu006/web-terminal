# Virtual Coding Workspace Platform - Design Document

## Phase 1: Core Platform

---

## Non-Negotiable Constraints (Design Lock)

| Rule | Status |
|------|--------|
| ❌ No persistent volumes | LOCKED |
| ❌ No user code stored by platform | LOCKED |
| ✅ One container per active user | LOCKED |
| ✅ Containers are disposable | LOCKED |
| ✅ All code must be cloned/pushed to GitHub | LOCKED |
| ✅ Resource limits enforced at container level | LOCKED |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (SPA)                          │
│                    Login | Dashboard | Terminal                 │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TRAEFIK REVERSE PROXY                      │
│              Routes /api/* and /workspace/{user_id}             │
└─────────────────────────────┬───────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────────────┐
│    FASTAPI BACKEND      │     │     USER CONTAINERS (ttyd)      │
│  - Auth (GitHub OAuth)  │     │  - Isolated per user            │
│  - Workspace API        │     │  - Resource limited             │
│  - Admin API            │     │  - Ephemeral filesystem         │
│  - Container Manager    │     │  - Git + Dev tools              │
└───────────┬─────────────┘     └─────────────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│    SQLITE DATABASE      │
│  - Users                │
│  - User Limits          │
│  - Active Workspaces    │
└─────────────────────────┘
```

---

## Core Principles

### 1. Stateless Workspaces
- Containers start with a clean filesystem every time
- No volumes or bind mounts attached
- All user code must be cloned from GitHub
- Users must push changes before stopping

### 2. Resource Isolation
- Each container has hard CPU/memory/disk limits
- Limits are admin-configurable per user
- Default limits: 1 CPU, 1GB RAM, 5GB disk, 1 hour runtime
- Misbehaving containers are automatically killed

### 3. Single Source of Truth
- GitHub is the only code storage
- Platform never persists user code
- Platform stores only: user identity, resource limits, active sessions

### 4. Security First
- No privileged containers
- No Docker socket exposed to users
- JWT validation on every API request
- GitHub OAuth for authentication

---

## Mental Model

> "We rent CPU & RAM, not storage."

The platform provides compute resources. Users bring their own code via GitHub.

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Backend API | FastAPI (Python) |
| Container Runtime | Docker |
| Authentication | JWT + GitHub OAuth |
| Reverse Proxy | Traefik |
| Database | SQLite |
| Web Terminal | ttyd |
| Frontend | Vanilla HTML/CSS/JS |

---

## Data Model

### Users Table
```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,           -- UUID
    github_id TEXT UNIQUE NOT NULL,
    github_username TEXT NOT NULL,
    github_access_token TEXT,      -- Encrypted
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### User Limits Table
```sql
CREATE TABLE user_limits (
    user_id TEXT PRIMARY KEY REFERENCES users(id),
    cpu REAL DEFAULT 1.0,          -- CPU cores
    memory INTEGER DEFAULT 1024,   -- MB
    disk INTEGER DEFAULT 5,        -- GB
    max_runtime INTEGER DEFAULT 3600  -- Seconds
);
```

### Workspaces Table
```sql
CREATE TABLE workspaces (
    id TEXT PRIMARY KEY,           -- UUID
    user_id TEXT REFERENCES users(id),
    container_id TEXT NOT NULL,
    status TEXT NOT NULL,          -- starting, running, stopping, stopped
    access_url TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);
```

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/auth/github` | Redirect to GitHub OAuth |
| GET | `/auth/github/callback` | Handle OAuth callback |
| POST | `/auth/logout` | Logout user |
| GET | `/auth/me` | Get current user info |

### Workspace
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/workspace/start` | Start user workspace |
| POST | `/workspace/stop` | Stop user workspace |
| GET | `/workspace/status` | Get workspace status |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/users` | List all users |
| GET | `/admin/users/{id}/limits` | Get user limits |
| PUT | `/admin/users/{id}/limits` | Update user limits |

---

## Container Lifecycle

```
User clicks "Start Workspace"
         │
         ▼
┌─────────────────────────┐
│  Validate JWT token     │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Check for existing     │
│  active workspace       │──── If exists ──── Return error
└───────────┬─────────────┘
            │ No existing
            ▼
┌─────────────────────────┐
│  Fetch user limits      │
│  from database          │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Create container with: │
│  --cpus={cpu}           │
│  --memory={memory}m     │
│  --pids-limit=256       │
│  No volumes!            │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Register in database   │
│  Set expiry time        │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Configure Traefik      │
│  route dynamically      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Return access URL      │
└─────────────────────────┘
```

---

## Security Checklist

- [x] No privileged containers
- [x] No Docker socket access for users
- [x] Outbound-only network for containers
- [x] JWT validation on every request
- [x] GitHub OAuth (no password storage)
- [x] Resource limits enforced by Docker
- [x] Auto-termination after max runtime

---

## Phase 1 Acceptance Criteria

Phase 1 is **COMPLETE** when:

- ✅ User can log in via GitHub
- ✅ Admin can set resource limits per user
- ✅ User can start a workspace
- ✅ Container spins up with correct limits
- ✅ User can access web terminal
- ✅ User can clone GitHub repo
- ✅ User can code and push changes
- ✅ Container is destroyed on stop
- ✅ No data remains on platform after stop
