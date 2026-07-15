FROM public.ecr.aws/docker/library/python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

# 모든 환경 변수를 하나의 레이어에 설정
ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1 \
    AWS_REGION=us-west-2 \
    AWS_DEFAULT_REGION=us-west-2



COPY agents/requirements.txt agents/requirements.txt
# requirements 파일에서 설치
RUN uv pip install -r agents/requirements.txt





# 호스트 바인딩 로직에서 Docker 실행 환경임을 알림
ENV DOCKER_CONTAINER=1

# non-root 사용자 생성
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 9000
EXPOSE 8000
EXPOSE 8080

# 전체 프로젝트 복사(.dockerignore 적용)
COPY . .

# 전체 모듈 경로 사용

CMD ["python", "-m", "agents.strands_claude"]
