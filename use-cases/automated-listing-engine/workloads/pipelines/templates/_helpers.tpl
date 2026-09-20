{{- define "pipelines.labels" -}}
app.kubernetes.io/part-of: {{ .Values.useCase }}
mlops-ct-platform.dev/use-case: {{ .Values.useCase }}
{{- end -}}

{{/* Environment shared by every step: the contract variables of libs/ctsteps. */}}
{{- define "pipelines.stepEnv" -}}
- name: CT_USE_CASE
  value: {{ .Values.useCaseRef | quote }}
- name: CT_NAMESPACE
  value: {{ .Release.Namespace }}
- name: S3_ENDPOINT_URL
  value: {{ .Values.artifactStore.endpointUrl }}
- name: MLFLOW_S3_ENDPOINT_URL
  value: {{ .Values.artifactStore.endpointUrl }}
- name: AWS_DEFAULT_REGION
  value: us-east-1
- name: CT_DATASETS_BUCKET
  value: {{ .Values.artifactStore.datasetsBucket }}
- name: CT_MODELS_BUCKET
  value: {{ .Values.artifactStore.modelsBucket }}
- name: CT_PREDICTIONS_BUCKET
  value: {{ .Values.artifactStore.predictionsBucket }}
- name: MLFLOW_TRACKING_URI
  value: {{ .Values.registry.trackingUri }}
- name: MLFLOW_DISABLE_AGENT_HINT
  value: "1"
- name: CT_OUTPUTS_DIR
  value: /tmp/outputs
- name: CT_GIT_COMMIT
  value: {{ .Values.image.tag | quote }}
{{- end -}}
