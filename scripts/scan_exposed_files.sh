#!/usr/bin/env bash
# Fails if Git tracks sensitive files or if .gitignore is missing a rule for them.
set -u
cd "$(git rev-parse --show-toplevel)" || exit 2
status=0

tracked=$(git ls-files | grep -E '(^|/)(\.env(\..*)?|credentials[^/]*\.json|token[^/]*\.json|client_secret[^/]*\.json|id_rsa)$|(^|/)secrets/|\.(db|sqlite3?|pem|key|p12|bak|dump|jsonl|log)$' | grep -v -E '(^|/)\.env\.example$')
if [ -n "$tracked" ]; then
  echo "FAIL: sensitive files tracked by Git:"
  echo "$tracked"
  status=1
fi

for path in .env .env.local secrets/x instance/gloz.sqlite3 logs/security.jsonl credentials.json backup.bak server.key; do
  if ! git check-ignore -q "$path"; then
    echo "FAIL: .gitignore does not cover $path"
    status=1
  fi
done

[ "$status" -eq 0 ] && echo "OK: no sensitive files exposed."
exit "$status"
