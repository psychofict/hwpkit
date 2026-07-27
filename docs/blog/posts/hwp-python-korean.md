---
date: 2026-06-09
slug: read-extract-hwp-files-python-ko
authors: [ebenworks]
categories:
  - Tutorials
description: >-
  파이썬으로 한글 HWP·HWPX 파일을 읽고 텍스트를 추출하고 편집하는 방법 —
  한컴오피스나 윈도우 없이 순수 파이썬으로.
---

# 파이썬으로 HWP·HWPX 파일 읽기와 텍스트 추출하기

한국의 공공기관, 대학, 법원, 그리고 대부분의 기업은 **HWP**(한글 워드
프로세서, 한컴오피스의 `.hwp`·`.hwpx` 형식)로 문서를 주고받습니다. 그런데
`python-docx`, `pdfplumber`, `unstructured` 같은 도구는 HWP를 읽지 못하고,
읽을 수 있는 `pyhwpx`는 **윈도우 + 한컴 설치 + COM**이 필요해 리눅스 서버나
CI, 컨테이너에서는 쓸 수 없습니다.

이 글에서는 [`hwpkit`](https://github.com/psychofict/hwpkit)으로 **`.hwp`와
`.hwpx`를 순수 파이썬으로 읽고, 텍스트를 추출하고, 편집하는 방법**을
정리합니다. 한컴이나 윈도우 없이 어디서든 동작합니다.

<!-- more -->

## 설치

```bash
pip install hwpkit[full]
```

기본 설치는 `olefile`만 필요하고, `[full]` 옵션이 `.hwpx`용 `lxml`과 이미지
삽입용 `Pillow`를 추가합니다.

## HWP·HWPX에서 텍스트 추출하기

가장 흔한 작업 — 한글 문서를 검색·색인·LLM 입력용 일반 텍스트로 바꾸기:

```python
from hwpkit import extract_text_from_file

text = extract_text_from_file("계약서.hwp")     # .hwpx도 동일하게 동작
print(text)
```

`extract_text_from_file`은 확장자가 아니라 **파일 내용으로 형식을 자동
판별**하므로, `.hwp`와 `.hwpx`가 섞인 폴더도 분기 없이 처리됩니다. 내부적으로
모든 구역(section)을 순회하며 표·이미지·각주·페이지번호 같은 인라인 컨트롤을
제거하고, 표 셀 내용을 포함한 **문단 단위의 깔끔한 텍스트**를 돌려줍니다.

명령줄에서도 됩니다:

```bash
hwpkit-text 계약서.hwp
```

## RAG / LLM 파이프라인에 넣기

한국어 RAG 파이프라인 대부분이 빠뜨리는 전처리 단계가 바로 이것입니다.
HWP 문서 보관소 전체를 벡터 DB에 색인하기:

```python
import glob
from hwpkit import extract_text_from_file

for path in glob.glob("corpus/**/*.hwp*", recursive=True):   # .hwp + .hwpx
    text = extract_text_from_file(path)
    vector_db.add(doc_id=path, content=text)
```

`hwpkit`은 LLM 의존성이 전혀 없습니다 — 어떤 청커·임베딩·컨텍스트에든 바로
넣을 수 있는 깨끗한 한국어 텍스트 소스입니다.

## 양식 채우기와 편집

읽기는 절반일 뿐입니다. 한국의 행정 업무는 `.hwp` **양식**(지원서, 결격사유
점검표, 점수표 등) 위에서 돌아갑니다. `hwpkit`은 파일을 손상시키지 않고
편집하며, 두 형식 모두 **동일한 객체 API**를 씁니다:

```python
from hwpkit import open_document

doc = open_document("지원서.hwp")              # 또는 "지원서.hwpx"
print(doc.describe())                          # 문단 인덱스로 필드 위치 찾기
doc.inject_text(24, "홍길동")                   # 빈 칸 채우기
doc.swap_in_para_text(40, "□ 동의", "☑ 동의")   # 체크박스 체크
doc.replace_text(75, "2026. 05. 19.")          # 셀 내용 교체
doc.save("작성완료.hwp")
```

## 도장·서명 이미지 삽입

양식에는 글자뿐 아니라 도장/직인/서명 이미지가 필요할 때가 많습니다:

```python
doc = open_document("계약서.hwp")
doc.place_image(42, "도장.png", width_mm=30)   # 가로 30mm, 비율 유지
doc.save("날인완료.hwp")
```

## 왜 한컴 자동화(pyhwpx)가 아니라 hwpkit인가

`pyhwpx`는 한컴오피스 앱을 COM으로 제어합니다. 강력하지만 **윈도우와 한컴
설치가 필수**라 서버·CI·컨테이너에서는 못 씁니다. `hwpkit`은 순수 파이썬이라
어디서든 동작합니다. (`pyhwp`는 바이너리 레코드 포맷과 HWP→XML 변환에
훌륭하지만 읽기 중심이고 `.hwpx`는 다루지 않습니다.) 자세한
[비교는 여기](../../comparison.md)에 있습니다.

## `.hwp` 편집이 까다로운 이유

바이너리 `.hwp`는 deflate로 압축된 레코드 스트림을 담은 MS-CFB 컨테이너입니다.
한글 텍스트를 넣는 순간 스트림 길이가 바뀌는데, 단순히 다시 쓰면 한컴이 열 때
검증하는 **레드-블랙 트리 디렉터리 구조**가 깨지고, 문단별 **레이아웃 캐시**를
제대로 무효화하지 않으면 글자가 한 줄에 뭉쳐 렌더링됩니다. `hwpkit`은 이
두 가지를 모두 처리합니다. 더 깊이 보려면
[gotchas](../../GOTCHAS.md)와 [객체 모델](../../OBJECT_MODEL.md) 문서를
참고하세요.

## 마무리

한국어 HWP·HWPX 문서를 파이썬에서 읽고, 추출하고, 편집해야 한다면 —
RAG 파이프라인이든 양식 자동화든 일회성 마이그레이션이든 — `hwpkit`이 순수
파이썬으로, 어떤 환경에서든 해결해 줍니다.

```bash
pip install hwpkit[full]
```

- **GitHub:** [github.com/psychofict/hwpkit](https://github.com/psychofict/hwpkit)
- **문서:** [hwpkit.ebenworks.co](https://hwpkit.ebenworks.co)

`hwpkit`이 아직 처리하지 못하는 형식이 있다면 이슈로 알려주세요 — 피드백이
로드맵을 만듭니다. 🙏
