#!/usr/bin/env bash
# Fails if the built site (_site/) has a broken internal link, image, script or
# in-page anchor. External links (Google Fonts) are not checked.
# Run after `bundle exec jekyll build`:   scripts/check_links.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# If a baseurl is set (e.g. "/website"), links in the built pages start with it
# but the files in _site/ don't, so tell html-proofer to strip it. The site
# now runs at the domain root (empty baseurl), so there is nothing to strip.
baseurl=$(ruby -ryaml -e 'puts(YAML.load_file("_config.yml")["baseurl"] || "")')
args=(./_site --disable-external --no-enforce-https)
if [ -n "$baseurl" ]; then
  args+=(--swap-urls "^${baseurl}:")
fi

LC_ALL=C.UTF-8 bundle exec htmlproofer "${args[@]}"
