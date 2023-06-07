#!/bin/bash

DATA_DIR=../data/2023may18/synonyms
SYNONYM_FILENAMES=($DATA_DIR/*.txt.gz)

echo ${SYNONYM_FILENAMES[*]}

# Combine files into a single giant combined.tsv.gz file.
gunzip -c ${SYNONYM_FILENAMES[*]} | jq -r '[ .curie, (.types | join("|")), .preferred_name ] | @tsv' |gzip > $DATA_DIR/combined.tsv.gz
