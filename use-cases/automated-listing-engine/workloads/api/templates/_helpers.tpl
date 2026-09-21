{{- define "api.labels" -}}
app.kubernetes.io/name: automated-listing-engine-api
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: automated-listing-engine
mlops-ct-platform.dev/use-case: automated-listing-engine
{{- end -}}

{{/* The pod template, shared by the Deployment (default) and the Rollout (progressive delivery). */}}
{{- define "api.podTemplate" -}}
metadata:
  labels:
    {{- include "api.labels" . | nindent 4 }}
  annotations:
    checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
spec:
  serviceAccountName: automated-listing-engine-api
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001
    seccompProfile: {type: RuntimeDefault}
  containers:
    - name: api
      image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
      imagePullPolicy: {{ .Values.image.pullPolicy }}
      ports:
        - name: http
          containerPort: 8000
          protocol: TCP    # explicit: Argo CD cannot default it on a Rollout (CRD)
      envFrom:
        - configMapRef:
            name: automated-listing-engine-api
        {{- if .Values.predictionLog.enabled }}
        - secretRef:
            name: {{ .Values.predictionLog.secretName }}
        {{- end }}
      readinessProbe:
        httpGet: {path: /readyz, port: http}
        periodSeconds: 5
      livenessProbe:
        httpGet: {path: /healthz, port: http}
        initialDelaySeconds: 10
        periodSeconds: 20
      resources:
        {{- toYaml .Values.resources | nindent 12 }}
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities: {drop: [ALL]}
      volumeMounts:
        - name: tmp
          mountPath: /tmp
  volumes:
    - name: tmp
      emptyDir: {}
{{- end -}}
