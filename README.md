# final-project-template

## Run everything with Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

This starts Postgres, the backend (`http://localhost:8080`, docs at `/api/docs`), and the frontend (`http://localhost:3000`). Visit `http://localhost:3000/users` to see the list-users page working end to end.

For running each part individually during development, see `backend/README.md` and `frontend/README.md`.