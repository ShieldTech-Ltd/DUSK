#!/bin/sh
# Execute the real shell runner with controlled Docker/Python substitutes.
set -eu
test_dir=$(mktemp -d)
trap 'rm -rf "$test_dir"' EXIT
mkdir -p "$test_dir/harness/scripts" "$test_dir/bin"
cp dusk-agent-harness/scripts/run_ci_sandbox.sh "$test_dir/harness/scripts/"
cat > "$test_dir/bin/docker" <<'SH'
#!/bin/sh
case " $* " in
  *' run '*) touch "$EXIT_TEST_LOAD_MARKER" ;;
esac
exit 0
SH
cat > "$test_dir/bin/python" <<'SH'
#!/bin/sh
printf '{"owned_test":true}\n'
exit "$EXIT_TEST_VERIFY_STATUS"
SH
chmod +x "$test_dir/bin/docker" "$test_dir/bin/python"
for mode in watch enforce; do
  for injected in 0 7; do
    marker="$test_dir/$mode-$injected-load"
    result=0
    PATH="$test_dir/bin:$PATH" DUSK_GATE_API_KEY=owned-test-only \
      EXIT_TEST_LOAD_MARKER="$marker" EXIT_TEST_VERIFY_STATUS="$injected" \
      sh "$test_dir/harness/scripts/run_ci_sandbox.sh" "$mode" > "$test_dir/output" 2>&1 || result=$?
    if test "$injected" = 0; then
      test "$result" = 0
      test -f "$marker"
    else
      test "$result" != 0
      test ! -e "$marker"
      grep -q 'containment verification failed' "$test_dir/output"
    fi
  done
done
echo 'Sandbox verifier failure propagation passed in watch and enforce modes'
