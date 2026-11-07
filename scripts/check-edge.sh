#!/usr/bin/env bash
# Runs both Caddyfiles in a throwaway Caddy container with stand-in upstreams and
# checks what actually answers: internal paths stay closed, only Cloudflare reaches
# the main server, and a client cannot choose its own address.
# Caddy sorts directives by its own order, not file order, so a valid config can
# still skip a rule; `caddy validate` alone does not show that.
set -euo pipefail
export MSYS_NO_PATHCONV=1

native() { (cd "$1" && { pwd -W 2>/dev/null || pwd; }); }
root="$(native "$(dirname "$0")/..")"
image="$(sed -n 's/^ *image: \(docker.io\/\)\{0,1\}\(caddy:.*\)$/\2/p' "$root/compose.yml" | head -1)"
work="$(native "$(mktemp -d)")"
trap 'rm -rf "$work"' EXIT

mkdir "$work/zrzur"
# the rule files as prepare-config.py writes them, with a placeholder for the ranges
"${PYTHON:-python3}" - "$root/production/prepare-config.py" "$work/zrzur" <<'PY'
import importlib.util, pathlib, sys
spec = importlib.util.spec_from_file_location('prepare_config', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
for name, content in module.caddy_files('RANGES').items():
    (pathlib.Path(sys.argv[2]) / name).write_text(content)
PY
# no TLS in the test: every site answers on port 80
sed -E 's#^([a-z][a-z.]*\.(com|cc)) \{#http://\1 {#' "$root/production/Caddyfile" > "$work/production.caddy"
cp "$root/Caddyfile" "$work/quickstart.caddy"

cat > "$work/probe.sh" <<'SH'
set -u
ip="$(hostname -i | awk '{print $1}')"
failed=0
status() { # host path [extra header]
  wget -S -qO /dev/null --header "Host: $1" ${3:+--header "$3"} "http://$ip$2" 2>&1 |
    awk '/HTTP\//{print $2; exit}'
}
expect() { # want host path
  got="$(status "$2" "$3")"
  if [ "$got" = "$1" ]; then echo "ok   $got $2$3"; else echo "FAIL $got (want $1) $2$3"; failed=1; fi
}
body() { wget -qO- --header "Host: x" ${1:+--header "$1"} "http://$ip/api/ok"; }
expect_body() { # want header
  got="$(body "$2")"
  if [ "$got" = "$1" ]; then echo "ok   $got"; else echo "FAIL $got (want $1)"; failed=1; fi
}
up() {
  cat > /tmp/run.caddy <<CADDY
import $1
http://:5000, http://:14702, http://:14703, http://:14704, http://:14705, http://:14706, http://:8500 {
	respond "xff={http.request.header.x-forwarded-for}" 200
}
CADDY
  caddy run --adapter caddyfile --config /tmp/run.caddy > /tmp/caddy.log 2>&1 &
  pid=$!
  sleep 1
}
down() { kill "$pid"; wait "$pid" 2>/dev/null; }

case "$MODE" in
quickstart)
  up /w/quickstart.caddy
  for p in /api/metrics /api/metrics/x /api/METRICS /api//metrics /api/./metrics; do expect 404 x "$p"; done
  expect 200 x /api/ok
  expect_body "xff=$ip" ""
  expect_body "xff=$ip" "X-Forwarded-For: 6.6.6.6"
  ;;
quickstart-proxied)
  up /w/quickstart.caddy
  expect 404 x /api/metrics
  expect_body "xff=6.6.6.6" "X-Forwarded-For: 6.6.6.6"
  expect_body "xff=7.7.7.7" "X-Forwarded-For: 6.6.6.6, 7.7.7.7"
  ;;
production)
  mkdir -p /etc/caddy/zrzur
  for f in /w/zrzur/*; do sed "s#RANGES#$ip/32#" "$f" > "/etc/caddy/zrzur/$(basename "$f")"; done
  up /w/production.caddy
  for p in /metrics /metrics/x /METRICS //metrics /./metrics; do expect 404 api.zrzur.com "$p"; done
  for p in /ok /january/x /gifbox/x /ingress/x; do expect 200 api.zrzur.com "$p"; done
  for h in app beta discover designs ws cdn; do expect 200 "$h.zrzur.com" /; done
  down
  for f in /w/zrzur/*; do sed "s#RANGES#203.0.113.0/24#" "$f" > "/etc/caddy/zrzur/$(basename "$f")"; done
  up /w/production.caddy
  for p in /ok /metrics /january/x /gifbox/x /ingress/x; do expect 403 api.zrzur.com "$p"; done
  for h in app.zrzur.com beta.zrzur.com discover.zrzur.com designs.zrzur.com admin.zrzur.com ws.zrzur.com cdn.zrzur.com zrzur.com status.zrzur.com; do expect 403 "$h" /; done
  ;;
esac
exit "$failed"
SH

hosts=()
for h in api events autumn january gifbox voice-ingress web web-beta discover designs; do
  hosts+=(--add-host "$h:127.0.0.1")
done
rc=0
run() { # mode [env]
  echo "== $1"
  docker run --rm "${hosts[@]}" -e HOSTNAME=:80 -e "MODE=$1" ${2:+-e "$2"} \
    -v "$work:/w:ro" "$image" sh /w/probe.sh || rc=1
}
run quickstart
run quickstart-proxied TRUSTED_PROXIES=private_ranges
run production
exit "$rc"
