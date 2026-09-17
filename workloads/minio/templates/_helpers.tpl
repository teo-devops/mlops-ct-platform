{{- define "minio.image" -}}
{{ .Values.image.repository }}:{{ .Values.image.tag }}{{ with .Values.image.digest }}@{{ . }}{{ end }}
{{- end -}}
{{- define "minio.mcImage" -}}
{{ .Values.mcImage.repository }}:{{ .Values.mcImage.tag }}{{ with .Values.mcImage.digest }}@{{ . }}{{ end }}
{{- end -}}
{{- define "minio.labels" -}}
app.kubernetes.io/name: minio
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: mlops-ct-platform
{{- end -}}
