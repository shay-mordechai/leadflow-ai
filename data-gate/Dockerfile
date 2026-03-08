# Dockerfile
# Use the official Envoy Proxy image as the base
FROM docker.io/envoyproxy/envoy:v1.28-latest

# Copy the Envoy routing configuration
COPY envoy.yaml /etc/envoy/envoy.yaml

# Copy the compiled WebAssembly (Wasm) DLP filter
COPY target/wasm32-unknown-unknown/release/data_hop_firewall.wasm /etc/envoy/data_hop_firewall.wasm

# Expose the main ingress port for filtered traffic
EXPOSE 10000

# Start Envoy with our custom configuration
CMD ["/usr/local/bin/envoy", "-c", "/etc/envoy/envoy.yaml", "--service-cluster", "proxy"]
