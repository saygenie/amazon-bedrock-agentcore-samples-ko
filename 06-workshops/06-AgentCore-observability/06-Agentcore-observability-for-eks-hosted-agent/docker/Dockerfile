FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

# 시스템 종속성 설치
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python 종속성 설치
# requirements 파일 복사
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY app/ .

# 애플리케이션을 실행할 non-root 사용자 생성
RUN useradd -m appuser
USER appuser

# 앱이 실행되는 포트 노출
EXPOSE 8000

ENV OTEL_PYTHON_DISTRO=aws_distro
ENV OTEL_PYTHON_CONFIGURATOR=aws_configurator
ENV OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
ENV OTEL_TRACES_EXPORTER=otlp
ENV AGENT_OBSERVABILITY_ENABLED=true
# 빌드 전에 아래 값을 업데이트하세요
ENV OTEL_RESOURCE_ATTRIBUTES=service.name=<YOUR_SERVICE_NAME>
ENV OTEL_EXPORTER_OTLP_LOGS_HEADERS=x-aws-log-group=<YOUR_LOG_GROUP>,x-aws-log-stream=<YOUR_LOG_STREAM>,x-aws-metric-namespace=<YOUR_METRIC_NAMESPACE>

# OpenTelemetry 계측으로 애플리케이션을 실행하는 명령
# opentelemetry-instrument는 앱을 자동 계측하도록 Python을 래핑
# 호스트(0.0.0.0)와 포트(8000)는 app.py에서 구성
CMD ["opentelemetry-instrument", "python", "app.py"]
