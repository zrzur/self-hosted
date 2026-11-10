# Zrzur main-server production stack

Runs zrzur.com (website), app.zrzur.com (Zrzur), beta.zrzur.com (Zrzur Beta), api/events/cdn.zrzur.com, and the team console on 127.0.0.1:8090 (SSH tunnel only, no public hostname) on the main server behind Cloudflare. Stable and Beta use the same backend. Voice (LiveKit) runs on the separate voice server. Nothing here is built on the server: images are built by the `Container images` workflows of [zrzur/backend](https://github.com/zrzur/backend) and [zrzur/web](https://github.com/zrzur/web) and pulled from `ghcr.io/zrzur`.

## Files

| File | Purpose |
|---|---|
| `compose.yml` | Services. Data services publish no ports; only the proxy publishes 80/443. Image tags are required. |
| `Caddyfile` | Hostnames and routes. Requests that do not come from Cloudflare get 403. |
| `bootstrap-host.sh` | Fresh-host preparation: 4 GB swap, Docker, clone of this repository. Builds and starts nothing. |
| `enter-storage.py` | Hidden console input for the S3 key, saved to `/etc/zrzur/storage.json` (mode 600). |
| `enter-smtp.py` | Hidden console input for the Resend API key, saved to `/etc/zrzur/smtp.json` (mode 600). |
| `enter-captcha.py` | Console input for the hCaptcha site key and hidden secret, saved to `/etc/zrzur/captcha.json` (mode 600). |
| `prepare-config.py` | Generates `/etc/zrzur/Revolt.toml`, the data-service env files and the Cloudflare range files. Prints no secrets and starts nothing. |

Secrets are never stored in this repository, in shell history or in chat.

## Order

0. On a fresh Ubuntu 24.04 host: `bash bootstrap-host.sh` (swap, Docker, clone of this repository in `/opt/zrzur/self-hosted`).
1. As root on the main server: `ZRZUR_S3_ENDPOINT=<your S3 endpoint> python3 enter-storage.py` (once), copy the voice server's LiveKit key/secret to `/etc/zrzur/voice.json` (mode 600, never through chat), then `python3 prepare-config.py`.
2. Choose the reviewed image tags, e.g. in `/opt/zrzur/main/.env`:
   `ZRZUR_BACKEND_TAG=26.0.0`, `ZRZUR_WEB_TAG=26.0.0` and `ZRZUR_WEB_BETA_TAG=26.1.0-beta.1` (or `sha-<commit>`).
   Put the built website in `/opt/zrzur/website` (`npm run build` in zrzur/website, its `dist/`) and the built admin console in `/opt/zrzur/admin` (`VITE_API_URL=https://api.zrzur.com pnpm build`, its `dist/`). Both are mounted read-only into the proxy.
3. `docker compose config --quiet`, then `docker compose pull`.
4. Starting the stack replaces the TLS bootstrap proxy of the same project; it is an explicit deployment step.

## Voice server

On the voice server: `bash bootstrap-host.sh`, then `ZRZUR_VOICE_IP=<public IPv4 of the voice server> python3 voice/prepare-voice.py` and `docker compose up -d` in `/opt/zrzur/voice`. It generates the LiveKit key/secret on that server and sends signed webhooks to `https://api.zrzur.com/ingress/fra`. Copy `/opt/zrzur/voice/credentials.json` to `/etc/zrzur/voice.json` on main through an SSH pipe before `prepare-config.py`.

Registration is invite-only.

## Email (Resend)

Email is off until a sending key exists: no verification or password-reset mail is sent. To enable it, verify `zrzur.com` in Resend (its SPF/DKIM DNS records in Cloudflare), then on main run `python3 enter-smtp.py` (hidden input for the `re_...` key), remove `/etc/zrzur/Revolt.toml`, run `python3 prepare-config.py` and `docker compose up -d --force-recreate api`. Sender: `Zrzur <no-reply@zrzur.com>` via `smtp.resend.com:465`. With email on, new accounts must verify their address.

## Sign-up and captcha

Sign-up is open: anyone can create an account without an invite code (`invite_only = false`). Before opening it on a public server, turn on email (above) so addresses are verified and passwords can be reset, and add hCaptcha: run `python3 enter-captcha.py`, remove `/etc/zrzur/Revolt.toml`, run `python3 prepare-config.py` and `docker compose up -d --force-recreate api`. Without a captcha key, sign-up has only the per-address rate limit.

With the captcha on, sign-in asks for it too, but only for an address that had ten wrong passwords within fifteen minutes. Without it, such an address waits instead (one minute, doubling up to an hour), but only on the network the wrong passwords came from (IPv4 /24, IPv6 /64); a password reset ends the wait. The captcha removes the wait altogether.

## Deploy order (security hardening)

Some pieces depend on each other. Deploy them in this order:

1. **API, then web, before the captcha key.** Deploy the API with the sign-in step-up and the web image whose login form runs the captcha when asked (`app.zrzur.com` and `beta.zrzur.com`). Only then run `enter-captcha.py` and recreate the api: an older web app shown a `CaptchaFailed` answer on sign-in has no way to solve it.
2. **The website before this Caddyfile.** Publish the zrzur.com build that loads `/theme.js` first, then reload Caddy with the new `zrzur.com` block. The older pages have an inline theme script that the new page policy refuses (the page would still work, but Arabic pages would get their right-to-left direction only once the site's script runs).
3. **The web image's environment.** The `web` and `web-beta` services need `CSP_API_URL: http://api:14702` (the page policy reads the API root on the internal network for the voice nodes, files and link proxy) and may name the voice host with `CSP_VOICE: wss://voice.zrzur.com` for the time before the first read. Without them the web server reads the public API address and retries every 15 to 30 seconds until it answers.

## Security headers

Every public site gets HSTS, `nosniff`, a strict referrer and no `Server` header (the `security-headers` snippet in `Caddyfile`). The web app sets its own Content-Security-Policy (`docker/server.js` in the web image), built from the container's `VITE_*` addresses and the API root (files, link proxy, events, voice nodes), read again every ten minutes. Optional variables on the `web` / `web-beta` services: `CSP_API_URL` (where the container reaches the API, if not `VITE_API_URL`), `CSP_CONNECT_EXTRA`, `CSP_FRAME_EXTRA`, `CSP_IMG_EXTRA` (space-separated origins). The website's policy is in its `zrzur.com` block. `scripts/check-edge.sh` checks the headers in a throwaway Caddy.

`prepare-config.py` also writes `/etc/zrzur/internal.env` (`ZRZUR_INTERNAL_TOKEN`, mode 600). The api, discover and designs services read it: the two public sites send the token to the API so their server-side rendering has its own rate-limit bucket. Existing installs get the token on the next run of `prepare-config.py`; then recreate the api, discover and designs containers.

## Team console (admin)

The console has no public hostname. The proxy serves it on `127.0.0.1:8090` of the main server only, and the API accepts staff requests from `http://localhost:8090`. Open it through an SSH tunnel:

```
ssh -N -L 8090:127.0.0.1:8090 zrzur@<main server>
```

then browse to `http://localhost:8090`. Close the tunnel with Ctrl+C.
