# 01 — 사용자 지정 컨테이너

기본 Amazon Linux VM 대신 **사용자 고유의 컨테이너 이미지** 안에서 AgentCore Harness 에이전트를 실행합니다. 이를 통해 에이전트에 필요한 모든 런타임, 시스템 라이브러리, 사전 설치 종속성을 사용할 수 있습니다.

## 사용자 지정 컨테이너가 필요한 이유

기본적으로 AgentCore Harness 세션은 Python이 사전 설치된 Amazon Linux 2023에서 실행됩니다. 하지만 실제 환경의 에이전트에는 다음 항목이 필요한 경우가 많습니다.

- 특정 언어 런타임(Node.js, Go, Rust, Java, Ruby 등)
- 시스템 라이브러리(ImageMagick, FFmpeg, Headless Chromium 등)
- 사전 설치된 종속성(프레임워크, ML 모델, 자체 소스 코드)
- 프로덕션 환경과 일치하도록 제한된 환경

사용자 지정 컨테이너를 사용하면 Public ECR, Private ECR 또는 OCI 호환 레지스트리에서 자체 Linux ARM64 이미지를 가져올 수 있습니다.

## 폴더 구성

| 파일 | 유형 | 설명 |
|---|---|---|
| [`01_custom_container_node.ipynb`](01_custom_container_node.ipynb) | 노트북 | **Node.js** 컨테이너를 연결하고, 에이전트에게 HTTP 서버를 빌드하도록 요청한 뒤 npm으로 `chalk`를 설치하고 실행합니다. 이 모든 작업은 에이전트의 VM 안에서 이루어집니다. |
| [`02_custom_container_cli.py`](02_custom_container_cli.py) | CLI 스크립트 | 독립 실행형 명령줄 버전입니다. `--language node\|go\|python` 프리셋 또는 원시 `--container URI`를 통해 **모든 컨테이너 이미지**와 함께 사용할 수 있습니다. |
| [`03_custom_container_go.ipynb`](03_custom_container_go.ipynb) | 노트북 | **Go** 컨테이너를 연결하고, 에이전트가 HTTP 서버를 작성하고 `go build`로 빌드한 후 실행하도록 합니다. 이어서 linux/amd64용 바이너리를 **크로스 컴파일**합니다. |

## 주요 학습 개념

- **`environmentArtifact.optionalValue.containerConfiguration.containerUri`** — 컨테이너 이미지를 연결하는 `update_harness` 필드
- **`systemPrompt`** — 에이전트가 적절한 도구를 선택할 수 있도록 사용 가능한 런타임을 알려 주는 설정
- **`invoke_agent_runtime_command`** (ExecuteCommand) — 에이전트 루프를 거치지 않고 VM에서 직접 명령을 실행하는 기능(`node --version`, `go env` 확인 및 생성된 파일 검사에 유용)
- **세션 지속성** — 동일한 `runtimeSessionId`를 사용하면 여러 호출에서 VM 상태가 유지됨(파일과 설치된 패키지가 그대로 유지됨)

## 실행 방법

### 노트북
Jupyter 또는 VSCode에서 열고 셀을 순서대로 실행합니다. 하단의 정리 셀은 AgentCore Harness를 삭제합니다.

### CLI
```bash
# 언어 preset
python 02_custom_container_cli.py --language node      # 기본값
python 02_custom_container_cli.py --language go
python 02_custom_container_cli.py --language python

# ARM64 호환 container image
python 02_custom_container_cli.py \
    --container public.ecr.aws/docker/library/rust:slim \
    --message "Write a Rust program that prints system info."

# 기타 옵션
python 02_custom_container_cli.py --skip-cleanup   # 데모 후 Harness 유지
python 02_custom_container_cli.py --raw-events     # 원시 streaming JSON dump
python 02_custom_container_cli.py --help
```

## 컨테이너 이미지 예시

| 이미지 | 사용 사례 |
|---|---|
| `public.ecr.aws/docker/library/node:slim` | Node.js/npm 생태계 |
| `public.ecr.aws/docker/library/golang:1.24` | Go 도구 체인 및 크로스 컴파일 |
| `public.ecr.aws/docker/library/python:3.12-slim` | 특정 버전의 Python |
| Private ECR 이미지 | 사용자 지정 종속성, 미리 로드된 소스 코드, ML 모델 |

> 컨테이너는 **linux/arm64**를 지원해야 합니다. AgentCore Harness VM은 ARM에서 실행됩니다.
