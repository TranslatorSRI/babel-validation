#!/bin/bash

DATE=2023jul13
DOWNLOAD_URL=https://stars.renci.org/var/babel_outputs/$DATE/synonyms/
DATA_DIR=../data/$DATE/synonyms
mkdir -p $DATA_DIR
wget --recursive --no-parent --no-clobber --no-host-directories --cut-dirs=4 -R "index.html" $DOWNLOAD_URL -P $DATA_DIR

SYNONYM_FILENAMES=($DATA_DIR/*.txt.gz)
echo ${SYNONYM_FILENAMES[*]}

# Combine files into a single giant combined.tsv.gz file.
gunzip -c ${SYNONYM_FILENAMES[*]} | jq -r '[ .curie, (.types | join("|")), .preferred_name ] | @tsv' |gzip > $DATA_DIR/combined.tsv.gz
