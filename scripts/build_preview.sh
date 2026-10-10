#!/usr/bin/env bash
# The hidden preview copy of the site: the same pages, built from the sample
# season, into _site/preview/ (published at /preview/, with the sample banner).
# Nothing links to it and every page carries the noindex tag. Run it after the
# main `jekyll build` (which would otherwise wipe _site/preview/):
#   scripts/build_preview.sh
# It does nothing when `preview_site` is false in _config.yml, or when
# `sample_data` is on (then the main site already shows the sample season).
# Afterwards it rebuilds the stats for the main site, so _data/computed/ and
# score-sheets/ match _config.yml again.
set -euo pipefail
cd "$(dirname "$0")/.."

read -r enabled sample <<<"$(python3 -c 'import yaml; c = yaml.safe_load(open("_config.yml")); print(bool(c.get("preview_site")), bool(c.get("sample_data")))')"
if [ "$enabled" != "True" ] || [ "$sample" = "True" ]; then
  echo "Preview site: skipped (preview_site: $enabled, sample_data: $sample)"
  exit 0
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
# Everything in _config.yml, plus: show the sample season, live under /preview.
python3 - "$tmp/preview-config.yml" <<'PY'
import sys, yaml
config = yaml.safe_load(open("_config.yml"))
config.update(sample_data=True, baseurl="/preview", preview_build=True)
config["exclude"] = config.get("exclude", []) + ["CNAME"]   # the domain file belongs at the root only
yaml.safe_dump(config, open(sys.argv[1], "w"), sort_keys=False)
PY
python3 scripts/build_stats.py --config "$tmp/preview-config.yml"
scripts/make_score_sheets.sh
JEKYLL_ENV=${JEKYLL_ENV:-production} bundle exec jekyll build --config "_config.yml,$tmp/preview-config.yml" -d _site/preview
echo "Preview site: _site/preview/ (sample season)"

# Back to the main site's data.
python3 scripts/build_stats.py >/dev/null
scripts/make_score_sheets.sh >/dev/null
