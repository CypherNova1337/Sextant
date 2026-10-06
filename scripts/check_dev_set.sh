#!/bin/sh
# Verify the reference fix of every dev task in the Docker sandbox, one task
# at a time: download its snapshot, check it, then delete the snapshot unless
# it is kept for agent runs. Results append to runs/reference/dev.jsonl, so an
# interrupted run resumes where it stopped.
cd "$(dirname "$0")/.."
out=runs/reference/dev.jsonl
mkdir -p runs/reference
keep="rich_3454 rich_4077 rich_3006 rich_3063 requests_7315 fastapi_14430 rich_3480 rich_3278 requests_6644 rich_3043 fastapi_14786 fastapi_14297 fastapi_14616 rich_3905"
for t in $(cat splits/dev.txt); do
    grep -q "\"id\": \"$t\"" "$out" 2>/dev/null && continue
    snap=data/snapshots/$t.tgz
    if [ ! -e "$snap" ]; then
        for i in 1 2 3 4; do
            kaggle competitions download -c gemma-4-developer-agent -f "snapshots/$t.tgz" -p data/snapshots -q >/dev/null 2>&1 && break
            sleep $((i * 10))
        done
    fi
    [ -e "$snap" ] || { echo "{\"id\": \"$t\", \"ok\": null, \"error\": \"download failed\"}" >> "$out"; continue; }
    LITELLM_LOCAL_MODEL_COST_MAP=True timeout 900 /home/user/venv/bin/python scripts/verify_reference.py --out "$out" "$t" 2>&1 | grep 'ok='
    case " $keep " in *" $t "*) ;; *) rm -f "$snap" ;; esac
done
