#!/bin/sh
# Standalone library candidate, not an Alpine distribution upgrade.
# SQLite 3.54.1 is upstream stable, packaged on Alpine's pre-release 3.25 branch.
set -eu
arch=$(apk --print-arch)
case "$arch" in
  x86_64)
    sqlite_hash=5dfd76936e795efd988d6bad4949b8d20c410d6dc9dd256da884111f668f3915
    zlib_hash=7b05bc778b8b25cd880835b40114182bd4d1581717504d0129c810c0a14291cb
    ;;
  aarch64)
    sqlite_hash=a7c1a639e294538e1ee773bbd8b13abb6c02bbd5400222f31d1627f4ca8e92ce
    zlib_hash=d3e30d012a3445222b0b4a28f1d4d97ce67387f8b48561921111696da174f0de
    ;;
  *) echo 'Unsupported runtime architecture' >&2; exit 1 ;;
esac
patch_dir=$(mktemp -d)
trap 'rm -rf "$patch_dir"' EXIT
origin=https://dl-cdn.alpinelinux.org/alpine
sqlite_url=$origin/v3.25/main/$arch/sqlite-libs-3.54.1-r0.apk
zlib_url=$origin/v3.24/main/$arch/zlib-1.4-r0.apk
wget -q -O "$patch_dir/sqlite.apk" "$sqlite_url"
wget -q -O "$patch_dir/zlib.apk" "$zlib_url"
printf '%s  %s\n%s  %s\n' "$sqlite_hash" "$patch_dir/sqlite.apk" "$zlib_hash" "$patch_dir/zlib.apk" | sha256sum -c -
# APK checks signatures with the trusted keys in the pinned base. No repository
# change, online dependency resolution or signature bypass is permitted.
apk add --no-cache --no-network "$patch_dir/sqlite.apk" "$patch_dir/zlib.apk"
apk info -v sqlite-libs zlib
if apk info -e sqlite || command -v sqlite3; then
  echo 'Unexpected SQLite CLI invalidates library-only applicability' >&2
  exit 1
fi
python - <<'PY'
import sqlite3
import zlib
assert sqlite3.sqlite_version == "3.54.1", "Loaded SQLite does not match patch"
assert zlib.ZLIB_RUNTIME_VERSION == "1.4", "Loaded zlib does not match patch"
with sqlite3.connect(":memory:") as db:
    db.execute("CREATE TABLE proof (value TEXT)")
    db.execute("INSERT INTO proof VALUES (?)", ("owned-check",))
    assert db.execute("SELECT value FROM proof").fetchone() == ("owned-check",)
    assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
PY
mkdir -p /usr/local/share/dusk
printf '%s %s\n%s %s\n' "$sqlite_hash" "$sqlite_url" "$zlib_hash" "$zlib_url" \
  > /usr/local/share/dusk/os-patches.txt
