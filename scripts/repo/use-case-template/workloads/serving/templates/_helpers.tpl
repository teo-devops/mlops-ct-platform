{{- define "serving.labels" -}}
app.kubernetes.io/part-of: {{ .Values.useCase }}
mlops-ct-platform.dev/use-case: {{ .Values.useCase }}
{{- end -}}
