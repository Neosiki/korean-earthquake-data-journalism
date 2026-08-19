# 지진 데이터 자동 갱신 운영 안내

이 저장소는 GitHub Actions를 이용해 **매일 09:15 KST**에 기상청 지진정보 OPEN-API를 확인하고, 최근 기록·웹페이지 요약 수치·SVG 인포그래픽을 갱신하도록 구성되어 있습니다. GitHub의 예약 워크플로는 기본 브랜치의 최신 커밋에서 실행되며, 이 저장소에서는 `main` 브랜치를 기준으로 동작합니다.[1]

| 항목 | 설정 |
|---|---|
| 워크플로 | `.github/workflows/refresh-earthquake-data.yml` |
| 갱신 스크립트 | `scripts/update_earthquake_data.py` |
| 실행 시각 | 매일 00:15 UTC / 09:15 KST |
| 데이터 원천 | 기상청 지진정보 OPEN-API [2] |
| 인증 방식 | GitHub 저장소 비밀값 `KMA_API_KEY` |
| 자동 산출물 | `docs/site-data.json`, `docs/media/latest_overview.svg`, `docs/media/latest_yearly_trend.svg` |

## 갱신 방식

자동 작업은 최근 기록을 기준으로 **30일의 중첩 조회 구간**을 다시 가져와 수정·재통보 가능성을 고려하고, 발생시각·규모·좌표를 기준으로 중복을 제거합니다. 새 기록이 있거나 자동 생성 파일이 달라졌을 때만 변경사항을 커밋합니다. 변경 커밋은 GitHub Pages의 `main/docs` 배포를 다시 실행합니다.

웹페이지는 `site-data.json`을 읽어 기록 수, 최대·평균 규모, 깊이 유효값, 마지막 기록 기준일을 표시합니다. 따라서 고정 HTML의 문구를 매일 직접 수정하지 않아도 최신 요약과 인포그래픽이 반영됩니다. 상세 기사는 기준일과 방법론을 명시한 분석 기사로 유지되며, 자동 갱신 지표는 별도 최신 섹션에서 확인할 수 있습니다.

## 수동 실행과 점검

GitHub 저장소의 **Actions** 탭에서 `Refresh KMA earthquake data` 워크플로를 선택한 뒤 **Run workflow**를 실행하면 예약 시각을 기다리지 않고 즉시 갱신을 시험할 수 있습니다. 실패하면 먼저 `KMA_API_KEY`가 저장소 비밀값으로 존재하는지, 기상청 API 활용 권한이 승인되었는지, 그리고 Actions 설정에서 워크플로가 저장소 콘텐츠를 쓸 수 있는지 확인합니다.

> 공개 페이지의 인터랙티브 지도는 별도의 내장 원자료를 유지합니다. 자동 갱신은 랜딩 페이지의 최신 요약·SVG 인포그래픽·정제 CSV를 우선 갱신하며, 지도 원본 데이터의 수집·정제 기준이 다를 수 있다는 안내를 페이지에 표시합니다.

## 참고자료

[1]: https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions "GitHub Actions 워크플로 문법"
[2]: https://apihub.kma.go.kr/apiList.do?seqApi=7 "기상청 지진·화산 OPEN-API"
