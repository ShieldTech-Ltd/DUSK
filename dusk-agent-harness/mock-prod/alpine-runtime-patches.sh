#!/bin/sh
# Standalone library candidate, not an Alpine distribution upgrade.
# SQLite 3.54.1 is upstream stable, packaged on Alpine's pre-release 3.25 branch.
set -eu
arch=$(apk --print-arch)
case "$arch" in
  x86_64)
    sqlite_hash=5dfd76936e795efd988d6bad4949b8d20c410d6dc9dd256da884111f668f3915
    zlib_hash=7b05bc778b8b25cd880835b40114182bd4d1581717504d0129c810c0a14291cb
    libcrypto_hash=042026082cc9bc7872d1baa81755c50efa70b05f03b5369fdc5f0a1303009720
    libssl_hash=18c5778cbe52e1991303f8531970b05d4e6e036ea08349322f7422f42a689dc7
    ;;
  aarch64)
    sqlite_hash=a7c1a639e294538e1ee773bbd8b13abb6c02bbd5400222f31d1627f4ca8e92ce
    zlib_hash=d3e30d012a3445222b0b4a28f1d4d97ce67387f8b48561921111696da174f0de
    libcrypto_hash=58ea027d8bd64fffac7d2106a9034341d6735387298a5e01b551429c73a13c71
    libssl_hash=4aff30f84e7ac922b026f8b2dd574d91bb3bb01d22767a8a9a0a10c5ef64a44b
    ;;
  *) echo 'Unsupported runtime architecture' >&2; exit 1 ;;
esac
patch_dir=$(mktemp -d)
trap 'rm -rf "$patch_dir"' EXIT
origin=https://dl-cdn.alpinelinux.org/alpine
sqlite_url=$origin/v3.25/main/$arch/sqlite-libs-3.54.1-r0.apk
zlib_url=$origin/v3.24/main/$arch/zlib-1.4-r0.apk
openssl_revision=3.5.9-r1
libcrypto_url=$origin/v3.24/main/$arch/libcrypto3-$openssl_revision.apk
libssl_url=$origin/v3.24/main/$arch/libssl3-$openssl_revision.apk
wget -q -O "$patch_dir/sqlite.apk" "$sqlite_url"
wget -q -O "$patch_dir/zlib.apk" "$zlib_url"
printf '%s  %s\n%s  %s\n' "$sqlite_hash" "$patch_dir/sqlite.apk" "$zlib_hash" "$patch_dir/zlib.apk" | sha256sum -c -
# APK checks signatures with the trusted keys in the pinned base. No repository
# change, online dependency resolution or signature bypass is permitted.
wget -q -O "$patch_dir/libcrypto.apk" "$libcrypto_url"
wget -q -O "$patch_dir/libssl.apk" "$libssl_url"
printf '%s  %s\n' "$libcrypto_hash" "$patch_dir/libcrypto.apk" \
  "$libssl_hash" "$patch_dir/libssl.apk" | sha256sum -c -
apk add --no-cache --no-network "$patch_dir/sqlite.apk" "$patch_dir/zlib.apk" \
  "$patch_dir/libcrypto.apk" "$patch_dir/libssl.apk"
apk info -v sqlite-libs zlib
apk info -v libcrypto3 | grep -Fx "libcrypto3-$openssl_revision"
apk info -v libssl3 | grep -Fx "libssl3-$openssl_revision"
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
printf '%s %s\n' "$libcrypto_hash" "$libcrypto_url" "$libssl_hash" "$libssl_url" \
  >> /usr/local/share/dusk/os-patches.txt
