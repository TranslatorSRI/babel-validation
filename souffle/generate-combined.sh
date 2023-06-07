#!/bin/bash

SYNONYM_FILENAMES=(../data/2023may18/synonyms/*.txt.gz)

echo ${SYNONYM_FILENAMES[*]}

# Combine files into a single giant combined.tsv.gz file.
gunzip -c ${SYNONYM_FILENAMES[*]} | jq -r '[ .curie, (.types | join("|")), .preferred_name ] | @tsv' |gzip > combined.tsv.gz
