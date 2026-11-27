# FastAPI Role Management Starter

A simple FastAPI backend with:

- Two roles: `admin` and `user`
- Register and login
- JWT access tokens
- Password hashing with bcrypt
- PostgreSQL + SQLAlchemy
- Redis + Celery background worker
- Admin dashboard and user management
- Docker Compose for local development

## 1. Run the project

Requirements: Docker and Docker Compose.

```bash
cp .env.example .env
```

Before starting, edit `.env`:
- Change `SECRET_KEY` to a long random value.
- Change `ADMIN_PASSWORD`.
- Change the default admin email if you want.

Start the API, PostgreSQL, Redis and Celery worker:

```bash
docker compose up --build
```

Open:
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

On first startup, the API creates the admin account configured by `ADMIN_EMAIL` and
`ADMIN_PASSWORD`, if that email does not already exist. Existing accounts are never
automatically promoted to admin.

## 2. Authentication

### Register a normal user

`POST /api/v1/auth/register`

```json
{
  "email": "user@example.com",
  "full_name": "Regular User",
  "password": "UserPassword123!"
}
```

Public registration always creates a `user`; clients cannot register themselves as admins.

### Login

`POST /api/v1/auth/login`

This endpoint uses OAuth2 form data:

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=ChangeMe123!"
```

Response:

```json
{
  "access_token": "YOUR_JWT_TOKEN",
  "token_type": "bearer",
  "expires_in": 3600
}
```

Use the token on protected endpoints:

```http
Authorization: Bearer YOUR_JWT_TOKEN
```

In Swagger UI, click **Authorize** and enter the email as the username and the password.

## 3. User endpoints

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| GET | `/api/v1/users/me` | Admin/User | Get own profile |
| PATCH | `/api/v1/users/me` | Admin/User | Update own name or password |

## 4. Admin endpoints

All endpoints below require an active admin JWT.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/admin/dashboard` | User counts and dashboard statistics |
| GET | `/api/v1/admin/users` | List users; supports `skip`, `limit`, `search`, `role`, `is_active` |
| GET | `/api/v1/admin/users/{id}` | View one user |
| POST | `/api/v1/admin/users` | Create a user or another admin |
| PATCH | `/api/v1/admin/users/{id}` | Update email, name, password, role or active status |
| DELETE | `/api/v1/admin/users/{id}` | Delete a user |
| POST | `/api/v1/admin/users/{id}/send-welcome-email` | Queue a welcome email through Celery |
| GET | `/api/v1/admin/tasks/{task_id}` | Check a Celery task's status |

Example admin-created user:

```json
{
  "email": "newuser@example.com",
  "full_name": "New User",
  "password": "StrongPassword123!",
  "role": "user",
  "is_active": true
}
```

Example update:

```json
{
  "role": "admin",
  "is_active": true
}
```

The API prevents an admin from deleting their own account, demoting/deactivating
their own admin account, or removing the last active admin.

## 5. Celery and email

Registering a user queues a welcome-email task. An admin can queue it again from the
admin endpoint. The worker is the `worker` service in Docker Compose.

To send real emails, configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
`SMTP_PASSWORD`, `SMTP_FROM`, and `SMTP_USE_TLS` in `.env`, then restart the worker:

```bash
docker compose up -d --force-recreate worker
```

If SMTP is not configured, the task logs a demo message. This lets you verify the
Celery + Redis flow without an email provider.

View worker logs:

```bash
docker compose logs -f worker
```

## 6. Useful commands

```bash
# Stop services
docker compose down

# Stop services and delete the local PostgreSQL volume
docker compose down -v

# Run tests inside the API container
docker compose exec api pytest
```

## 7. Project structure

```text
app/
  api/
    routes/
      auth.py
      users.py
      admin.py
    deps.py
    router.py
  core/
    config.py
    security.py
  db/
    base.py
    session.py
  models/
    user.py
  schemas/
    auth.py
    user.py
  tasks/
    celery_app.py
    tasks.py
  main.py
  seed.py
tests/
  test_security.py
Dockerfile
docker-compose.yml
requirements.txt
.env.example
```

## Notes before production

This is a starter project, not a fully hardened production deployment. Before deploying:
- Use a strong secret manager value for `SECRET_KEY` and strong database credentials.
- Use HTTPS and configure CORS deliberately if a browser frontend is added.
- Add Alembic migrations instead of relying on `create_all`.
- Add rate limiting, audit logs, refresh-token rotation/revocation and account recovery.
- Configure SMTP credentials securely.
- Add integration tests for database and role-protected endpoints.
