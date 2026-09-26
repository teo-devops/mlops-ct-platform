{{- define "seaweedfs.image" -}}
{{ .Values.image.repository }}:{{ .Values.image.tag }}{{ with .Values.image.digest }}@{{ . }}{{ end }}
{{- end -}}
{{- define "seaweedfs.labels" -}}
app.kubernetes.io/name: seaweedfs
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: mlops-ct-platform
{{- end -}}
