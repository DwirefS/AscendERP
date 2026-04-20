{{/*
Expand the name of the chart.
*/}}
{{- define "capital-markets.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "capital-markets.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "capital-markets.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "capital-markets.labels" -}}
helm.sh/chart: {{ include "capital-markets.chart" . }}
{{ include "capital-markets.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "capital-markets.selectorLabels" -}}
app.kubernetes.io/name: {{ include "capital-markets.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
flavor: capital-markets
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "capital-markets.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "capital-markets.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the secret for database credentials
*/}}
{{- define "capital-markets.secretName" -}}
{{- if .Values.secrets.name }}
{{- .Values.secrets.name }}
{{- else }}
{{- printf "%s-secrets" (include "capital-markets.fullname" .) }}
{{- end }}
{{- end }}

{{/*
Generate database connection string
*/}}
{{- define "capital-markets.databaseConnectionString" -}}
postgresql://{{ .Values.postgresql.auth.username }}:{{ .Values.postgresql.auth.password }}@postgresql.{{ .Release.Namespace }}.svc.cluster.local:5432/{{ .Values.postgresql.auth.database }}
{{- end }}

{{/*
Return the appropriate apiVersion for RBAC APIs
*/}}
{{- define "capital-markets.rbac.apiVersion" -}}
rbac.authorization.k8s.io/v1
{{- end }}

{{/*
Return the appropriate image for the agents
*/}}
{{- define "capital-markets.image" -}}
{{- $registry := .Values.global.imageRegistry }}
{{- $repository := .image.repository }}
{{- $tag := .image.tag | default $.Chart.AppVersion }}
{{- printf "%s/%s:%s" $registry $repository $tag }}
{{- end }}

{{/*
Return the appropriate pull policy
*/}}
{{- define "capital-markets.imagePullPolicy" -}}
{{- .imagePullPolicy | default .Values.global.imagePullPolicy }}
{{- end }}

{{/*
Validate required values
*/}}
{{- define "capital-markets.validateValues" -}}
{{- if not .Values.postgresql.enabled }}
error: PostgreSQL must be enabled
{{- end }}
{{- end }}

{{/*
Return the appropriate apiVersion for PodSecurityPolicy
*/}}
{{- define "capital-markets.podSecurityPolicy.apiVersion" -}}
{{- if .Capabilities.APIVersions.Has "policy/v1beta1" }}
policy/v1beta1
{{- else }}
policy/v1beta1
{{- end }}
{{- end }}

{{/*
Return the appropriate apiVersion for NetworkPolicy
*/}}
{{- define "capital-markets.networkPolicy.apiVersion" -}}
networking.k8s.io/v1
{{- end }}

{{/*
Return the appropriate apiVersion for Deployment
*/}}
{{- define "capital-markets.deployment.apiVersion" -}}
apps/v1
{{- end }}

{{/*
Return the appropriate apiVersion for Service
*/}}
{{- define "capital-markets.service.apiVersion" -}}
v1
{{- end }}

{{/*
Return the appropriate apiVersion for ConfigMap
*/}}
{{- define "capital-markets.configmap.apiVersion" -}}
v1
{{- end }}

{{/*
Return the appropriate apiVersion for Secret
*/}}
{{- define "capital-markets.secret.apiVersion" -}}
v1
{{- end }}

{{/*
Return CPU and Memory limits for pod
*/}}
{{- define "capital-markets.resources" -}}
resources:
  requests:
    cpu: {{ .requests.cpu | quote }}
    memory: {{ .requests.memory | quote }}
  limits:
    cpu: {{ .limits.cpu | quote }}
    memory: {{ .limits.memory | quote }}
{{- end }}
