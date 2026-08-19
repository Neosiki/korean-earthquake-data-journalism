#!/usr/bin/env python3
"""Update the site dataset from the KMA earthquake API and regenerate site assets.

The script is dependency-free so it can run in GitHub Actions. It refreshes a
rolling 30-day window to accommodate later corrections and de-duplicates records.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / 'data' / 'kma_earthquakes_2005_2026_extracted.csv'
DOCS = ROOT / 'docs'
MEDIA = DOCS / 'media'
SITE_DATA = DOCS / 'site-data.json'
OVERVIEW_SVG = MEDIA / 'latest_overview.svg'
YEARLY_SVG = MEDIA / 'latest_yearly_trend.svg'
API_URL = 'https://apihub.kma.go.kr/api/typ01/url/eqk_list.php'
FIELDS = ['발생일시', '규모', '깊이km', '최대진도', '위도', '경도', '위치']
KST = timezone(timedelta(hours=9))


def parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.search(r'-?\d+(?:\.\d+)?', str(value))
    return float(match.group()) if match else None


def parse_datetime(value: str) -> datetime | None:
    text = str(value).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y%m%d%H%M%S', '%Y%m%d%H%M'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def format_coordinate(value: float | None, positive: str) -> str:
    if value is None:
        return ''
    return f'{value:.3f} {positive}'


def record_key(record: dict[str, str]) -> str:
    normalized = '|'.join([
        record.get('발생일시', '').strip(),
        record.get('규모', '').strip(),
        f"{parse_number(record.get('위도')) or 0:.3f}",
        f"{parse_number(record.get('경도')) or 0:.3f}",
    ])
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def read_existing() -> list[dict[str, str]]:
    with DATA_PATH.open('r', encoding='utf-8-sig', newline='') as file:
        rows = []
        for row in csv.DictReader(file):
            rows.append({field: (row.get(field) or '').strip() for field in FIELDS})
    return rows


def write_csv(rows: list[dict[str, str]]) -> None:
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, '') for field in FIELDS})
    write_if_changed(DATA_PATH, buffer.getvalue())


def request_recent_records(start: datetime, end: datetime, api_key: str) -> list[dict[str, str]]:
    query = urllib.parse.urlencode({
        'tm1': start.strftime('%Y%m%d%H%M'),
        'tm2': end.strftime('%Y%m%d%H%M'),
        'disp': '1',
        'help': '0',
        'authKey': api_key,
    })
    url = f'{API_URL}?{query}'
    request = urllib.request.Request(url, headers={'User-Agent': 'earthquake-data-journalism/1.0'})
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
    text = raw.decode('utf-8', errors='replace')
    if text.count('�') > 10:
        text = raw.decode('euc-kr', errors='replace')
    lowered = text.lower()
    if '<html' in lowered or 'error' in lowered and 'eqk' not in lowered:
        raise RuntimeError('KMA API returned an error response. Check the KMA_API_KEY secret and API access approval.')

    new_records: list[dict[str, str]] = []
    for row in csv.reader(io.StringIO(text)):
        cells = [cell.strip() for cell in row]
        if len(cells) < 9:
            continue
        occurrence = parse_datetime(cells[3])
        magnitude = parse_number(cells[5])
        latitude = parse_number(cells[6])
        longitude = parse_number(cells[7])
        if not occurrence or magnitude is None or latitude is None or longitude is None:
            continue
        intensity = cells[9] if len(cells) > 9 else ''
        new_records.append({
            '발생일시': occurrence.strftime('%Y-%m-%d %H:%M:%S'),
            '규모': f'{magnitude:.1f}',
            '깊이km': '',
            '최대진도': intensity,
            '위도': format_coordinate(latitude, 'N' if latitude >= 0 else 'S'),
            '경도': format_coordinate(longitude, 'E' if longitude >= 0 else 'W'),
            '위치': cells[8],
        })
    return new_records


def first_region(location: str) -> str:
    match = re.match(r'^(경북|북한|전남|제주|충남|강원|경남|전북|충북|경기|인천|울산|대구|부산|서울|세종)', location or '')
    return match.group(1) if match else '기타'


def summarize(rows: list[dict[str, str]]) -> dict[str, Any]:
    dated = []
    for row in rows:
        occurred = parse_datetime(row['발생일시'])
        magnitude = parse_number(row['규모'])
        if occurred and magnitude is not None:
            dated.append((row, occurred, magnitude))
    if not dated:
        raise RuntimeError('No valid records available for summary generation.')

    annual = Counter(item[1].year for item in dated)
    monthly = Counter(item[1].month for item in dated)
    magnitudes = [item[2] for item in dated]
    sorted_magnitudes = sorted(magnitudes)
    middle = len(sorted_magnitudes) // 2
    median = sorted_magnitudes[middle] if len(sorted_magnitudes) % 2 else (sorted_magnitudes[middle - 1] + sorted_magnitudes[middle]) / 2
    depths = [parse_number(item[0]['깊이km']) for item in dated]
    valid_depths = [depth for depth in depths if depth is not None]
    region_counts = Counter(first_region(item[0]['위치']) for item in dated)
    sea_count = sum('해역' in item[0]['위치'] for item in dated)
    highest = max(dated, key=lambda item: item[2])
    latest = max(dated, key=lambda item: item[1])
    major = sorted((item for item in dated if item[2] >= 5.0), key=lambda item: (-item[2], item[1]))[:5]

    return {
        'schemaVersion': 1,
        'generatedAt': latest[1].strftime('%Y-%m-%d'),
        'source': {
            'name': '기상청 지진정보 OPEN-API',
            'url': 'https://apihub.kma.go.kr/apiList.do?seqApi=7',
            'note': '국내 지진정보의 발표 기준과 API 제공 범위는 원천기관 안내를 따른다.',
        },
        'summary': {
            'recordCount': len(dated),
            'periodStart': min(item[1] for item in dated).strftime('%Y-%m-%d'),
            'periodEnd': latest[1].strftime('%Y-%m-%d'),
            'meanMagnitude': round(sum(magnitudes) / len(magnitudes), 2),
            'medianMagnitude': round(median, 2),
            'maxMagnitude': round(highest[2], 1),
            'maxMagnitudeDate': highest[1].strftime('%Y-%m-%d'),
            'maxMagnitudeLocation': highest[0]['위치'],
            'depthValidCount': len(valid_depths),
            'depthValidShare': round(len(valid_depths) / len(dated) * 100, 1),
            'depthMeanKm': round(sum(valid_depths) / len(valid_depths), 1) if valid_depths else None,
            'seaCount': sea_count,
            'seaShare': round(sea_count / len(dated) * 100, 1),
        },
        'yearlyCounts': [{'year': year, 'count': annual[year]} for year in sorted(annual)],
        'monthlyCounts': [{'month': month, 'count': monthly[month]} for month in range(1, 13)],
        'topRegions': [{'region': name, 'count': count} for name, count in region_counts.most_common(5)],
        'majorEvents': [
            {
                'datetime': occurred.strftime('%Y-%m-%d %H:%M:%S'),
                'magnitude': magnitude,
                'location': row['위치'],
                'depthKm': parse_number(row['깊이km']),
            }
            for row, occurred, magnitude in major
        ],
        'latestEvent': {
            'datetime': latest[1].strftime('%Y-%m-%d %H:%M:%S'),
            'magnitude': latest[2],
            'location': latest[0]['위치'],
        },
    }


def write_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding='utf-8') == content:
        return False
    path.write_text(content, encoding='utf-8')
    return True


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def overview_svg(summary: dict[str, Any]) -> str:
    data = summary['summary']
    cards = [
        ('기록 건수', f"{data['recordCount']:,}건", f"{data['periodStart']}~{data['periodEnd']}"),
        ('평균 규모', f"M {data['meanMagnitude']:.2f}", '전체 기록 기준'),
        ('최대 규모', f"M {data['maxMagnitude']:.1f}", data['maxMagnitudeDate']),
        ('깊이 유효값', f"{data['depthValidShare']:.1f}%", f"{data['depthValidCount']:,}건"),
    ]
    sections = []
    for index, (label, value, note) in enumerate(cards):
        x = 48 + index * 246
        sections.append(f'''<g transform="translate({x},236)">
          <rect width="214" height="142" rx="5" fill="#102a45" stroke="#29435a"/>
          <text x="20" y="31" fill="#9fb2c3" font-size="17" font-family="sans-serif">{esc(label)}</text>
          <text x="20" y="85" fill="#f2eee5" font-size="38" font-weight="700" font-family="sans-serif">{esc(value)}</text>
          <text x="20" y="116" fill="#72e5ff" font-size="14" font-family="sans-serif">{esc(note)}</text>
        </g>''')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="520" viewBox="0 0 1080 520" role="img" aria-labelledby="title desc">
      <title id="title">자동 갱신 한반도 지진 데이터 요약</title><desc id="desc">기록 수, 평균 규모, 최대 규모, 깊이 유효값을 요약한 인포그래픽</desc>
      <rect width="1080" height="520" fill="#071727"/>
      <text x="48" y="72" fill="#72e5ff" font-size="19" font-weight="700" font-family="sans-serif">LATEST DATA / KMA API</text>
      <text x="48" y="137" fill="#f2eee5" font-size="52" font-weight="700" font-family="sans-serif">한반도 지진 기록, 최신 요약</text>
      <text x="48" y="179" fill="#aebdca" font-size="22" font-family="sans-serif">마지막 기록 기준일 {esc(data['periodEnd'])} · 자동 갱신 데이터</text>
      <line x1="48" x2="1032" y1="206" y2="206" stroke="#29435a"/>
      {''.join(sections)}
      <text x="48" y="474" fill="#8196a8" font-size="14" font-family="sans-serif">출처: 기상청 지진정보 OPEN-API · 재생성 시점은 최신 발생 기록일을 기준으로 표시</text>
    </svg>'''


def yearly_svg(summary: dict[str, Any]) -> str:
    values = summary['yearlyCounts']
    peak = max(item['count'] for item in values)
    left, top, width, height = 88, 135, 900, 230
    step = width / max(len(values) - 1, 1)
    points = []
    labels = []
    for index, item in enumerate(values):
        x = left + index * step
        y = top + height - item['count'] / peak * height
        points.append(f'{x:.1f},{y:.1f}')
        if index == 0 or index == len(values) - 1 or item['year'] % 2 == 0:
            labels.append(f'<text x="{x:.1f}" y="400" text-anchor="middle" fill="#9fb2c3" font-size="13" font-family="sans-serif">{item["year"]}</text>')
    peak_item = max(values, key=lambda item: item['count'])
    peak_index = values.index(peak_item)
    peak_x = left + peak_index * step
    peak_y = top
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="460" viewBox="0 0 1080 460" role="img" aria-labelledby="title desc">
      <title id="title">연도별 지진 기록 추이</title><desc id="desc">자동 갱신 지진 데이터의 연도별 기록 건수 선 그래프</desc>
      <rect width="1080" height="460" fill="#0d2238"/>
      <text x="48" y="66" fill="#72e5ff" font-size="18" font-weight="700" font-family="sans-serif">YEARLY TREND / AUTO-UPDATED</text>
      <text x="48" y="109" fill="#f2eee5" font-size="36" font-weight="700" font-family="sans-serif">연도별 기록 수</text>
      <line x1="{left}" x2="{left + width}" y1="{top + height}" y2="{top + height}" stroke="#496276"/>
      <polyline points="{' '.join(points)}" fill="none" stroke="#72e5ff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="{peak_x:.1f}" cy="{peak_y:.1f}" r="8" fill="#ffbd69"/>
      <text x="{peak_x:.1f}" y="{peak_y - 18:.1f}" text-anchor="middle" fill="#ffbd69" font-size="17" font-weight="700" font-family="sans-serif">{peak_item['year']}년 {peak_item['count']}건</text>
      {''.join(labels)}
      <text x="48" y="435" fill="#8196a8" font-size="14" font-family="sans-serif">출처: 기상청 지진정보 OPEN-API · 최신 기록을 반영해 자동 재생성</text>
    </svg>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline', action='store_true', help='Skip the API request and regenerate assets from the local CSV only.')
    args = parser.parse_args()

    records = read_existing()
    if not args.offline:
        api_key = os.getenv('KMA_API_KEY', '').strip()
        if not api_key:
            print('KMA_API_KEY is not set; skipping remote update. Add the GitHub Actions secret before scheduled runs.', file=sys.stderr)
            return 0
        dated = [parse_datetime(row['발생일시']) for row in records]
        latest = max(value for value in dated if value)
        fetched = request_recent_records(latest - timedelta(days=30), datetime.now(KST).replace(tzinfo=None), api_key)
        known = {record_key(row) for row in records}
        additions = [row for row in fetched if record_key(row) not in known]
        if additions:
            records.extend(additions)
            records.sort(key=lambda row: parse_datetime(row['발생일시']) or datetime.min)
            write_csv(records)
            print(f'Added {len(additions)} new KMA API records.')
        else:
            print('No new KMA API records found in the rolling update window.')

    payload = summarize(records)
    changed = False
    changed |= write_if_changed(SITE_DATA, json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    changed |= write_if_changed(OVERVIEW_SVG, overview_svg(payload))
    changed |= write_if_changed(YEARLY_SVG, yearly_svg(payload))
    print(f'Generated site assets. changed={changed} records={payload["summary"]["recordCount"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
