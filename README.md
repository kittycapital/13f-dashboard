# 🏦 월가 슈퍼투자자 13F 대시보드

SEC EDGAR 무료 API를 활용한 세계 최고 헤지펀드 포트폴리오 추적 대시보드

## 추적 펀드 (13개)

### Group A: 2025 성과 우수 + 분석 가치 높은 펀드
| 펀드 | 매니저 | CIK |
|---|---|---|
| TCI Fund Management | Chris Hohn | 1446194 |
| Soroban Capital Partners | Eric Mandelblatt | 1535392 |
| Pershing Square Capital | Bill Ackman | 1336528 |
| Appaloosa Management | David Tepper | 1656456 |

### Group B: 레전드 투자자
| 펀드 | 매니저 | CIK |
|---|---|---|
| Berkshire Hathaway | Warren Buffett | 1067983 |
| Scion Asset Management | Michael Burry | 1649339 |
| Soros Fund Management | George Soros | 1029160 |
| Duquesne Family Office | Stanley Druckenmiller | 3297803 |
| ARK Investment Management | Cathie Wood | 1603466 |

### Group C: 2025 최고 퀀트/멀티전략
| 펀드 | 매니저 | CIK |
|---|---|---|
| Bridgewater Associates | Ray Dalio (founded) | 1350694 |
| D.E. Shaw & Co. | David Shaw | 1009207 |
| Renaissance Technologies | Jim Simons (founded) | 1037389 |
| Citadel Advisors | Ken Griffin | 1423053 |

## 기술 스택

```
Python (fetch_13f.py)  →  SEC EDGAR API (무료)
        ↓
GitHub Actions (매일 7AM KST)
        ↓
data/holdings.json
        ↓
index.html (단일 파일)  →  GitHub Pages  →  imweb 임베딩
```

## 로컬 실행

```bash
# 데이터 수집
python fetch_13f.py

# HTML 빌드 (데이터 주입)
python3 -c "
import json
with open('data/holdings.json') as f: data = json.load(f)
with open('index_template.html') as f: html = f.read()
html = html.replace('HOLDINGS_DATA_PLACEHOLDER', json.dumps(data, ensure_ascii=False))
with open('index.html', 'w') as f: f.write(html)
"
```

## 데이터 소스

- **SEC EDGAR**: https://data.sec.gov/submissions/
- API 키 불필요, 완전 무료
- User-Agent 헤더 필수 (SEC 정책)
- Rate limit: 10 req/sec

## 참고

- 13F는 분기별 공시 (45일 시차)
- 숏 포지션 미포함
- 2025 수익률은 Bloomberg/Reuters 보도 기반
