<!-- zrzur-publication -->
# Quick start

```bash
git clone https://github.com/zrzur/self-hosted.git
cd self-hosted
./generate_config.sh your.domain
docker compose config --quiet
docker compose up -d
```

Needs Git, Bash and Docker. The application images (`ghcr.io/zrzur/*`) are not published yet: until they are, build them from [zrzur/backend](https://github.com/zrzur/backend) and [zrzur/web](https://github.com/zrzur/web). `compose.local.yml` starts the data services only.

## Default values are examples

`./generate_config.sh` creates the file encryption key, the VAPID key pair and the LiveKit key and secret in `secrets.env`; keep that file private. The RabbitMQ and MinIO passwords in `compose.yml` are public example values, published with the upstream project: replace them before anyone else can reach the server, and generate each with `openssl rand -base64 32`. MongoDB and Redis have no password and must stay on the internal Docker network.

Zrzur is an independent, Arabic-first chat platform based on the open-source Stoat software (formerly Revolt), licensed under AGPL-3.0 or later. Zrzur is not affiliated with Stoat, stoat.chat or Revolt Platforms Ltd. Please do not report Zrzur issues to the Stoat team.

Licence and origin: [LICENSE](./LICENSE), [NOTICE](./NOTICE), [MODIFICATIONS.md](./MODIFICATIONS.md). Security: [SECURITY.md](./SECURITY.md). Contributing: [CONTRIBUTING.md](./CONTRIBUTING.md).

# Zrzur Self-hosted

Deployment source and configuration templates for the Zrzur backend, web, desktop companion services, storage and LiveKit. See [release preparation](ZRZUR_RELEASE.md) and [publication policy](PUBLICATION_POLICY.md).

## Configuration boundaries

Only templates and reviewed source belong in Git. Store actual server configuration, credentials, databases, backups and logs outside the checkout. Real production origins and TLS must be configured explicitly; localhost examples are for local testing only. Do not run inherited upstream application images as Zrzur production services.

## Components

- [Backend](https://github.com/zrzur/backend): locally built Rust application services.
- [Web](https://github.com/zrzur/web): Solid web client, built against an explicit API origin.
- [Desktop](https://github.com/zrzur/desktop): Electron client requiring an approved application origin.

## Upstream and license

Forked from [Stoat self-hosted infrastructure](https://github.com/stoatchat/self-hosted). Required attribution is preserved (see NOTICE). [AGPL license](LICENSE).
