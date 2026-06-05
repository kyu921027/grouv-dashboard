#!/bin/bash
# Grouv Daily Dashboard Runner
# Credentials read from /tmp/grouv_creds.env

set -eo pipefail
source /tmp/grouv_creds.env

echo "=== STEP 1: Calculate dates ==="
python3 -c "
from datetime import date, timedelta
today = date.today()
today_str = today.strftime('%Y-%m-%d')
wd = today.weekday()
ws = today - timedelta(days=wd)
we = ws + timedelta(days=6)
pe = date(today.year, today.month, 1) - timedelta(days=1)
ps = date(pe.year, pe.month, 1)
ppe = date(ps.year, ps.month, 1) - timedelta(days=1)
pps = date(ppe.year, ppe.month, 1)
ts = date(today.year, today.month, 1)
open('/tmp/dates.txt','w').write('|'.join(str(x) for x in [today_str,ws,we,ps,pe,pps,ppe,ts]) + '\n')
print('dates saved')
"

IFS='|' read -r TODAY WEEK_START WEEK_END PREV_START PREV_END PP_START PP_END THIS_START < /tmp/dates.txt
echo "Today=$TODAY prev=$PREV_START~$PREV_END pp=$PP_START~$PP_END"

echo "=== STEP 2: Collect Granter data ==="

collect_granter_cli() {
  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" || true
  # Refresh PATH to pick up newly installed granter
  export PATH="$NVM_DIR/versions/node/$(node -v 2>/dev/null | tr -d v)/bin:$PATH"
  npm install -g @granter-biz/cli 2>/dev/null || true
  GRANTER_BIN=$(which granter 2>/dev/null || find "$NVM_DIR" -name granter -type f 2>/dev/null | head -1)
  [ -z "$GRANTER_BIN" ] && return 1
  "$GRANTER_BIN" config --api-key "$GRANTER_KEY" 2>/dev/null || return 1
  "$GRANTER_BIN" tickets --type BANK_TRANSACTION_TICKET --from "$PREV_START" --to "$PREV_END" > /tmp/prev_tickets.json 2>/dev/null || return 1
  "$GRANTER_BIN" tickets --type BANK_TRANSACTION_TICKET --from "$PP_START" --to "$PP_END" > /tmp/pp_tickets.json 2>/dev/null || return 1
  "$GRANTER_BIN" tickets --type BANK_TRANSACTION_TICKET --from "$THIS_START" --to "$TODAY" > /tmp/this_tickets.json 2>/dev/null || return 1
  "$GRANTER_BIN" assets --type BANK_ACCOUNT > /tmp/assets.json 2>/dev/null || return 1
}

collect_npx() {
  npx --yes @granter-biz/cli tickets --type BANK_TRANSACTION_TICKET --from "$PREV_START" --to "$PREV_END" > /tmp/prev_tickets.json 2>/dev/null || return 1
  npx --yes @granter-biz/cli tickets --type BANK_TRANSACTION_TICKET --from "$PP_START" --to "$PP_END" > /tmp/pp_tickets.json 2>/dev/null || return 1
  npx --yes @granter-biz/cli tickets --type BANK_TRANSACTION_TICKET --from "$THIS_START" --to "$TODAY" > /tmp/this_tickets.json 2>/dev/null || return 1
  npx --yes @granter-biz/cli assets --type BANK_ACCOUNT > /tmp/assets.json 2>/dev/null || return 1
}

collect_curl() {
  curl -sf -H "Authorization: Bearer $GRANTER_KEY" \
    "https://api.granter.biz/v1/tickets?type=BANK_TRANSACTION_TICKET&from=$PREV_START&to=$PREV_END" > /tmp/prev_tickets.json || return 1
  curl -sf -H "Authorization: Bearer $GRANTER_KEY" \
    "https://api.granter.biz/v1/tickets?type=BANK_TRANSACTION_TICKET&from=$PP_START&to=$PP_END" > /tmp/pp_tickets.json || return 1
  curl -sf -H "Authorization: Bearer $GRANTER_KEY" \
    "https://api.granter.biz/v1/tickets?type=BANK_TRANSACTION_TICKET&from=$THIS_START&to=$TODAY" > /tmp/this_tickets.json || return 1
  curl -sf -H "Authorization: Bearer $GRANTER_KEY" \
    "https://api.granter.biz/v1/assets?type=BANK_ACCOUNT" > /tmp/assets.json || return 1
}

validate_json() {
  python3 -c "
import json, sys
try:
  d = json.load(open('/tmp/prev_tickets.json'))
  if isinstance(d, list): sys.exit(0)
  for k in ('data','items','tickets','result'):
    if k in d and isinstance(d[k], list): sys.exit(0)
  sys.exit(1)
except: sys.exit(1)
"
}

STATUS="UNKNOWN"
if collect_granter_cli && validate_json; then
  STATUS="A:OK"
elif collect_npx && validate_json; then
  STATUS="B:OK"
elif collect_curl && validate_json; then
  STATUS="C:OK"
else
  STATUS="ALL_FAILED"
  echo "[]" | tee /tmp/prev_tickets.json /tmp/pp_tickets.json /tmp/this_tickets.json /tmp/assets.json > /dev/null
fi
echo "$STATUS" > /tmp/collect_status.txt
echo "Collect status: $STATUS"

echo "=== STEP 3: Run analysis ==="
curl -s -H "Authorization: token $GH_TOKEN" \
  -H "Accept: application/vnd.github.v3.raw" \
  "https://api.github.com/repos/$REPO/contents/scripts/analyze.py" \
  -o /tmp/analyze.py
python3 /tmp/analyze.py

echo "=== STEP 4: Upload to GitHub Pages ==="
python3 << PYEOF
import base64, urllib.request, json
today_str = open('/tmp/dates.txt').read().split('|')[0]
import os
TOKEN = os.environ.get('GH_TOKEN','')
REPO  = os.environ.get('REPO','kyu921027/grouv-dashboard')
with open(f'/tmp/dashboard_{today_str}.html','rb') as f:
    b64 = base64.b64encode(f.read()).decode()
def gh(path, method='GET', data=None):
    req = urllib.request.Request(
        f'https://api.github.com/repos/{REPO}/contents/{path}',
        data=json.dumps(data).encode() if data else None,
        method=method,
        headers={'Authorization':f'token {TOKEN}','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req) as r: return json.loads(r.read())
    except urllib.error.HTTPError as e: return json.loads(e.read())
sha = gh('index.html').get('sha','')
gh('index.html','PUT',{'message':f'Daily update {today_str}','content':b64,'sha':sha})
arch_sha = gh(f'archive/dashboard_{today_str}.html').get('sha','')
gh(f'archive/dashboard_{today_str}.html','PUT',{'message':f'Archive','content':b64,'sha':arch_sha})
print('Upload done: https://kyu921027.github.io/grouv-dashboard/')
PYEOF

echo "=== Runner complete ==="
cat /tmp/summary.txt
