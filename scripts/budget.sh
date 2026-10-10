#!/bin/bash
added=$(git diff --numstat HEAD | awk '{s+=$1} END {print s+0}')
[ "$added" -gt "$1" ] && echo "OVER BUDGET: $added > $1" && exit 1 || echo "ok: $added/$1"