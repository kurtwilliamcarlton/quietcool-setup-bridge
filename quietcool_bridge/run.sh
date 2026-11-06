#!/command/with-contenv bashio
set -e
bashio::log.info "Starting QuietCool Setup Bridge on Ingress port 8099"
exec python3 /opt/quietcool/server.py
