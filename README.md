<!-- zrzur-publication -->
# Zrzur Self-hosted

Everything needed to run your own [Zrzur](https://zrzur.com) server with Docker Compose: the services, the web app, storage, the reverse proxy and LiveKit for voice.

Part of Zrzur 26. Versions and the other components: [ZRZUR_RELEASE.md](./ZRZUR_RELEASE.md).

## Quick start

```bash
git clone https://github.com/zrzur/self-hosted.git
cd self-hosted
./generate_config.sh your.domain
docker compose config --quiet
docker compose up -d
```

Needs Git, Bash and Docker.

The application images (`ghcr.io/zrzur/*`) are not public yet. Until they are, build them from [zrzur/backend](https://github.com/zrzur/backend) and [zrzur/web](https://github.com/zrzur/web). `compose.local.yml` starts the data services only.

## Before anyone else can reach the server

- `./generate_config.sh` creates the file encryption key, the VAPID key pair and the LiveKit key and secret in `secrets.env`. **Keep that file private.**
- The RabbitMQ and MinIO passwords in `compose.yml` are public example values, published with the upstream project. Replace each one; generate it with `openssl rand -base64 32`.
- MongoDB and Redis have no password and must stay on the internal Docker network.
- Set your real domain and TLS yourself. The localhost values are for local testing only.

## What belongs in Git

Only templates and reviewed source. Keep the real server configuration, credentials, databases, backups and logs outside the checkout. Do not run inherited upstream application images as a Zrzur server. More: [PUBLICATION_POLICY.md](./PUBLICATION_POLICY.md).

## What is inside

| Path | Role |
| --- | --- |
| `compose.yml` | The whole stack |
| `compose.local.yml` | The data services only |
| `Caddyfile` | Reverse proxy |
| `generate_config.sh` | Creates the configuration and the keys |
| `secrets.env.example` | The names of the secrets, with no values |
| `migrations/` | Database migrations |

The parts it runs:

- [Backend](https://github.com/zrzur/backend): the Rust services
- [Web](https://github.com/zrzur/web): the browser app, built for one API address
- [Desktop](https://github.com/zrzur/desktop): the desktop app, pointed at your web address

## Contributing and security

- Contributing: [CONTRIBUTING.md](./CONTRIBUTING.md).
- Security reports: [SECURITY.md](./SECURITY.md).

## Licence and origin

Zrzur is an independent, Arabic-first chat platform based on the open-source Stoat software (formerly Revolt), licensed under AGPL-3.0 or later. Zrzur is not affiliated with Stoat, stoat.chat or Revolt Platforms Ltd. Please do not report Zrzur issues to the Stoat team.

- Licence: AGPL-3.0-or-later, see [LICENSE](./LICENSE).
- Upstream: [stoatchat/self-hosted](https://github.com/stoatchat/self-hosted).
- Notices and changes: [NOTICE](./NOTICE), [MODIFICATIONS.md](./MODIFICATIONS.md), [THIRD-PARTY-LICENSES.md](./THIRD-PARTY-LICENSES.md).
