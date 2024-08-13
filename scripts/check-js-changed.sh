#!/usr/bin/env bash
# This script checks if compiled javascript files have changed, ignoring the unique debug IDs that
# the sentry-webpack plugin adds to the files.
#
# It exits with code 10 if the files have changed, and 0 if they have not.

for js_file in peachjam/static/js/app-prod.js peachjam/static/js/pdf.worker-prod.js; do
  # get the previous version of the file
  git show HEAD:$js_file > $js_file.head

  for f in $js_file $js_file.head; do
    # remove the debug ids from the first 1000 chars
    head -c 1000 $f | sed -E '
      s/sentryDebugIds\[t\]="[^"]+"/sentryDebugIds[t]=""/g;
      s/sentryDebugIdIdentifier="[^"]+"/sentryDebugIdIdentifier=""/g;
      s/SENTRY_RELEASE=\{id:"[^"]+"\}/SENTRY_RELEASE={id:""}/g' > $f.stripped
    tail -c +1000 $f >> $f.stripped
  done

  diff -q $js_file.stripped $js_file.head.stripped
  if [ $? -ne 0 ]; then
    exit 10
  fi
done
