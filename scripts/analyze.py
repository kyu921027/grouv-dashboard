import json, sys
from datetime import date, timedelta, datetime

parts = open('/tmp/dates.txt').read().strip().split('|')
today_str, week_start_s, week_end_s = parts[0], parts[1], parts[2]

today      = date.today()
week_start = datetime.strptime(week_start_s, '%Y-%m-%d').date()
week_end   = datetime.strptime(week_end_s,   '%Y-%m-%d').date()

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
    r = {'fixed':0,'variable':0,'variable_cats':{},
         'revenue':{'상품매출':0,'서비스매출':0,'온라인 매출':0,'기타':0}}
    for t in tickets:
        cat = (t.get('expenseCategory') or {}).get('name','미분류')
        if '단순이체' in cat: continue
        amt = t.get('amount', 0)
        tx  = t.get('transactionType', '')
        if tx == 'OUT':
            if classify(cat) == 'fixed':
                r['fixed'] += amt
            else:
                r['variable'] += amt
                r['variable_cats'][cat] = r['variable_cats'].get(cat, 0) + amt
        elif tx == 'IN':
            key = cat if cat in ('상품매출','서비스매출','온라인 매출') else '기타'
            r['revenue'][key] += amt
    return r

def slim_tickets(path):
    result = []
    for t in load_tickets(path):
        cat = (t.get('expenseCategory') or {}).get('name', '미분류')
        if '단순이체' in cat: continue
        result.append({
            'd': t.get('transactAt', t.get('date',''))[:10],
            'a': t.get('amount', 0),
            'tx': t.get('transactionType',''),
            'cat': cat,
            'memo': t.get('content', t.get('description',''))[:40]
        })
    return result

prev_raw   = load_tickets('/tmp/prev_tickets.json')
pp_raw     = load_tickets('/tmp/pp_tickets.json')
this_raw   = load_tickets('/tmp/this_tickets.json')

prev   = analyze(prev_raw)
pp     = analyze(pp_raw)
this_m = analyze(this_raw)

prev_slim_js = json.dumps(slim_tickets('/tmp/prev_tickets.json'), ensure_ascii=False)
this_slim_js = json.dumps(slim_tickets('/tmp/this_tickets.json'), ensure_ascii=False)

def bank_from_name(name):
    if '우리' in name or 'CUBE' in name.upper(): return '우리은행'
    if 'KB' in name.upper() or '국민' in name:  return 'KB국민은행'
    if '신한' in name: return '신한은행'
    if '하나' in name: return '하나은행'
    if '기업' in name: return 'IBK기업은행'
    return '-'

try:
    raw   = json.load(open('/tmp/assets.json'))
    items = raw if isinstance(raw, list) else raw.get('data', raw.get('items', []))
    accounts, total_balance = [], 0
    for a in items:
        ba = a.get('bankAccount') or a
        if ba.get('accountType','') == 'LOAN': continue
        if ba.get('isLoan', False): continue
        bal  = ba.get('accountBalance', 0)
        name = ba.get('accountName', ba.get('name','계좌'))
        accounts.append({'bank': bank_from_name(name), 'name': name, 'balance': bal})
        total_balance += bal
except:
    total_balance, accounts = 0, []

tag_f1 = today.strftime('%m월')
next_m = (date(today.year, today.month, 1) + timedelta(days=32))
tag_f2 = next_m.strftime('%m월')

def fmt(v): return f'{int(v)//10000:,}만'

f1 = {'revenue': {k: int(v*0.93) for k,v in prev['revenue'].items()},
      'fixed': prev['fixed'], 'variable': prev['variable']}
f2 = {'revenue': {k: int(v*0.88) for k,v in prev['revenue'].items()},
      'fixed': prev['fixed'], 'variable': prev['variable']}

f1_tr = sum(f1['revenue'].values()); f1_te = f1['fixed']+f1['variable']; f1_net = f1_tr-f1_te
f2_tr = sum(f2['revenue'].values()); f2_te = f2['fixed']+f2['variable']; f2_net = f2_tr-f2_te
this_tr = sum(this_m['revenue'].values()); this_te = this_m['fixed']+this_m['variable']
this_net = this_tr - this_te

sign_f1 = '+' if f1_net>=0 else ''; col_f1 = '#16a34a' if f1_net>=0 else '#ef4444'
sign_f2 = '+' if f2_net>=0 else ''; col_f2 = '#16a34a' if f2_net>=0 else '#ef4444'
sign_th = '+' if this_net>=0 else ''; col_th = '#16a34a' if this_net>=0 else '#ef4444'

FIXED_SCHEDULE = [
    (6,  '기장료 (세무법인다성)',    220000),
    (11, '사대보험료',             2500360),
    (11, 'SW구독 (웹케시)',           27500),
    (15, '차량임대료 (아이엠캐피탈)', 620950),
    (15, '차량임대료 (엠지캐피탈)',   739158),
    (21, '건물관리비',               338670),
    (21, '사무실 임대료',          1650000),
    (26, '이자비용',               1853547),
    (26, '통신비',                    36960),
]
total_fixed_sched = sum(a for _,_,a in FIXED_SCHEDULE)

week_pay = [(d,n,a) for d,n,a in FIXED_SCHEDULE if week_start.day <= d <= week_end.day]
week_pay_html = ''.join(
    f'<tr><td>{d}일</td><td>{n}</td>'
    f'<td style="text-align:right;color:#ef4444;font-weight:700">{a:,}원</td></tr>'
    for d,n,a in week_pay
) or '<tr><td colspan="3" style="text-align:center;color:#94a3b8">이번 주 납부 예정 없음</td></tr>'

all_sched_html = ''.join(
    f'<tr><td>{d}일</td><td>{n}</td>'
    f'<td style="text-align:right;color:#ef4444">{a:,}원</td></tr>'
    for d,n,a in FIXED_SCHEDULE
)

acct_html = ''.join(
    f'<tr><td style="color:#64748b">{a["bank"]}</td>'
    f'<td>{a["name"]}</td>'
    f'<td style="text-align:right;font-weight:700;color:#0f172a">{fmt(a["balance"])}</td></tr>'
    for a in accounts
) or '<tr><td colspan="3" style="text-align:center;color:#94a3b8">계좌 데이터 없음</td></tr>'

# Variable cats for JS popup
prev_var_cats = sorted(prev['variable_cats'].items(), key=lambda x:-x[1])[:8]
scale1 = f1['variable']/prev['variable'] if prev['variable'] else 1
scale2 = f2['variable']/prev['variable'] if prev['variable'] else 1

def var_cats_js(cats, scale):
    items = [(k, int(v*scale)) for k,v in cats]
    escaped = [(k.replace('"','\''), v) for k,v in items]
    return '[' + ','.join(f'{{"n":"{k}","v":{v}}}' for k,v in escaped) + ']'

f1_var_js = var_cats_js(prev_var_cats, scale1)
f2_var_js = var_cats_js(prev_var_cats, scale2)

fixed_js = '[' + ','.join(
    f'{{"day":{d},"n":"{n.replace(chr(34), chr(39))}","v":{a}}}' for d,n,a in FIXED_SCHEDULE
) + ']'

# Revenue detail rows helper
def rev_rows(rev):
    rows = ''
    for k,v in rev.items():
        if v > 0:
            rows += (f'<div style="display:flex;justify-content:space-between;padding:5px 0;'
                     f'border-bottom:1px solid #f1f5f9">'
                     f'<span style="color:#475569;font-size:12px">{k}</span>'
                     f'<span style="font-size:12px;font-weight:700;color:#2563eb">{fmt(v)}</span></div>')
    return rows or '<div style="color:#94a3b8;font-size:12px">데이터 없음</div>'

f1_rev_rows = rev_rows(f1['revenue'])
f2_rev_rows = rev_rows(f2['revenue'])

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
.h280{{height:280px;position:relative}}
.h180{{height:180px;position:relative}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
thead th{{padding:8px 10px;font-size:11px;font-weight:600;color:#94a3b8;text-align:left;border-bottom:1px solid #f1f5f9;text-transform:uppercase}}
tbody tr{{border-bottom:1px solid #f8fafc}}
tbody td{{padding:8px 10px}}
.in{{color:#2563eb;font-weight:600;text-align:right}}
.out{{color:#ef4444;font-weight:600;text-align:right}}
.ttl{{background:#f8fafc;font-weight:700}}

/* 검색 바 */
.search-wrap{{margin-bottom:14px}}
.search-bar{{display:flex;align-items:center;gap:10px;background:#fff;border:1.5px solid #e2e8f0;
             border-radius:16px;padding:10px 16px;box-shadow:0 1px 3px rgba(0,0,0,.05);transition:.15s}}
.search-bar:focus-within{{border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,.1)}}
.search-bar input{{flex:1;border:none;outline:none;font-size:14px;color:#0f172a;background:transparent}}
.search-bar input::placeholder{{color:#94a3b8}}
.search-btn{{padding:7px 18px;background:#0f172a;color:#fff;border:none;border-radius:10px;
             font-size:13px;font-weight:600;cursor:pointer;white-space:nowrap;transition:.15s}}
.search-btn:hover{{background:#1e293b}}
.search-result{{background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:20px 24px;
                margin-top:10px;box-shadow:0 1px 3px rgba(0,0,0,.05)}}
.result-title{{font-size:13px;font-weight:700;margin-bottom:12px;display:flex;
               justify-content:space-between;align-items:center}}
.result-total{{font-size:12px;font-weight:600;padding:3px 10px;border-radius:8px;background:#f1f5f9}}
.tag-hint{{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600;
           background:#eff6ff;color:#2563eb;margin-left:6px;cursor:pointer}}

/* 탭 버튼 */
.tab-bar{{display:flex;gap:8px;margin-bottom:16px}}
.tab-btn{{padding:8px 20px;border-radius:24px;border:1.5px solid #e2e8f0;background:#fff;
          font-size:13px;font-weight:700;color:#64748b;cursor:pointer;transition:.15s}}
.tab-btn.active{{background:#2563eb;color:#fff;border-color:#2563eb}}

/* KPI 클릭 */
.kpi-card{{cursor:pointer;transition:box-shadow .15s;position:relative}}
.kpi-card:hover{{box-shadow:0 4px 12px rgba(37,99,235,.12)}}
.kpi-hint{{font-size:10px;color:#cbd5e1;margin-top:6px}}

/* 미니 배너 (KPI 카드 내 드롭다운) */
.mini-banner{{margin-top:12px;padding:10px 12px;background:#f8fafc;
              border-radius:10px;border:1px solid #e2e8f0}}

/* 팝업 오버레이 */
.popup-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:100;
                align-items:center;justify-content:center}}
.popup-overlay.show{{display:flex}}
.popup-box{{background:#fff;border-radius:20px;padding:24px;min-width:320px;max-width:480px;
            width:90%;box-shadow:0 20px 60px rgba(0,0,0,.2);max-height:80vh;overflow-y:auto}}
.popup-title{{font-size:15px;font-weight:800;margin-bottom:14px;display:flex;
              justify-content:space-between;align-items:center}}
.popup-close{{background:none;border:none;font-size:18px;cursor:pointer;color:#94a3b8;
              padding:0 4px;line-height:1}}
.popup-row{{display:flex;justify-content:space-between;align-items:center;
            padding:7px 0;border-bottom:1px solid #f1f5f9;font-size:13px}}
.popup-row:last-child{{border-bottom:none}}
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

<!-- 검색 바 -->
<div class="search-wrap">
  <div class="search-bar">
    <span style="font-size:16px;color:#94a3b8">🔍</span>
    <input type="text" id="search-input"
      placeholder="예) 상품매출 상세내역 보여줘 / 고정지출 월 상세내역 / 이달 변동지출"
      onkeydown="if(event.key==='Enter') doSearch()" />
    <button class="search-btn" onclick="doSearch()">검색</button>
  </div>
  <div class="search-result" id="search-result" style="display:none">
    <div class="result-title">
      <span id="result-label">검색 결과</span>
      <span class="result-total" id="result-total"></span>
    </div>
    <div id="result-body"></div>
  </div>
</div>

<!-- 탭 -->
<div class="tab-bar">
  <button class="tab-btn active" id="tab-f1" onclick="switchTab('f1')">{tag_f1}</button>
  <button class="tab-btn" id="tab-f2" onclick="switchTab('f2')">{tag_f2}</button>
</div>

<!-- KPI — f1 -->
<div id="kpi-f1" class="grid g4" style="margin-bottom:14px">
  <div class="card kpi-card" onclick="toggleBanner('f1-rev')">
    <div class="lbl">{tag_f1} 예상 매출</div>
    <div class="val" style="color:#2563eb">{fmt(f1_tr)}</div>
    <div class="sub">전월 기준 93%</div>
    <div class="kpi-hint">▼ 클릭하여 상세 보기</div>
    <div class="mini-banner" id="f1-rev-banner">
      {f1_rev_rows}
    </div>
  </div>
  <div class="card kpi-card" onclick="toggleBanner('f1-exp')">
    <div class="lbl">{tag_f1} 예상 지출</div>
    <div class="val" style="color:#ef4444">{fmt(f1_te)}</div>
    <div class="sub">고정 {fmt(f1['fixed'])} / 변동 {fmt(f1['variable'])}</div>
    <div class="kpi-hint">▼ 클릭하여 상세 보기</div>
    <div class="mini-banner" id="f1-exp-banner">
      <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #f1f5f9">
        <span style="color:#6366f1;font-size:12px">🟣 고정(인건비포함)</span>
        <span style="font-size:12px;font-weight:700">{fmt(f1['fixed'])}</span>
      </div>
      <div style="display:flex;justify-content:space-between;padding:5px 0">
        <span style="color:#f97316;font-size:12px">🟠 변동</span>
        <span style="font-size:12px;font-weight:700">{fmt(f1['variable'])}</span>
      </div>
    </div>
  </div>
  <div class="card">
    <div class="lbl">{tag_f1} 예상 순이익</div>
    <div class="val" style="color:{col_f1}">{sign_f1}{fmt(f1_net)}</div>
    <div class="sub">{'흑자' if f1_net>=0 else '적자'} 예상</div>
  </div>
  <div class="card">
    <div class="lbl">이달 현재 매출</div>
    <div class="val" style="color:#0ea5e9">{fmt(this_tr)}</div>
    <div class="sub">지출 {fmt(this_te)}</div>
  </div>
</div>

<!-- KPI — f2 -->
<div id="kpi-f2" class="grid g4" style="margin-bottom:14px;display:none">
  <div class="card kpi-card" onclick="toggleBanner('f2-rev')">
    <div class="lbl">{tag_f2} 예상 매출</div>
    <div class="val" style="color:#2563eb">{fmt(f2_tr)}</div>
    <div class="sub">전월 기준 88%</div>
    <div class="kpi-hint">▼ 클릭하여 상세 보기</div>
    <div class="mini-banner" id="f2-rev-banner">
      {f2_rev_rows}
    </div>
  </div>
  <div class="card kpi-card" onclick="toggleBanner('f2-exp')">
    <div class="lbl">{tag_f2} 예상 지출</div>
    <div class="val" style="color:#ef4444">{fmt(f2_te)}</div>
    <div class="sub">고정 {fmt(f2['fixed'])} / 변동 {fmt(f2['variable'])}</div>
    <div class="kpi-hint">▼ 클릭하여 상세 보기</div>
    <div class="mini-banner" id="f2-exp-banner">
      <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #f1f5f9">
        <span style="color:#6366f1;font-size:12px">🟣 고정(인건비포함)</span>
        <span style="font-size:12px;font-weight:700">{fmt(f2['fixed'])}</span>
      </div>
      <div style="display:flex;justify-content:space-between;padding:5px 0">
        <span style="color:#f97316;font-size:12px">🟠 변동</span>
        <span style="font-size:12px;font-weight:700">{fmt(f2['variable'])}</span>
      </div>
    </div>
  </div>
  <div class="card">
    <div class="lbl">{tag_f2} 예상 순이익</div>
    <div class="val" style="color:{col_f2}">{sign_f2}{fmt(f2_net)}</div>
    <div class="sub">{'흑자' if f2_net>=0 else '적자'} 예상</div>
  </div>
  <div class="card">
    <div class="lbl">이달 현재 매출</div>
    <div class="val" style="color:#0ea5e9">{fmt(this_tr)}</div>
    <div class="sub">지출 {fmt(this_te)}</div>
  </div>
</div>

<!-- 이번주 납부 + 계좌 잔액 -->
<div class="grid g2" style="margin-bottom:14px">
  <div class="card">
    <div class="stitle">⚠️ 이번주 납부 예정 ({week_start.month}/{week_start.day} ~ {week_end.month}/{week_end.day})</div>
    <table><thead><tr><th>납부일</th><th>항목</th><th style="text-align:right">금액</th></tr></thead>
    <tbody>{week_pay_html}</tbody></table>
  </div>
  <div class="card">
    <div class="stitle">계좌 잔액</div>
    <table>
      <thead><tr><th>은행</th><th>계좌명</th><th style="text-align:right">잔액</th></tr></thead>
      <tbody>{acct_html}</tbody>
    </table>
    <div style="margin-top:8px;padding-top:8px;border-top:2px solid #e2e8f0;display:flex;justify-content:space-between">
      <strong>총계</strong><strong style="color:#2563eb">{fmt(total_balance)}</strong>
    </div>
  </div>
</div>

<!-- 차트 + 지출 구성 -->
<div class="grid g31" style="margin-bottom:14px">
  <div class="card">
    <div class="stitle">매출 vs 지출 | 이달 현재 · {tag_f1}·{tag_f2} 예상</div>
    <div class="h280"><canvas id="mainChart"></canvas></div>
  </div>
  <div class="card" style="position:relative">
    <div class="stitle" id="donut-title">{tag_f1} 예상 지출 구성</div>
    <div class="h180"><canvas id="donutChart"></canvas></div>
    <div style="margin-top:12px;font-size:12px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;
                  padding:6px 10px;border-radius:8px;cursor:pointer;transition:.15s"
           onmouseover="this.style.background='#f0f4ff'" onmouseout="this.style.background=''"
           onclick="openPopup('fixed')">
        <span>🟣 고정(인건비포함)</span>
        <strong id="lbl-fixed">{fmt(f1['fixed'])} ({(f1['fixed']/f1_te*100) if f1_te else 0:.0f}%)</strong>
        <span style="color:#94a3b8;font-size:10px">▶</span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;
                  padding:6px 10px;border-radius:8px;cursor:pointer;transition:.15s"
           onmouseover="this.style.background='#fff7f0'" onmouseout="this.style.background=''"
           onclick="openPopup('variable')">
        <span>🟠 변동</span>
        <strong id="lbl-var">{fmt(f1['variable'])} ({(f1['variable']/f1_te*100) if f1_te else 0:.0f}%)</strong>
        <span style="color:#94a3b8;font-size:10px">▶</span>
      </div>
    </div>
  </div>
</div>

<!-- 손익 종합 (3개월) -->
<div class="card" style="margin-bottom:14px">
  <div class="stitle">손익 종합 | 이달 현재 · {tag_f1} · {tag_f2}</div>
  <table>
    <thead><tr>
      <th>항목</th>
      <th style="text-align:right">이달 현재</th>
      <th style="text-align:right">{tag_f1}(예상)</th>
      <th style="text-align:right">{tag_f2}(예상)</th>
    </tr></thead>
    <tbody>
      <tr><td>매출</td>
        <td class="in">{fmt(this_tr)}</td>
        <td class="in">{fmt(f1_tr)}</td>
        <td class="in">{fmt(f2_tr)}</td>
      </tr>
      <tr><td style="padding-left:16px;color:#64748b">고정(인건비포함)</td>
        <td class="out">-{fmt(this_m['fixed'])}</td>
        <td class="out">-{fmt(f1['fixed'])}</td>
        <td class="out">-{fmt(f2['fixed'])}</td>
      </tr>
      <tr><td style="padding-left:16px;color:#64748b">변동</td>
        <td class="out">-{fmt(this_m['variable'])}</td>
        <td class="out">-{fmt(f1['variable'])}</td>
        <td class="out">-{fmt(f2['variable'])}</td>
      </tr>
      <tr class="ttl"><td>지출 합계</td>
        <td class="out">-{fmt(this_te)}</td>
        <td class="out">-{fmt(f1_te)}</td>
        <td class="out">-{fmt(f2_te)}</td>
      </tr>
      <tr style="border-top:2px solid #e2e8f0">
        <td style="font-weight:800">순이익</td>
        <td style="font-weight:800;text-align:right;color:{col_th}">{sign_th}{fmt(this_net)}</td>
        <td style="font-weight:800;text-align:right;color:{col_f1}">{sign_f1}{fmt(f1_net)}</td>
        <td style="font-weight:800;text-align:right;color:{col_f2}">{sign_f2}{fmt(f2_net)}</td>
      </tr>
    </tbody>
  </table>
</div>

<!-- 납부 일정 -->
<div class="card">
  <div class="stitle">이달 고정지출 납부 일정 | 월 총 {total_fixed_sched:,}원</div>
  <table>
    <thead><tr><th>납부일</th><th>항목</th><th style="text-align:right">금액</th></tr></thead>
    <tbody>{all_sched_html}</tbody>
  </table>
</div>

<!-- 팝업: 고정 지출 상세 -->
<div class="popup-overlay" id="popup-fixed" onclick="closePopup('fixed')">
  <div class="popup-box" onclick="event.stopPropagation()">
    <div class="popup-title">
      <span>🟣 고정 지출 상세 <span id="popup-fixed-tag" style="color:#64748b;font-weight:400;font-size:13px"></span></span>
      <button class="popup-close" onclick="closePopup('fixed')">✕</button>
    </div>
    <div id="popup-fixed-body"></div>
  </div>
</div>

<!-- 팝업: 변동 지출 상세 -->
<div class="popup-overlay" id="popup-variable" onclick="closePopup('variable')">
  <div class="popup-box" onclick="event.stopPropagation()">
    <div class="popup-title">
      <span>🟠 변동 지출 상세 <span id="popup-var-tag" style="color:#64748b;font-weight:400;font-size:13px"></span></span>
      <button class="popup-close" onclick="closePopup('variable')">✕</button>
    </div>
    <div id="popup-var-body"></div>
  </div>
</div>

<script>
const DATA = {{
  f1: {{
    fixed: {f1['fixed']}, variable: {f1['variable']},
    fixedPct: {(f1['fixed']/f1_te*100) if f1_te else 0:.0f},
    varPct:   {(f1['variable']/f1_te*100) if f1_te else 0:.0f},
    varCats: {f1_var_js},
    tag: '{tag_f1}'
  }},
  f2: {{
    fixed: {f2['fixed']}, variable: {f2['variable']},
    fixedPct: {(f2['fixed']/f2_te*100) if f2_te else 0:.0f},
    varPct:   {(f2['variable']/f2_te*100) if f2_te else 0:.0f},
    varCats: {f2_var_js},
    tag: '{tag_f2}'
  }}
}};
const FIXED_ITEMS = {fixed_js};
let currentTab = 'f1';

// 검색용 거래 데이터
const PREV_DATA = {prev_slim_js};
const THIS_DATA = {this_slim_js};
const FIXED_CAT_SET = new Set({json.dumps(list(FIXED_CATS), ensure_ascii=False)});

function fmt(v) {{
  return Math.round(v/10000).toLocaleString() + '만';
}}

function fmtAmt(v) {{
  return v.toLocaleString() + '원';
}}

// 검색 실행
function doSearch() {{
  const q = document.getElementById('search-input').value.trim();
  if (!q) return;

  // 데이터 소스 결정 — 월 키워드 없으면 현재 탭 기준
  let data, srcLabel;
  if (q.includes('전월') || q.includes('5월') || q.includes('지난달')) {{
    data = PREV_DATA; srcLabel = '전월(5월) ';
  }} else if (q.includes('이달') || q.includes('6월') || q.includes('이번달')) {{
    data = THIS_DATA; srcLabel = '이달(6월) ';
  }} else if (currentTab === 'f1') {{
    data = THIS_DATA; srcLabel = '6월 ';
  }} else {{
    // f2(7월)는 실데이터 없음 — 전월(5월) 기준 표시
    data = PREV_DATA; srcLabel = '7월 예상 근거(전월 5월) ';
  }}

  // 필터 결정
  let filtered = data;
  let label = srcLabel;

  // 매출 카테고리
  const revCats = ['상품매출','서비스매출','온라인 매출'];
  const matchedRevCat = revCats.find(c => q.includes(c));
  if (matchedRevCat) {{
    filtered = data.filter(t => t.tx === 'IN' && t.cat === matchedRevCat);
    label += matchedRevCat + ' 상세내역';
  }} else if (q.includes('매출')) {{
    filtered = data.filter(t => t.tx === 'IN');
    label += '매출 전체 내역';
  // 지출 카테고리
  }} else if ((q.includes('고정') || q.includes('Fixed')) && (q.includes('지출') || q.includes('비용'))) {{
    filtered = data.filter(t => t.tx === 'OUT' && FIXED_CAT_SET.has(t.cat));
    label += '고정지출 상세내역';
  }} else if ((q.includes('변동') || q.includes('variable')) && (q.includes('지출') || q.includes('비용'))) {{
    filtered = data.filter(t => t.tx === 'OUT' && !FIXED_CAT_SET.has(t.cat));
    label += '변동지출 상세내역';
  }} else if (q.includes('지출') || q.includes('비용')) {{
    filtered = data.filter(t => t.tx === 'OUT');
    label += '지출 전체 내역';
  }} else {{
    // 카테고리명 포함 여부로 검색
    const allCats = [...new Set(data.map(t => t.cat))];
    const matchedCat = allCats.find(c => q.includes(c) || c.includes(q.replace(/\\s*(보여줘|상세|내역|조회).*/,'').trim()));
    if (matchedCat) {{
      filtered = data.filter(t => t.cat === matchedCat);
      label += matchedCat + ' 내역';
    }} else {{
      // 메모/거래처 검색
      const kw = q.replace(/\\s*(보여줘|상세|내역|조회|알려줘).*/,'').trim();
      filtered = data.filter(t => t.cat.includes(kw) || t.memo.includes(kw));
      label += '"' + kw + '" 검색 결과';
    }}
  }}

  renderResults(label, filtered);
}}

function renderResults(label, rows) {{
  const panel = document.getElementById('search-result');
  panel.style.display = 'block';
  document.getElementById('result-label').textContent = label || '검색 결과';

  // 합계 계산
  const totalIn  = rows.filter(r=>r.tx==='IN').reduce((s,r)=>s+r.a, 0);
  const totalOut = rows.filter(r=>r.tx==='OUT').reduce((s,r)=>s+r.a, 0);
  const net = totalIn - totalOut;
  const totalEl = document.getElementById('result-total');
  if (totalIn > 0 && totalOut > 0) {{
    totalEl.textContent = '합계: 수입 ' + fmt(totalIn) + ' / 지출 ' + fmt(totalOut);
  }} else if (totalIn > 0) {{
    totalEl.textContent = '합계: ' + fmt(totalIn);
    totalEl.style.color = '#2563eb';
  }} else {{
    totalEl.textContent = '합계: ' + fmt(totalOut);
    totalEl.style.color = '#ef4444';
  }}

  if (rows.length === 0) {{
    document.getElementById('result-body').innerHTML =
      '<div style="text-align:center;color:#94a3b8;padding:20px">해당하는 내역이 없습니다.</div>';
    return;
  }}

  // 테이블 렌더
  let html = '<table><thead><tr><th>날짜</th><th>카테고리</th><th>거래처/내용</th>'
           + '<th style="text-align:right">금액</th></tr></thead><tbody>';
  const sorted = [...rows].sort((a,b) => b.d.localeCompare(a.d));
  for (const r of sorted) {{
    const isIn = r.tx === 'IN';
    const amtStyle = isIn ? 'color:#2563eb;font-weight:600;text-align:right'
                           : 'color:#ef4444;font-weight:600;text-align:right';
    const prefix = isIn ? '+' : '-';
    html += '<tr>'
          + '<td style="color:#64748b;white-space:nowrap">' + r.d + '</td>'
          + '<td><span style="background:#f1f5f9;padding:2px 8px;border-radius:6px;font-size:11px">' + r.cat + '</span></td>'
          + '<td style="color:#475569;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + (r.memo||'-') + '</td>'
          + '<td style="' + amtStyle + '">' + prefix + fmtAmt(r.a) + '</td>'
          + '</tr>';
  }}
  html += '</tbody></table>';
  document.getElementById('result-body').innerHTML = html;
}}

// 탭 전환
function switchTab(tab) {{
  currentTab = tab;
  ['f1','f2'].forEach(t => {{
    document.getElementById('kpi-'+t).style.display = t===tab ? 'grid' : 'none';
    document.getElementById('tab-'+t).classList.toggle('active', t===tab);
  }});
  const d = DATA[tab];
  document.getElementById('donut-title').textContent = d.tag + ' 예상 지출 구성';
  document.getElementById('lbl-fixed').textContent = fmt(d.fixed) + ' (' + d.fixedPct + '%)';
  document.getElementById('lbl-var').textContent   = fmt(d.variable) + ' (' + d.varPct + '%)';
  donutChart.data.datasets[0].data = [d.fixed, d.variable];
  donutChart.update();
}}

// 미니 배너 토글 (KPI 카드 클릭)
function toggleBanner(id) {{
  const el = document.getElementById(id + '-banner');
  if (!el) return;
  el.style.display = el.style.display === 'none' ? 'block' : 'none';
}}

// 팝업 열기/닫기
function openPopup(type) {{
  const d = DATA[currentTab];
  if (type === 'fixed') {{
    document.getElementById('popup-fixed-tag').textContent = '(' + d.tag + ' 예상)';
    let html = FIXED_ITEMS.map(item =>
      '<div class="popup-row">' +
        '<span style="color:#64748b">' + item.day + '일</span>' +
        '<span style="flex:1;margin:0 12px">' + item.n + '</span>' +
        '<strong style="color:#ef4444">' + item.v.toLocaleString() + '원</strong>' +
      '</div>'
    ).join('');
    const total = FIXED_ITEMS.reduce((s,i)=>s+i.v,0);
    html += '<div class="popup-row" style="border-top:2px solid #e2e8f0;margin-top:4px;font-weight:800">' +
              '<span>합계</span><strong style="color:#ef4444">' + total.toLocaleString() + '원</strong></div>';
    document.getElementById('popup-fixed-body').innerHTML = html;
    document.getElementById('popup-fixed').classList.add('show');
  }} else {{
    document.getElementById('popup-var-tag').textContent = '(' + d.tag + ' 예상)';
    let html = d.varCats.map(item =>
      '<div class="popup-row">' +
        '<span style="flex:1;color:#475569">' + item.n + '</span>' +
        '<strong style="color:#f97316">' + fmt(item.v) + '</strong>' +
      '</div>'
    ).join('');
    html += '<div style="font-size:11px;color:#94a3b8;margin-top:8px;padding-top:8px;border-top:1px solid #f1f5f9">전월 실적 기준 예상치</div>';
    document.getElementById('popup-var-body').innerHTML = html;
    document.getElementById('popup-variable').classList.add('show');
  }}
}}

function closePopup(type) {{
  document.getElementById('popup-' + type).classList.remove('show');
}}

document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') {{ closePopup('fixed'); closePopup('variable'); }}
}});

// 차트 (이달 현재 + 6월 예상 + 7월 예상)
new Chart(document.getElementById('mainChart'), {{
  type: 'bar',
  data: {{
    labels: ['이달 현재', '{tag_f1} 예상', '{tag_f2} 예상'],
    datasets: [
      {{label:'매출', data:[{this_tr},{f1_tr},{f2_tr}],
        backgroundColor:['#93c5fd','#3b82f6','#3b82f688'], stack:'r',
        borderRadius:{{topLeft:4,topRight:4}}}},
      {{label:'고정(인건비포함)', data:[-{this_m['fixed']},-{f1['fixed']},-{f2['fixed']}],
        backgroundColor:['#a5b4fc','#6366f1','#6366f188'], stack:'e',
        borderRadius:{{topLeft:4,topRight:4}}}},
      {{label:'변동', data:[-{this_m['variable']},-{f1['variable']},-{f2['variable']}],
        backgroundColor:['#fca5a5','#f97316','#f9731688'], stack:'e',
        borderRadius:{{bottomLeft:4,bottomRight:4}}}}
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
      y:{{stacked:true,grid:{{color:'#f1f5f9'}},border:{{display:false}},
          ticks:{{color:'#94a3b8',callback:v=>Math.abs(v/10000)+'만'}}}}
    }}
  }}
}});

const donutChart = new Chart(document.getElementById('donutChart'), {{
  type: 'doughnut',
  data: {{
    labels: ['고정(인건비포함)','변동'],
    datasets: [{{data:[{f1['fixed']},{f1['variable']}],
      backgroundColor:['#6366f1','#f97316'], borderWidth:3, borderColor:'#fff'}}]
  }},
  options:{{responsive:true,maintainAspectRatio:false,cutout:'65%',
    plugins:{{legend:{{display:false}}}}}}
}});
</script>
</body>
</html>"""

with open(f'/tmp/dashboard_{today_str}.html', 'w', encoding='utf-8') as f:
    f.write(html)

# Slack 요약
week_pay_slack = '\n'.join(f'  - {d}일 | {n} | {a:,}원' for d,n,a in week_pay) or '  이번 주 납부 예정 없음'
acct_slack = '\n'.join(f'  - {a["bank"]} {a["name"]}: {fmt(a["balance"])}' for a in accounts) or '  계좌 데이터 없음'

summary = f"""today_str={today_str}
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
