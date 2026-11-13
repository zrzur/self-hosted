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
tmpbase="$(native "${TMPDIR:-/tmp}")"
work="$(native "$(mktemp -d "${TMPDIR:-/tmp}/tmp.XXXXXXXXXX")")"
# remove only what mktemp -d just made (tmp.XXXXXXXXXX right inside the
# temporary folder), never an empty path, / or anything else
cleanup() {
  case "$work" in
    "$tmpbase"/tmp.??????????) rm -rf -- "$work" ;;
    *) echo "check-edge: left '$work' in place (not a folder mktemp made)" >&2 ;;
  esac
}
trap cleanup EXIT

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
header() { # host name [path]: the header's value (any answer, error pages too)
  wget -S -qO /dev/null --header "Host: $1" "http://$ip${3:-/}" 2>&1 |
    awk -v name="$2" 'tolower($1) == tolower(name) ":" { $1 = ""; sub(/^ /, ""); print; exit }'
}
expect_header() { # host name text: the header holds the text
  got="$(header "$1" "$2")"
  case "$got" in *"$3"*) echo "ok   $1 $2: $3" ;; *) echo "FAIL $1 $2 lacks $3 (got: $got)"; failed=1 ;; esac
}
expect_upstream() { # host path want: the path the service behind receives
  got="$(header "$1" x-upstream-uri "$2")"
  if [ "$got" = "$3" ]; then echo "ok   $1$2 -> $got"; else echo "FAIL $1$2 reaches '$got' (want $3)"; failed=1; fi
}
expect_script_policy() { # host: script-src 'self' without inline or eval
  got="$(header "$1" content-security-policy | sed -n "s/.*script-src \([^;]*\).*/\1/p")"
  case "$got" in
    *unsafe-inline*|*unsafe-eval*) echo "FAIL $1 script-src too wide: $got"; failed=1 ;;
    *"'self'"*) echo "ok   $1 script-src $got" ;;
    *) echo "FAIL $1 has no script-src 'self' (got: $got)"; failed=1 ;;
  esac
}
expect_body() { # want header
  got="$(body "$2")"
  if [ "$got" = "$1" ]; then echo "ok   $got"; else echo "FAIL $got (want $1)"; failed=1; fi
}
up() {
  cat > /tmp/run.caddy <<CADDY
import $1
http://:5000, http://:14702, http://:14703, http://:14704, http://:14705, http://:14706, http://:8500 {
	header X-Upstream-Uri "{http.request.uri}"
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
  # a stand-in website, so zrzur.com answers 200 with its headers
  mkdir -p /srv/website && echo ok > /srv/website/index.html
  mkdir -p /etc/caddy/zrzur
  for f in /w/zrzur/*; do sed "s#RANGES#$ip/32#" "$f" > "/etc/caddy/zrzur/$(basename "$f")"; done
  up /w/production.caddy
  for p in /metrics /metrics/x /METRICS //metrics /./metrics; do expect 404 api.zrzur.com "$p"; done
  for p in /ok /january/proxy /gifbox/x /ingress/x; do expect 200 api.zrzur.com "$p"; done
  # January serves its proxy at /proxy: only /january comes off the path
  expect_upstream api.zrzur.com '/january/proxy?url=x' '/proxy?url=x'
  expect_upstream api.zrzur.com /gifbox/x /x
  # only January's media proxy is public (C2); /embed and the rest stay closed
  for p in /january/x /january/embed; do expect 404 api.zrzur.com "$p"; done
  for h in app beta discover designs events ws cdn; do expect 200 "$h.zrzur.com" /; done
  # zrzur.cc: the bare domain goes to the website, a code to its invite page,
  # anything else is a 404; www.zrzur.cc answers (it gave Cloudflare a 525)
  expect 302 zrzur.cc /
  expect 302 zrzur.cc /arab-gamers
  expect 302 zrzur.cc /p/abc
  expect 404 zrzur.cc /invite/abc
  expect 308 www.zrzur.cc /abc
  # HTTPS only and no type guessing on every public site that answers 200
  # here (busybox wget shows no headers of redirects and errors, so www,
  # status and zrzur.cc are not read; they import the same snippet)
  for h in zrzur.com app.zrzur.com beta.zrzur.com api.zrzur.com events.zrzur.com ws.zrzur.com cdn.zrzur.com discover.zrzur.com designs.zrzur.com; do
    expect_header "$h" strict-transport-security "max-age=63072000"
    expect_header "$h" x-content-type-options nosniff
  done
  # the app's front door is for search engines, what is behind the sign-in is
  # not; the beta app stays out altogether
  for p in / /login /login/create; do
    got="$(header app.zrzur.com x-robots-tag "$p")"
    if [ -z "$got" ]; then echo "ok   app.zrzur.com$p may be listed"; else echo "FAIL app.zrzur.com$p has x-robots-tag $got"; failed=1; fi
  done
  for p in /settings /server/x/channel/y /login/x /invite/abc; do
    got="$(header app.zrzur.com x-robots-tag "$p")"
    case "$got" in *noindex*) echo "ok   app.zrzur.com$p noindex" ;; *) echo "FAIL app.zrzur.com$p lacks noindex (got: $got)"; failed=1 ;; esac
  done
  expect_header beta.zrzur.com x-robots-tag noindex
  expect 200 app.zrzur.com /robots.txt
  robots="$(wget -qO- --header "Host: app.zrzur.com" "http://$ip/robots.txt")"
  for line in 'Allow: /login$' 'Allow: /assets/' 'Disallow: /'; do
    case "$robots" in *"$line"*) echo "ok   app robots.txt: $line" ;; *) echo "FAIL app robots.txt lacks $line"; failed=1 ;; esac
  done
  # the website's own page policy
  expect_script_policy zrzur.com
  expect_header zrzur.com content-security-policy "frame-ancestors 'none'"
  expect_header zrzur.com content-security-policy "object-src 'none'"
  expect_header zrzur.com referrer-policy strict-origin-when-cross-origin
  expect_header zrzur.com permissions-policy "camera=()"
  down
  for f in /w/zrzur/*; do sed "s#RANGES#203.0.113.0/24#" "$f" > "/etc/caddy/zrzur/$(basename "$f")"; done
  up /w/production.caddy
  for p in /ok /metrics /january/x /gifbox/x /ingress/x; do expect 403 api.zrzur.com "$p"; done
  for h in app.zrzur.com beta.zrzur.com discover.zrzur.com designs.zrzur.com events.zrzur.com ws.zrzur.com cdn.zrzur.com zrzur.com status.zrzur.com; do expect 403 "$h" /; done
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
