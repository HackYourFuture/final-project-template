# Final Project Backend

A Spring Boot REST API template for the HackYourFuture final project.

**Stack:** Java 25 · Spring Boot 4.1 · PostgreSQL · Flyway · Spring Security · springdoc-openapi (Scalar) · Lombok · Maven

---

## Quick start

You need **JDK 25** and a PostgreSQL database (in Docker, in the cloud, or installed locally). Maven comes with the project via the `mvnw` wrapper.

Start a database — the defaults expect `mydb` on `localhost:5432`, user `admin`, password `password`:

```bash
docker run --name hyf-postgres -e POSTGRES_DB=mydb -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres:17
```

Run the app:

```bash
./mvnw spring-boot:run
```

Open the API docs at **http://localhost:8080/api/docs**

On Windows use `mvnw.cmd`. Every setting has a working default, so nothing needs configuring to get started.

---

## API docs

| | URL |
|---|---|
| **Scalar UI** — browse and try endpoints | http://localhost:8080/api/docs |
| **OpenAPI spec** — for Postman, or generating a frontend client | http://localhost:8080/api/docs/openapi.yaml |

Both are public (see [`SecurityConfig`](src/main/java/nl/hackyourfuture/project/backend/config/SecurityConfig.java)). Change a controller, restart, refresh — your endpoint is there.

---

## Building

Build a runnable JAR into `target/`:

```bash
./mvnw clean package
```

Run it:

```bash
java -jar target/backend-0.0.1-SNAPSHOT.jar
```

Run the tests:

```bash
./mvnw test
```

> `BackendApplicationTests.contextLoads()` boots the whole Spring context, so it needs a reachable database just like the app does.

Check code style with Checkstyle ([`checkstyle.xml`](checkstyle.xml)):

```bash
./mvnw checkstyle:check
```

### Docker build

The [`Dockerfile`](Dockerfile) is multi-stage, so you need neither Java nor Maven installed:

```bash
docker build -t hyf-backend .
```

Stage 1 compiles the JAR in a Maven image; stage 2 copies just that JAR into a slim JRE image, leaving the source and build tools behind.

---

## Docker

Pull the published image from GitHub Container Registry:

```bash
docker pull ghcr.io/<org>/backend:latest
```

Run it, pointing at your database:

```bash
docker run -p 8080:8080 -e DB_URL=jdbc:postgresql://my-db-host:5432/mydb -e DB_USER=admin -e DB_PASSWORD=secret ghcr.io/<org>/backend:latest
```

Two things to watch:

- **`localhost` inside a container means the container itself.** To reach a database on your own machine, use `host.docker.internal`.
- **Don't commit credentials** in a `docker run` command. Use `--env-file secrets.env` (gitignored), or your host's secret manager.

---

## Environment variables

All configuration lives in [`application.yaml`](src/main/resources/application.yaml). Each value reads an environment variable and falls back to a local-development default, so you only set what you need to change.

| Variable | Default | Description |
|---|---|---|
| `DB_URL` | `jdbc:postgresql://localhost:5432/mydb` | JDBC URL, must start with `jdbc:postgresql://` |
| `DB_USER` | `admin` | Database username |
| `DB_PASSWORD` | `password` | Database password |
| `PORT` | `8080` | Port the server listens on |
| `SPRING_PROFILES_ACTIVE` | — | `dev` or `prod`. The Docker image defaults to `prod` |

`application-dev.yaml` and `application-prod.yaml` layer on top when the matching profile is active. They only set logging levels right now — put anything environment-specific there.

> The defaults are real credentials for a local throwaway database. In production always override them with environment variables, and never commit real secrets.

Any Spring property can be set this way: upper-case it and replace `.` with `_`, so `server.port` becomes `SERVER_PORT`.

---

## Architecture

The project is organised **by feature**, not by layer. Everything about users lives in `user/`; add orders and everything about them goes in `order/` beside it.

```
src/main/java/nl/hackyourfuture/project/backend/
├── BackendApplication.java        ← entry point
├── user/                          ← one folder per feature
│   ├── UserController.java        ← HTTP layer
│   ├── UserService.java           ← business logic
│   ├── UserRepository.java        ← database access
│   ├── User.java                  ← model
│   └── dto/
│       ├── UserRequest.java       ← what the client sends
│       └── UserResponse.java      ← what we send back
└── config/                        ← cross-cutting setup
    ├── SecurityConfig.java
    ├── GlobalExceptionHandler.java
    └── OpenApiConfig.java

src/main/resources/
├── application.yaml               ← all configuration
└── db/migration/                  ← Flyway migrations
```

Requests flow down, data flows back up, and each layer only talks to the one below it:

```
HTTP request → Controller → Service → Repository → PostgreSQL
```

**Controller** — maps URLs to methods, validates input with `@Valid`, returns status codes. No business logic: each method should be a one-line delegation to the service. The OpenAPI annotations live here.

**Service** — the business logic. Knows nothing about HTTP, which is what makes it easy to test.

**Repository** — database access only. This project uses `JdbcClient` with **plain SQL** (no JPA/Hibernate), so the query you write is the query that runs. A `RowMapper` turns a result row into a model. Always use named parameters (`:email`) as the existing code does — never concatenate user input into SQL.

**Model** — a plain object mirroring a table row, with Lombok generating the getters and builder.

**DTOs** — records defining what crosses the network. Don't return the model directly: it may hold fields you don't want to expose, the input and output shapes differ (the client sends an email but never an id), and DTOs let you rename a column without breaking the frontend. `UserRequest` carries the validation rules; `UserResponse` has a `from(User)` factory.

### The `config` folder

**[`SecurityConfig`](src/main/java/nl/hackyourfuture/project/backend/config/SecurityConfig.java)** — the filter chain every request passes through *before* reaching a controller. `/api/users/**`, `/api/docs/**` and `/error` are open; everything else needs authentication. CSRF and form login are off because this is a stateless JSON API. Note that a 401/403 raised here never reaches `GlobalExceptionHandler`.

**[`GlobalExceptionHandler`](src/main/java/nl/hackyourfuture/project/backend/config/GlobalExceptionHandler.java)** — a `@RestControllerAdvice` catching exceptions from any controller, so you don't write try/catch everywhere. A failed `@Valid` check becomes a 400 with an RFC 9457 `ProblemDetail` listing the invalid fields. For a new error case add another `@ExceptionHandler(YourException.class)` method; Spring picks the closest matching type.

**[`OpenApiConfig`](src/main/java/nl/hackyourfuture/project/backend/config/OpenApiConfig.java)** — the title, version and server list shown in the docs, plus a customizer that sorts endpoints so the spec doesn't reshuffle between builds.

---

## How the docs are generated

**There is no `openapi.yaml` file in this repo, and you should never write one by hand.**

The spec is built at runtime: on startup springdoc scans every `@RestController`, reads the Spring and OpenAPI annotations, derives JSON schemas from your DTO records, and assembles the document in memory. `/api/docs/openapi.yaml` serves it; `/api/docs` renders it with Scalar.

So **your code is the source of truth** — no generation step, no file that can drift. But a missing annotation shows up as a gap in the docs immediately.

- **Free:** paths, methods, parameter names and types, DTO schemas, `required` from `@NotBlank`, lengths from `@Size`, format from `@Email`.
- **You write:** `@Operation`, `@ApiResponse`, `@Parameter`, and `@Schema` descriptions and examples.

Copy the pattern from [`UserController`](src/main/java/nl/hackyourfuture/project/backend/user/UserController.java). Document every status code your endpoint can return, not just the happy path.

To hand the spec to the frontend team, grab it while the app runs:

```bash
curl http://localhost:8080/api/docs/openapi.yaml -o openapi.yaml
```

---

## Migrations

The schema is managed by **Flyway** in [`db/migration`](src/main/resources/db/migration). On startup it applies any migration that hasn't run yet, tracking them in a `flyway_schema_history` table — so everyone's schema matches, including production.

Name files `V<number>__<description>.sql` (**two** underscores): after `V1__init_schema.sql` comes `V2__add_orders_table.sql`.

**Never edit a migration that has already run.** Flyway checksums each applied file and startup fails if one changes. Need a change? Add a new migration. If your local database is in a mess, drop it and let Flyway rebuild it.

---

## CI/CD

Every push or PR touching `backend/**` runs [`deploy-backend.yaml`](../.github/workflows/deploy-backend.yaml):

1. **`lint-and-test`** — `./mvnw checkstyle:check` then `./mvnw test`. Both must pass.
2. **`build`** — builds the Docker image; only pushes to GHCR when the change lands on `main`.

Images are tagged `latest`, `1.0.<run number>`, and `main-sha-<short sha>`.

---


## Adding a feature

Adding products, bottom-up:

1. Migration — `V3__create_products_table.sql`
2. Create the `product/` package next to `user/`
3. `Product.java` mirroring the table
4. `ProductRepository.java` with a `RowMapper` and your SQL
5. `dto/ProductRequest.java` (validation annotations) and `dto/ProductResponse.java` (`from` factory)
6. `ProductService.java` for the logic
7. `ProductController.java` with `@RestController`, `@RequestMapping("/api/products")` and OpenAPI annotations
8. Add the path to `SecurityConfig` if it should be public
9. Restart and check http://localhost:8080/api/docs

The `user` package is your reference — deliberately small and complete.

---

## Good to know

- **Lombok** generates boilerplate at compile time, which is why `UserService` has no visible constructor. Your IDE needs the Lombok plugin or it will flag code that compiles fine.
- **Constructor injection** via `@RequiredArgsConstructor` and `private final` fields. Prefer it to `@Autowired` on fields.
- **DevTools** restarts the app when you rebuild — in IntelliJ, Recompile (⇧⌘F9 / Ctrl+Shift+F9) is enough.
- **Keep classes under `nl.hackyourfuture.project.backend`.** Spring only scans below the package holding `BackendApplication`; anything outside is silently ignored.
- **Use correct status codes** — `200` read/update, `201` create (see `@ResponseStatus(HttpStatus.CREATED)`), `400` invalid input, `404` not found — then document them with `@ApiResponse`.
- **Validate at the edge:** constraints on the request DTO, `@Valid` on the controller parameter.
- **Before opening a PR,** run `./mvnw checkstyle:check` and `./mvnw test` locally — CI runs the same checks and blocks the PR if either fails.

### Troubleshooting

| Symptom | Cause |
|---|---|
| `Failed to configure a DataSource: 'url' attribute is not specified` | Config files missing from `target/classes`. Run `./mvnw clean package`, or Rebuild Project in IntelliJ — recompiling a single class doesn't copy resources |
| `Connection refused` on port 5432 | PostgreSQL isn't running — start the container from [Quick start](#quick-start) |
| `Migration checksum mismatch` | An applied migration was edited. Revert it and add a new `V…` file |
| `403 Forbidden` on your new endpoint | Not listed in `SecurityConfig`; anything unlisted requires authentication |
| Endpoint missing from `/api/docs` | Not annotated `@RestController`, or outside the base package |
| IDE errors on `@Getter`/`@Builder` but Maven builds fine | Lombok plugin not installed in the IDE |
| Checkstyle fails in CI but not locally | Run `./mvnw checkstyle:check` before pushing — it's the same check CI runs |
