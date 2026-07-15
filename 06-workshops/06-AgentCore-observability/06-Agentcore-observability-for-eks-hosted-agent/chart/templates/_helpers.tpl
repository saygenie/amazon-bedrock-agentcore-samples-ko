{{/*
chart 이름을 확장합니다.
*/}}
{{- define "strands-agents-travel.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
기본 정규화된 앱 이름을 생성합니다.
일부 Kubernetes 이름 필드는 DNS 명명 사양에 따라 63자로 제한되므로 잘라냅니다.
release 이름에 chart 이름이 포함되어 있으면 전체 이름으로 사용합니다.
*/}}
{{- define "strands-agents-travel.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
chart label에 사용할 chart 이름과 version을 생성합니다.
*/}}
{{- define "strands-agents-travel.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
공통 label
*/}}
{{- define "strands-agents-travel.labels" -}}
helm.sh/chart: {{ include "strands-agents-travel.chart" . }}
{{ include "strands-agents-travel.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
선택기 label
*/}}
{{- define "strands-agents-travel.selectorLabels" -}}
app.kubernetes.io/name: {{ include "strands-agents-travel.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
사용할 service account 이름 생성
*/}}
{{- define "strands-agents-travel.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "strands-agents-travel.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
