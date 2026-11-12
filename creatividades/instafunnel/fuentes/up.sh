#!/bin/bash
# usage: up.sh NAME URL  -> appends "NAME mediaId" to ids.txt
r=$(curl -sS -X POST -H "Content-Type: application/octet-stream" --data-binary @png/$1.png "$2")
id=$(echo "$r" | python3 -c "import sys,json;print(json.load(sys.stdin).get('mediaId',''))" 2>/dev/null)
if [ -n "$id" ]; then echo "$1 $id" >> ids.txt; echo "$1 OK $id"; else echo "$1 FAIL $r"; fi
