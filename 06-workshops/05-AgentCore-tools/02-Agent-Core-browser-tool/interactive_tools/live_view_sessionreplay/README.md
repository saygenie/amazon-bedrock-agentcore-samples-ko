# Amazon Bedrock AgentCore SDK Tools 예제

이 폴더에는 Amazon Bedrock AgentCore SDK Tools 사용 방법을 보여 주는 예제가 포함되어 있습니다.

## Browser 도구

* `browser_viewer_replay.py` - 적절한 디스플레이 크기 조절을 지원하는 Amazon Bedrock AgentCore Browser Live Viewer
* `browser_interactive_session.py` - Live View, 녹화, 재생 기능을 갖춘 완전한 엔드 투 엔드 브라우저 환경
* `session_replay_viewer.py` - 녹화된 브라우저 세션을 재생하는 뷰어
* `view_recordings.py` - Amazon S3에 녹화된 세션을 보는 독립 실행형 스크립트

## 사전 요구 사항

### Python 종속성
```bash
pip install -r requirements.txt
```

필수 패키지: fastapi, uvicorn, rich, boto3, bedrock-agentcore

### AWS 자격 증명
AWS 자격 증명이 구성되어 있는지 확인합니다.
```bash
aws configure
```

## 예제 실행

### 녹화 및 재생을 포함한 전체 Browser 환경
`02-Agent-Core-browser-tool/interactive_tools` 디렉터리에서 다음 명령을 실행합니다.
```bash
python -m live_view_sessionreplay.browser_interactive_session
```

### 녹화물 보기
`02-Agent-Core-browser-tool/interactive_tools` 디렉터리에서 다음 명령을 실행합니다.
```bash
python -m live_view_sessionreplay.view_recordings --bucket YOUR_BUCKET --prefix YOUR_PREFIX
```

## 녹화 및 재생을 포함한 전체 Browser 환경

실시간 브라우저 보기, Amazon S3 자동 녹화, 통합 세션 재생을 포함한 완전한 엔드 투 엔드 워크플로를 실행합니다.

### 기능
- Amazon S3 자동 녹화를 사용하는 브라우저 세션 생성
- 대화형 제어권 전환(take/release)이 가능한 Live View
- 실행 중 디스플레이 해상도 조정
- Amazon S3에 세션 자동 녹화
- 녹화물을 볼 수 있는 통합 세션 재생 뷰어

### 작동 방식
1. 스크립트가 녹화를 활성화한 Browser를 생성합니다.
2. 브라우저 세션이 시작되고 로컬 브라우저에 표시됩니다.
3. Browser를 직접 제어하거나 자동화가 계속 실행되도록 둘 수 있습니다.
4. 모든 작업이 Amazon S3에 자동으로 녹화됩니다.
5. 세션을 종료하면(Ctrl+C) 녹화물을 보여 주는 재생 뷰어가 열립니다.

### 환경 변수
- `AWS_REGION` - AWS 리전(기본값: us-west-2)
- `AGENTCORE_ROLE_ARN` - Browser 실행용 IAM 역할 ARN(기본값: 계정 ID에서 자동 생성)
- `RECORDING_BUCKET` - 녹화물용 Amazon S3 버킷(기본값: session-record-test-{ACCOUNT_ID})
- `RECORDING_PREFIX` - 녹화물용 Amazon S3 접두사(기본값: replay-data)

### 필수 IAM 권한
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:CreateBucket",
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::session-record-test-*",
                "arn:aws:s3:::session-record-test-*/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": "bedrock:*",
            "Resource": "*"
        }
    ]
}
```

## 독립 실행형 Session Replay Viewer

새 Browser를 만들지 않고 Amazon S3에서 녹화된 브라우저 세션을 직접 확인하는 별도 도구입니다.

### 기능
- Amazon S3에 직접 연결하여 녹화물 보기
- 세션 ID를 지정하여 이전 녹화물 보기
- 세션 ID를 지정하지 않으면 최신 녹화물을 자동으로 검색

### 사용법

```bash
# Bucket의 최신 recording 보기
python -m live_view_sessionreplay.view_recordings --bucket session-record-test-123456789012 --prefix replay-data

# 특정 recording 보기
python -m live_view_sessionreplay.view_recordings --bucket session-record-test-123456789012 --prefix replay-data --session 01JZVDG02M8MXZY2N7P3PKDQ74

# 특정 AWS profile 사용
python -m live_view_sessionreplay.view_recordings --bucket session-record-test-123456789012 --prefix replay-data --profile my-profile
```

### 녹화물 찾기

Amazon S3 녹화물을 나열합니다.
```bash
aws s3 ls s3://session-record-test-123456789012/replay-data/ --recursive
```

## 문제 해결

### DCV SDK를 찾을 수 없음
DCV SDK 파일이 `interactive_tools/static/dcvjs/`에 있는지 확인합니다.

### 브라우저 세션이 표시되지 않음
- DCV SDK가 올바르게 설치되었는지 확인
- 브라우저 콘솔(F12)에서 오류 확인
- AWS 자격 증명에 적절한 권한이 있는지 확인

### 녹화가 작동하지 않음
- Amazon S3 버킷이 존재하고 액세스 가능한지 확인
- Amazon S3 작업에 대한 IAM 권한 확인
- 실행 역할에 적절한 권한이 있는지 확인

### Session Replay 문제
- Amazon S3에 녹화물이 있는지 확인(AWS CLI 또는 콘솔 사용)
- 콘솔 로그에서 오류 확인
- Amazon S3 버킷 정책에서 객체 읽기를 허용하는지 확인

### Amazon S3 액세스 오류
- AWS 자격 증명이 구성되어 있는지 확인
- Amazon S3 작업에 대한 IAM 권한 확인
- 버킷 이름이 전역적으로 고유한지 확인

## 아키텍처 참고 사항
- Live Viewer는 FastAPI를 사용하여 미리 서명된 DCV URL을 제공합니다.
- 녹화는 데이터 플레인의 Browser 서비스에서 직접 처리합니다.
- 재생에는 rrweb-player를 사용하여 녹화된 이벤트를 표시합니다.
- 모든 구성 요소는 함께 또는 독립적으로 작동할 수 있습니다.
