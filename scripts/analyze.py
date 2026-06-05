import json, sys
from datetime import date, timedelta, datetime

# 날짜 읽기
parts = open('/tmp/dates.txt').read().strip().split('|')
today_str, week_start_s, week_end_s = parts[0], parts[1], parts[2]
pp_end_s = parts[6]

today      = date.today()
week_start = datetime.strptime(week_start_s, '%Y-%m-%d').date()
week_end   = datetime.strptime(week_end_s,   '%Y-%m-%d').date()
pp_end     = datetime.strptime(pp_end_s,     '%Y-%m-%d').date()

# 인건비 포함 고정지출 통합
FIXED_CATS = {
    '기장료','차량임대료','사무실 및 공장 임대료','통신비','소프트웨어구독료',
    '건물관리비','사대보험료(4대보험)','이자비용','직원급여','외주 직원 급여'
}

def classify(cat): return 'fixed' if cat in FIXED_CATS else 'variable'

def load_tickets(path):
    try:
        raw = json.load(open(path))
        if isinstance(raw, list): return raw
        for k in ('data','items','tickets','result','content'):
            if k in raw and isinstance(raw[k], list): return raw[k]
        return []
    except: return []

def analyze(tickets):
    r = {'fixed':0,'variable':0,'revenue':{'상품매출':0,'서비스매출':0,'온라인 매출':0,'기타':0}}
    for t in tickets:
        cat = (t.get('expenseCategory') or {}).get('name','미분류')
        if '단순이체' in cat: continue
        amt = t.get('amount', 0)
        tx  = t.get('transactionType', '')
        if tx == 'OUT':
            r[classify(cat)] += amt
        elif tx == 'IN':
            key = cat if cat in ('상품매출','서비스매출','온라인 매출') else '기타'
            r['revenue'][key] += amt
    return r

prev   = analyze(load_tickets('/tmp/prev_tickets.json'))
pp     = analyze(load_tickets('/tmp/pp_tickets.json'))
this_m = analyze(load_tickets('/tmp/this_tickets.json'))

try:
    raw   = json.load(open('/tmp/assets.json'))
    items = raw if isinstance(raw, list) else raw.get('data', raw.get('items', []))
    accounts, total_balance = [], 0
    for a in items:
        ba = a.get('bankAccount') or a
        if ba.get('isLoan', False): continue
        bal  = ba.get('accountBalance', 0)
        name = ba.get('accountName', ba.get('name', '계좌'))
        accounts.append({'name': name, 'balance': bal})
        total_balance += bal
except:
    total_balance, accounts = 0, []

tag_pp = pp_end.strftime('%m월')
tag_f1 = today.strftime('%m월')
tag_f2 = (date(today.year, today.month, 1) + timedelta(days=32)).strftime('%m월')

def fmt(v): return f'{int(v)//10000:,}만'

# 예측 (전월 기준)
f1 = {'revenue': {k: int(v*0.93) for k,v in prev['revenue'].items()}, 'fixed': prev['fixed'], 'variable': prev['variable']}
f2 = {'revenue': {k: int(v*0.88) for k,v in prev['revenue'].items()}, 'fixed': prev['fixed'], 'variable': prev['variable']}

pp_tr, pp_te = sum(pp['revenue'].values()), pp['fixed'] + pp['variable']
pp_net       = pp_tr - pp_te
f1_tr, f1_te = sum(f1['revenue'].values()), f1['fixed'] + f1['variable']
f1_net       = f1_tr - f1_te
f2_tr, f2_te = sum(f2['revenue'].values()), f2['fixed'] + f2['variable']
f2_net       = f2_tr - f2_te
this_tr, this_te = sum(this_m['revenue'].values()), this_m['fixed'] + this_m['variable']

# 납부 일정 (항목별 개별 행)
FIXED_SCHEDULE = [
    (6,  '기장료 (세무법인다성)',     220000),
    (11, '사대보험료',              2500360),
    (11, 'SW구독 (웹케시)',            27500),
    (15, '차량임대료 (아이엠캐피탈)',  620950),
    (15, '차량임대료 (엠지캐피탈)',    739158),
    (21, '건물관리비',                338670),
    (21, '사무실 임대료',           1650000),
    (26, '이자비용',                1853547),
    (26, '통신비',                     36960),
]
total_fixed = sum(a for _,_,a in FIXED_SCHEDULE)

week_pay = [(d,n,a) for d,n,a in FIXED_SCHEDULE if week_start.day <= d <= week_end.day]
week_pay_html = ''.join(
    f'<tr><td>{d}일</td><td>{n}</td><td style="text-align:right;color:#ef4444;font-weight:700">{a:,}원</td></tr>'
    for d,n,a in week_pay
) or '<tr><td colspan="3" style="text-align:center;color:#94a3b8">이번 주 납부 예정 없음</td></tr>'

all_sched_html = ''.join(
    f'<tr><td>{d}일</td><td>{n}</td><td style="text-align:right;color:#ef4444">{a:,}원</td></tr>'
    for d,n,a in FIXED_SCHEDULE
)

acct_html = ''.join(
    f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f1f5f9">'
    f'<span style="color:#64748b">{a["name"]}</span><strong>{fmt(a["balance"])}</strong></div>'
    for a in accounts
) or '<div style="color:#94a3b8">계좌 데이터 없음</div>'

col_pp_net  = '#16a34a' if pp_net  >= 0 else '#ef4444'
col_f1_net  = '#16a34a' if f1_net  >= 0 else '#f59e0b'
col_f2_net  = '#16a34a' if f2_net  >= 0 else '#f59e0b'
sign_pp     = '+' if pp_net  >= 0 else ''
sign_f1     = '+' if f1_net  >= 0 else ''
sign_f2     = '+' if f2_net  >= 0 else ''
kpi_col     = '#16a34a' if f1_net >= 0 else '#ef4444'
kpi_label   = '흑자' if f1_net >= 0 else '적자'

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"/>
<title>그로우 자금일보 {today_str}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;color:#0f172a;padding:32px 40px}}
.card{{background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:20px 24px;box-shadow:0 1px 3px rgba(0,0,0,.05)}}
.grid{{display:grid;gap:14px}}
.g4{{grid-template-columns:repeat(4,1fr)}}
.g31{{grid-template-columns:2fr 1fr}}
.g2{{grid-template-columns:1fr 1fr}}
h1{{font-size:22px;font-weight:800}}
.lbl{{font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px}}
.val{{font-size:24px;font-weight:800;letter-spacing:-1px}}
.sub{{font-size:12px;color:#94a3b8;margin-top:4px}}
.stitle{{font-size:13px;font-weight:700;margin-bottom:12px}}
.badge{{padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;display:inline-flex;align-items:center;gap:4px;margin-right:6px}}
.actual{{background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0}}
.forecast{{background:#eff6ff;color:#2563eb;border:1px solid #bfdbfe}}
.h280{{height:280px;position:relative}}
.h180{{height:180px;position:relative}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
thead th{{padding:8px 10px;font-size:11px;font-weight:600;color:#94a3b8;text-align:left;border-bottom:1px solid #f1f5f9;text-transform:uppercase}}
tbody tr{{border-bottom:1px solid #f8fafc}}
tbody td{{padding:8px 10px}}
.in{{color:#2563eb;font-weight:600;text-align:right}}
.out{{color:#ef4444;font-weight:600;text-align:right}}
.ttl{{background:#f8fafc;font-weight:700}}
</style>
</head>
<body>

<div style="display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:24px">
  <div>
    <h1>그로우 자금일보</h1>
    <p style="font-size:13px;color:#64748b;margin-top:4px">업데이트: {today_str} | <a href="https://kyu921027.github.io/grouv-dashboard/" style="color:#2563eb">GitHub Pages</a></p>
  </div>
  <div style="text-align:right">
    <div style="font-size:11px;color:#94a3b8;margin-bottom:2px">현재 잔액</div>
    <div style="font-size:22px;font-weight:800;color:#2563eb">{fmt(total_balance)}</div>
  </div>
</div>

<div style="margin-bottom:16px">
  <span class="badge actual">{tag_pp} 실측</span>
  <span class="badge forecast">{tag_f1} 예측</span>
  <span class="badge forecast">{tag_f2} 예측</span>
</div>

<div class="grid g4" style="margin-bottom:14px">
  <div class="card"><div class="lbl">{tag_f1} 예측 매출</div><div class="val" style="color:#2563eb">{fmt(f1_tr)}</div><div class="sub">전월 기준 93%</div></div>
  <div class="card"><div class="lbl">{tag_f1} 예측 지출</div><div class="val" style="color:#ef4444">{fmt(f1_te)}</div><div class="sub">고정 {fmt(f1['fixed'])} / 변동 {fmt(f1['variable'])}</div></div>
  <div class="card"><div class="lbl">{tag_f1} 예측 순이익</div><div class="val" style="color:{kpi_col}">{sign_f1}{fmt(f1_net)}</div><div class="sub">{kpi_label} 예상</div></div>
  <div class="card"><div class="lbl">이달 현재 매출</div><div class="val" style="color:#0ea5e9">{fmt(this_tr)}</div><div class="sub">지출 {fmt(this_te)}</div></div>
</div>

<div class="grid g2" style="margin-bottom:14px">
  <div class="card">
    <div class="stitle">⚠️ 이번주 납부 예정 ({week_start.month}/{week_start.day} ~ {week_end.month}/{week_end.day})</div>
    <table><thead><tr><th>납부일</th><th>항목</th><th style="text-align:right">금액</th></tr></thead>
    <tbody>{week_pay_html}</tbody></table>
  </div>
  <div class="card">
    <div class="stitle">계좌 잔액</div>
    {acct_html}
    <div style="margin-top:8px;padding-top:8px;border-top:2px solid #e2e8f0;display:flex;justify-content:space-between">
      <strong>총계</strong><strong style="color:#2563eb">{fmt(total_balance)}</strong>
    </div>
  </div>
</div>

<div class="grid g31" style="margin-bottom:14px">
  <div class="card">
    <div class="stitle">매출 vs 지출 | {tag_pp} 실측 · {tag_f1}·{tag_f2} 예측</div>
    <div class="h280"><canvas id="mainChart"></canvas></div>
  </div>
  <div class="card">
    <div class="stitle">{tag_f1} 예측 지출 구성</div>
    <div class="h180"><canvas id="donutChart"></canvas></div>
    <div style="margin-top:12px;font-size:12px">
      <div style="display:flex;justify-content:space-between;margin-bottom:4px">
        <span>🟣 고정(인건비포함)</span><strong>{fmt(f1['fixed'])} ({f1['fixed']/f1_te*100:.0f}%)</strong>
      </div>
      <div style="display:flex;justify-content:space-between">
        <span>🟠 변동</span><strong>{fmt(f1['variable'])} ({f1['variable']/f1_te*100:.0f}%)</strong>
      </div>
    </div>
  </div>
</div>

<div class="card" style="margin-bottom:14px">
  <div class="stitle">손익 종합 | {tag_pp} 실측 기준</div>
  <table>
    <thead><tr><th>항목</th><th style="text-align:right">{tag_pp}(실측)</th><th style="text-align:right">{tag_f1}(예측)</th><th style="text-align:right">{tag_f2}(예측)</th></tr></thead>
    <tbody>
      <tr><td>매출</td><td class="in">{fmt(pp_tr)}</td><td class="in">{fmt(f1_tr)}</td><td class="in">{fmt(f2_tr)}</td></tr>
      <tr><td style="padding-left:16px;color:#64748b">고정(인건비포함)</td><td class="out">-{fmt(pp['fixed'])}</td><td class="out">-{fmt(f1['fixed'])}</td><td class="out">-{fmt(f2['fixed'])}</td></tr>
      <tr><td style="padding-left:16px;color:#64748b">변동</td><td class="out">-{fmt(pp['variable'])}</td><td class="out">-{fmt(f1['variable'])}</td><td class="out">-{fmt(f2['variable'])}</td></tr>
      <tr class="ttl"><td>지출 합계</td><td class="out">-{fmt(pp_te)}</td><td class="out">-{fmt(f1_te)}</td><td class="out">-{fmt(f2_te)}</td></tr>
      <tr style="border-top:2px solid #e2e8f0">
        <td style="font-weight:800">순이익</td>
        <td style="font-weight:800;text-align:right;color:{col_pp_net}">{sign_pp}{fmt(pp_net)}</td>
        <td style="font-weight:800;text-align:right;color:{col_f1_net}">{sign_f1}{fmt(f1_net)}</td>
        <td style="font-weight:800;text-align:right;color:{col_f2_net}">{sign_f2}{fmt(f2_net)}</td>
      </tr>
    </tbody>
  </table>
</div>

<div class="card">
  <div class="stitle">이달 고정지출 납부 일정 | 월 총 {total_fixed:,}원</div>
  <table>
    <thead><tr><th>납부일</th><th>항목</th><th style="text-align:right">금액</th></tr></thead>
    <tbody>{all_sched_html}</tbody>
  </table>
</div>

<script>
const labels = ['{tag_pp}(실측)', '{tag_f1}(예측)', '{tag_f2}(예측)'];
const isFc   = [false, true, true];
new Chart(document.getElementById('mainChart'), {{
  type: 'bar',
  data: {{
    labels,
    datasets: [
      {{label:'매출',         data:[{pp_tr},{f1_tr},{f2_tr}],                         backgroundColor:isFc.map(f=>f?'#3b82f688':'#3b82f6'), stack:'r', borderRadius:{{topLeft:4,topRight:4}}}},
      {{label:'고정(인건비포함)', data:[-{pp['fixed']},-{f1['fixed']},-{f2['fixed']}],    backgroundColor:isFc.map(f=>f?'#6366f188':'#6366f1'), stack:'e', borderRadius:{{topLeft:4,topRight:4}}}},
      {{label:'변동',         data:[-{pp['variable']},-{f1['variable']},-{f2['variable']}], backgroundColor:isFc.map(f=>f?'#f9731688':'#f97316'), stack:'e', borderRadius:{{bottomLeft:4,bottomRight:4}}}}
    ]
  }},
  options: {{
    responsive:true, maintainAspectRatio:false,
    plugins:{{
      legend:{{labels:{{color:'#64748b',font:{{size:11}},boxWidth:10}}}},
      tooltip:{{callbacks:{{label:c=>' '+c.dataset.label+': '+Math.abs(c.raw/10000).toFixed(0)+'만'}}}}
    }},
    scales:{{
      x:{{stacked:true,grid:{{display:false}},ticks:{{color:'#94a3b8'}},border:{{display:false}}}},
      y:{{stacked:true,grid:{{color:'#f1f5f9'}},border:{{display:false}},ticks:{{color:'#94a3b8',callback:v=>Math.abs(v/10000)+'만'}}}}
    }}
  }}
}});
new Chart(document.getElementById('donutChart'), {{
  type: 'doughnut',
  data: {{
    labels: ['고정(인건비포함)', '변동'],
    datasets: [{{data:[{f1['fixed']},{f1['variable']}], backgroundColor:['#6366f1','#f97316'], borderWidth:3, borderColor:'#fff'}}]
  }},
  options:{{responsive:true,maintainAspectRatio:false,cutout:'65%',plugins:{{legend:{{display:false}}}}}}
}});
</script>
</body>
</html>"""

with open(f'/tmp/dashboard_{today_str}.html', 'w', encoding='utf-8') as f:
    f.write(html)

# Slack용 요약 저장
week_pay_slack = '\n'.join(f'  - {d}일 | {n} | {a:,}원' for d,n,a in week_pay) or '  이번 주 납부 예정 없음'
acct_slack = '\n'.join(f'  - {a["name"]}: {fmt(a["balance"])}' for a in accounts) or '  계좌 데이터 없음'

summary = f"""today_str={today_str}
tag_pp={tag_pp}
tag_f1={tag_f1}
tag_f2={tag_f2}
f1_tr={fmt(f1_tr)}
f1_te={fmt(f1_te)}
f1_fixed={fmt(f1['fixed'])}
f1_variable={fmt(f1['variable'])}
f1_net={sign_f1}{fmt(f1_net)}
this_tr={fmt(this_tr)}
this_te={fmt(this_te)}
total_balance={fmt(total_balance)}
week_start={week_start.month}/{week_start.day}
week_end={week_end.month}/{week_end.day}
week_pay_slack={week_pay_slack}
acct_slack={acct_slack}
"""
with open('/tmp/summary.txt','w') as f:
    f.write(summary)

print(f'Done. f1_net={sign_f1}{fmt(f1_net)}, balance={fmt(total_balance)}')
