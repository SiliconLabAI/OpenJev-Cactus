!curl -s -o /tmp/resp.json -w "%{time_total}" \
  http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"needle","messages":[{"role":"user","content":"dim the living room lights to 30"}],"tools":[{"type":"function","function":{"name":"set_lights","description":"Control room lights","parameters":{"type":"object","properties":{"room":{"type":"string"},"brightness":{"type":"integer"}},"required":["room"]}}}]}' \
  | awk '{printf "Total: %.0f ms\n", $1 * 1000}'