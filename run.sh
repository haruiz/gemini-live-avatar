 lsof -ti :8080 | xargs -r kill -9 && gemini-live-avatar \
 --google-search-grounding \
 --workers 1 \
 --avatar-path "https://models.readyplayer.me/6837ead83a298813297870d9.glb" \
 --mcp-server-config "./mcp.config.json" \
 --response-modality "audio" # --response-modality "text"
