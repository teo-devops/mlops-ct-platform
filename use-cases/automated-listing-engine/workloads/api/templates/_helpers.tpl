{{- define "api.labels" -}}
app.kubernetes.io/name: automated-listing-engine-api
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: automated-listing-engine
mlops-ct-platform.dev/use-case: automated-listing-engine
{{- end -}}
