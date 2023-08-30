#!/usr/bin/env bash

set -e

echo "Extracting translatable strings from django"
for d in peachjam africanlii liiweb tanzlii zanzibarlii; do
  pushd $d
  django-admin makemessages -a --no-wrap
  popd
done

echo "Extracting translatable strings from javascript"
i18next './peachjam/js/**/*.{js,ts,vue}'
