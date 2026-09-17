{{- define "api.labels" -}}
app.kubernetes.io/name: listing-engine-api
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: listing-engine
mlops-ct-platform.dev/use-case: listing-engine
{{- end -}}
