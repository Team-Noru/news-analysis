# Company Directory readme 파일

이 디렉토리는 한국 및 미국 상장기업 정보를 정규화하고,
뉴스 기사에서 기업명을 자동 추출하기 위한 데이터 파이프라인과 매칭 로직을 포함한다.

## 전체 흐름

DART 고유번호 → 회사 리스트 정제 → 한국기업 + 영어명 매핑 → 미국기업 병합 → 기업명 alias 생성 → 뉴스에서 기업명 매칭

## 파일 설명
### 1. ```trans.py```

상장법인목록.xls을 JSON으로 변환하는 스크립트.

- 스팩 워딩이 포함된 회사는 필터링 하여 제거

출력 파일 → ```listed_companies_korea.json```

### 2. ```listed_companies_korea.json```

한국 상장기업의 기본 정보가 담긴 JSON.

예시 데이터 : 
```
{
  "name": "아로마티카",
  "market_raw": "코스닥",
  "exchange": "KOSDAQ",
  "ticker": "0015N0",
  "industry": "...",
  "homepage": "...",
  "region": "경기도"
}
```

### 3. ```corp_name.py```

DART 고유번호 Zip 데이터를 다운 → CSV/JSON으로 변환하는 스크립트.

DART에서 제공하는 모든 기업의:

출력 파일 → ```dart_corp_code.json```, ```dart_corp_code.csv```

### 4. ```merge_ko_eng_name.py```

listed_companies_korea.json(한국 상장사) + dart_corp_code.json(영문명/고유번호)

➡ 두 데이터를 병합하여 실제 상장사에 대응되는 corp_code와 영문명 추출

출력 파일 → ```corp_merged.json``` / ```corp_unmatched.json```

### 5. ```corp_merged.json```

한국 상장사 + DART 공식 영문명 + 고유번호까지 매칭된 최종 DB

예시 데이터 :

```
{
  "name": "에임드바이오",
  "ticker": "0009K0",
  "corp_code": "01781999",
  "corp_eng_name": "Aimed Bio Inc.",
  "dart_stock_code": "0009K0"
}
```

### 6. ```sp_500_list.json```

미국 S&P500 기업 목록.

예시 데이터:
```
{
  "company": "Nvidia",
  "symbol": "NVDA",
  "company_kor": "엔비디아",
  "CIK": 1045810
}
```

### 7. ```company_match.py```

뉴스 기사에서 등장하는 기업명을 자동 추출하는 핵심 스크립트

- corp_merged.json + sp_500_list.json 로딩

- 각 기업의 alias 목록 생성 (예: “삼성전자”, “삼성”, “Samsung Electronics”, “Samsung”)

- 뉴스 문장을 스캔하여 기업명 등장 여부 탐지

- 결과 출력 (한국(KR) / 미국(US) 기업 모두 추출 가능.)

출력 예시 데이터:
```
=== FOUND COMPANIES ===
SK하이닉스 (KOSPI)
삼성전자 (KOSPI)
Nvidia (NASDAQ)
```


## 🎯 전체 파이프라인 요약

**1) 상장법인목록.xls**
        ↓  (trans.py)
**2) listed_companies_korea.json**
        ↓  (corp_name.py via DART API)
**3) dart_corp_code.json**
        ↓  (merge_ko_eng_name.py)
**4) corp_merged.json**   ← 한국 기업 영문명 + 고유번호 완성본
        ↓
**5) corp_merged.json** + sp_500_list.json
        ↓
**6) company_match.py**   ← 뉴스 기사에서 KR/US 기업명 추출
