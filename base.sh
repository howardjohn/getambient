#!/usr/bin/env bash
set -eu
clr='\e[0m'
blue='\e[0;34m'

function apply() {
  echo -en  ${blue}Applying ${1}...${clr}
  kubectl apply -f - > /dev/null
  echo ✅
}

function build_kind() {
    if ! kind get clusters | grep -q ^ambient-demo$; then
      echo -e ${blue}Creating cluster...${clr}
      cat <<EOF | kind create cluster --name ambient-demo --image gcr.io/istio-testing/kind-node:v1.30.0 --config=- || return 1
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
- role: worker
  labels:
    topology.kubernetes.io/region: worker1
- role: worker
  labels:
    topology.kubernetes.io/region: worker2
EOF
  fi
  kind export kubeconfig --name ambient-demo &> /dev/null
}
{% filter mkcli(
    name="getambient",
    flags=[
      Flag("no-kiali", default="off", help="disable Kiali", flag_only=True),
      Flag("no-prometheus", default="off", help="disable Prometheus", flag_only=True),
      Flag("no-grafana", default="off", help="do not deploy Grafana", flag_only=True),
      Flag("no-metallb", default="off", help="disable MetalLB", flag_only=True),
      Flag("no-cluster", default="off", help="use existing cluster", flag_only=True),
      Flag("no-bookinfo", default="off", help="do not deploy bookinfo", flag_only=True),
      Flag("no-gateway", default="off", help="do not deploy gateway", flag_only=True),
    ],
) %}
if [[ "${no_cluster}" != "on" ]]; then
  build_kind
fi

cat <<'EOF' | apply Istio
{{ readfile('istio.yaml') }}
EOF

if [[ "${no_prometheus}" != "on" ]]; then
  cat <<'EOF' | apply Prometheus
{{ readfile('prometheus.yaml') }}
EOF
fi

if [[ "${no_kiali}" != "on" ]]; then
  cat <<'EOF' | apply Kiali
{{ readfile('kiali.yaml') }}
EOF
fi

if [[ "${no_grafana}" != "on" ]]; then
  cat <<'EOF' | apply Grafana
{{ readfile('grafana.yaml') }}
EOF
fi

if [[ "${no_metallb}" != "on" ]]; then
  cat <<'EOF' | apply MetalLB
{{ readfile('metallb.yaml') }}
EOF
fi


if [[ "${no_bookinfo}" != "on" ]]; then
  cat <<'EOF' | apply "Bookinfo Demo App"
{{ readfile('bookinfo.yaml') }}
EOF
fi

if [[ "${no_gateway}" != "on" ]]; then

  cat <<'EOF' | apply "Gateway API"
{{ readfile('gateway-api-crd.yaml') }}
EOF

  cat <<'EOF' | apply "Ingress Gateway"
{{ readfile('gateway.yaml') }}
EOF
fi

kubectl label ns default istio.io/dataplane-mode=ambient &> /dev/null

echo -e "$(cat <<EOF
${blue}Istio ambient mode demo successfully deployed!${clr}
* Kiali is deployed at http://kiali.getambient.howardjohn.info/.
* Prometheus is deployed at http://prometheus.getambient.howardjohn.info/.
* Grafana is deployed at http://grafana.getambient.howardjohn.info/.
* Bookinfo is deployed at http://bookinfo.getambient.howardjohn.info/productpage.
${blue}Note${clr}: URLS refer to local IPs, so must be accessed from the machine the demo is deployed on.
EOF
)"

{% endfilter %}
