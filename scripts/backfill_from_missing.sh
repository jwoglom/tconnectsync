#!/bin/bash

PIPENV=/home/$(whoami)/.local/bin/pipenv

echo "Most recent upload:"
mongo --quiet nightscout --eval 'JSON.stringify(db.treatments.find({"enteredBy":"Pump (tconnectsync)"}).sort({_id: -1}).limit(1)[0])' | jq

SINCE_DATETIME=$(mongo --quiet nightscout --eval 'JSON.stringify(db.treatments.find({"enteredBy":"Pump (tconnectsync)"}).sort({_id: -1}).limit(1)[0])' | jq -r '.created_at')

SINCE_DATE=$(python3 -c "print('$SINCE_DATETIME'.split(' ')[0])")
CUR_DATE=$(python3 -c "import datetime; print(str(datetime.datetime.now()).split(' ')[0])")
echo "Will run with start date $SINCE_DATE and end date $CUR_DATE"

PRETEND="--pretend"
$PIPENV run python3 -u ../main.py --start-date "$SINCE_DATE" --end-date "$CUR_DATE" $PRETEND