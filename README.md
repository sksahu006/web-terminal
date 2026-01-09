# Virtual Workspace Platform

On-demand, stateless, resource-limited virtual coding workspaces with GitHub-based code persistence.

## Features

- 🚀 **Instant Workspaces**: Spin up isolated development environments in seconds
- 🔒 **Resource Isolation**: Hard limits on CPU, memory, and runtime per user
- 📦 **GitHub Integration**: Code persistence through GitHub - clone and push
- ♻️ **Ephemeral by Design**: Clean state on every start, zero storage cost
- 🛡️ **Secure Multi-tenant**: No privileged containers, JWT authentication

## Quick Start

### Prerequisites

- Docker & Docker Compose
- GitHub OAuth App (for authentication)

### 1. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

Required settings:
- `GITHUB_CLIENT_ID` - Your GitHub OAuth App client ID
- `GITHUB_CLIENT_SECRET` - Your GitHub OAuth App client secret
- `SECRET_KEY` - Random secret for sessions
- `JWT_SECRET_KEY` - Random secret for JWT tokens

### 2. Build Workspace Image

```bash
cd docker/workspace-image
docker build -t workspace-dev:latest .
```

### 3. Start the Platform

**Development:**
```bash
docker-compose -f docker-compose.dev.yml up --build
```

**Production:**
```bash
docker-compose up --build -d
```

### 4. Access

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│    Frontend     │────▶│   Nginx Proxy   │
│   (nginx)       │     │                 │
└─────────────────┘     └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
          ┌─────────────────┐      ┌─────────────────┐
          │  Backend API    │      │ User Containers │
          │  (FastAPI)      │─────▶│ (ttyd terminal) │
          └────────┬────────┘      └─────────────────┘
                   │
                   ▼
          ┌─────────────────┐
          │    SQLite DB    │
          └─────────────────┘
```

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/auth/github` | Start GitHub OAuth flow |
| GET | `/auth/github/callback` | OAuth callback |
| GET | `/auth/me` | Get current user |
| POST | `/auth/logout` | Logout |

### Workspace
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/workspace/start` | Start workspace |
| POST | `/workspace/stop` | Stop workspace |
| GET | `/workspace/status` | Get status |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/stats` | Platform statistics |
| GET | `/admin/users` | List users |
| PUT | `/admin/users/{id}/limits` | Update limits |

## Resource Limits

Default limits per user:
- **CPU**: 1 core
- **Memory**: 1024 MB
- **Disk**: 5 GB
- **Runtime**: 1 hour

Admins can adjust limits per user through the admin dashboard.

## Project Structure

```
├── backend/                # FastAPI backend
│   ├── app/
│   │   ├── core/          # Config, DB, Security
│   │   ├── models/        # SQLAlchemy models
│   │   ├── routers/       # API routes
│   │   ├── schemas/       # Pydantic schemas
│   │   └── services/      # Container manager
│   └── requirements.txt
├── frontend/              # Static frontend
├── docker/
│   ├── workspace-image/   # Dev container image
│   └── nginx/            # Frontend & Proxy config
├── docker-compose.yml     # Production config
└── docker-compose.dev.yml # Development config
```

## Security

- ✅ No privileged containers
- ✅ No Docker socket exposed to users
- ✅ JWT authentication with expiry
- ✅ GitHub OAuth (no password storage)
- ✅ Resource limits enforced at container level
- ✅ Ephemeral filesystems (no persistent user data)

## Development

### Run Backend Locally

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Run Frontend Locally

Simply open `frontend/index.html` in a browser, or use a local server.

## License

MIT
