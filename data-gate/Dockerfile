# Dockerfile
# Use the official Envoy Proxy image as the base
FROM docker.io/envoyproxy/envoy:v1.28-latest

# Copy the Envoy routing configuration and Wasm DLP filter owned by non-root envoy user
COPY --chown=envoy:envoy envoy.yaml /etc/envoy/envoy.yaml
COPY --chown=envoy:envoy target/wasm32-unknown-unknown/release/data_hop_firewall.wasm /etc/envoy/data_hop_firewall.wasm

# Drop root privileges to mitigate container breakout risk
USER envoy

# Expose the main ingress port for filtered traffic
EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD bash -c 'exec 3<>/dev/tcp/127.0.0.1/10000' || exit 1

# Start Envoy with our custom configuration
CMD ["/usr/local/bin/envoy", "-c", "/etc/envoy/envoy.yaml", "--service-cluster", "proxy"]
