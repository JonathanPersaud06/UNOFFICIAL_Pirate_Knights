import os
import requests
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

class AIPAgentClient:
    """
    Client for interacting with Palantir AIP (Artificial Intelligence Platform) Agent Service.
    Handles session lifecycle and prompts.
    """
    def __init__(self, base_url: str = None, token: str = None, agent_id: str = None):
        # Load from environment if not explicitly provided
        self.base_url = (base_url or os.getenv("PALANTIR_AIP_URL") or os.getenv("PALANTIR_URL") or "").strip().rstrip("/")
        self.token = (token or os.getenv("PALANTIR_AIP_TOKEN") or "").strip()
        self.agent_id = (agent_id or os.getenv("PALANTIR_AIP_AGENT_ID") or os.getenv("AGENT_ID") or "").strip()

        self._discovered_api_path = None
        self._use_encoding = True

        # Simple verification
        if not self.base_url:
            logger.warning("PALANTIR_AIP_URL is not set!")
        if not self.token:
            logger.warning("PALANTIR_AIP_TOKEN is not set!")
        if not self.agent_id:
            logger.warning("PALANTIR_AIP_AGENT_ID is not set!")

        if self.is_configured:
            logger.info(f"✨ Palantir AIP Client successfully initialized with live Agent ID '{self.agent_id}' on domain '{self.base_url}'.")

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.token and self.agent_id)

    def _encode_rid(self, rid: str) -> str:
        """
        URL-encodes a Palantir Resource Identifier (RID).
        Special care is taken to encode dots '.' as '%2E' to prevent web servers, WAFs,
        and reverse proxies from treating the double dots '..' inside RIDs (e.g., 'ri.aip-agents..agent.')
        as a directory traversal attempt, which typically results in 404 Not Found or 400 Bad Request.
        """
        if not rid:
            return ""
        return quote(rid, safe='').replace(".", "%2E")

    def _send_request(self, method: str, url: str, headers: dict, json_data: dict = None, timeout: int = 15) -> requests.Response:
        """
        Sends an HTTP request with the exact URL provided, bypassing python-requests'
        automatic path normalization. This ensures that percent-encoded characters like
        %2E (for '.') are preserved over the wire and not unquoted/collapsed.
        """
        session = requests.Session()
        req = requests.Request(method, url, headers=headers, json=json_data)
        prepared = session.prepare_request(req)
        # Force the PreparedRequest to use our exact encoded URL, bypassing urllib/requests normalization
        prepared.url = url
        return session.send(prepared, timeout=timeout)

    @property
    def api_path(self) -> str:
        """
        Dynamically determine the API base path based on the Agent/Chatbot ID (RID) format.
        Older instances of Foundry use 'aip-agents/agents', newer ones use 'aip-chatbots/chatbots'.
        Can be overridden with PALANTIR_AIP_TYPE env var ('chatbot' or 'agent').
        """
        aip_type = os.getenv("PALANTIR_AIP_TYPE", "chatbot").strip().lower()
        if aip_type == "agent":
            return "api/v1/aip-agents/agents"
        elif aip_type == "chatbot":
            return "api/v1/aip-chatbots/chatbots"

        if self.agent_id and "aip-chatbots" in self.agent_id:
            return "api/v1/aip-chatbots/chatbots"
        
        return "api/v1/aip-chatbots/chatbots"

    def _discover_endpoint(self) -> tuple[str, bool]:
        """
        Proactively probes and discovers the correct API path and RID encoding scheme
        by trying common Palantir API paths and checking their response codes.
        Returns a tuple of (discovered_path, use_encoding).
        """
        if self._discovered_api_path is not None:
            return self._discovered_api_path, self._use_encoding

        logger.info("🔮 Palantir AIP: Starting self-healing API endpoint auto-discovery...")

        # Core namespaces used by Palantir across different versions of Foundry / AIP
        candidates = [
            "api/v2/aipAgents/agents",
            "api/v2/aipChatbots/chatbots",
            "api/v1/aip-agents/agents",
            "api/v1/aip-chatbots/chatbots",
            "api/v1/aip/chatbots",
            "api/v1/aip/agents"
        ]

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # Baseline payload required for validating execution
        probe_payload = {
            "session": {
                "parameters": {}
            }
        }

        # Let's test each candidate endpoint
        for candidate in candidates:
            for use_enc in [True, False]:
                agent_id_str = self._encode_rid(self.agent_id) if use_enc else self.agent_id
                
                # If checking a v2 endpoint, we must append preview flag to get accurate status codes
                url = f"{self.base_url}/{candidate}/{agent_id_str}/sessions"
                if "v2" in candidate:
                    url += "?preview=true"
                
                try:
                    logger.debug(f"Probing: Path={candidate}, Encoded={use_enc} at URL={url}")
                    response = self._send_request("POST", url, headers=headers, json_data=probe_payload, timeout=5)
                    status = response.status_code
                    logger.info(f"Probe Result for {candidate} (Encoded={use_enc}): HTTP {status}")
                    
                    # 200/201 mean success, 400 with a payload on v2 means it hit the actual business logic layer
                    if status in:
                        logger.info(f"Discovered valid operational endpoint path '{candidate}' with use_encoding={use_enc} (HTTP {status})")
                        self._discovered_api_path = candidate
                        self._use_encoding = use_enc
                        return candidate, use_enc
                        
                    elif status in [400, 401, 403] and "v2" in candidate:
                        logger.info(f"Discovered valid route boundary '{candidate}' with use_encoding={use_enc} (HTTP {status})")
                        self._discovered_api_path = candidate
                        self._use_encoding = use_enc
                        return candidate, use_enc
                except Exception as e:
                    logger.debug(f"Probe error for {candidate} (Encoded={use_enc}): {e}")

        # Default fallback if nothing succeeded
        fallback_path = "api/v2/aipAgents/agents"
        logger.warning(f"⚠️ Endpoint discovery could not identify a valid path. Falling back to default: '{fallback_path}' with encoding=True")
        self._discovered_api_path = fallback_path
        self._use_encoding = True
        return fallback_path, True

    def create_session(self) -> str:
        """
        Creates a new interactive session with the AIP Agent.
        Returns the session ID (or RID).
        """
        if not self.is_configured:
            raise ValueError(
                "Palantir AIP is not configured. PALANTIR_AIP_URL, PALANTIR_AIP_TOKEN, and PALANTIR_AIP_AGENT_ID are required in .env."
            )

        # Auto-discover correct endpoint path and encoding scheme
        api_path, use_encoding = self._discover_endpoint()
        agent_id_str = self._encode_rid(self.agent_id) if use_encoding else self.agent_id

        # 1. Format URL endpoint string target
        url = f"{self.base_url}/{api_path}/{agent_id_str}/sessions"
        if "v2" in api_path:
            url += "?preview=true"

        # 2. Build explicit baseline session parameters configuration mapping payload
        payload = {
            "session": {
                "parameters": {}
            }
        }

        # 3. Complete header configuration mapping definitions
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        logger.info(f"Palantir AIP: Creating session at {url}")
        
        # Execute the HTTP POST request passing down our JSON body
        response = self._send_request("POST", url, headers=headers, json_data=payload)
        
        if response.status_code not in:
            logger.error(f"Failed to create session. Server response: {response.text}")
            response.raise_for_status()

        data = response.json()
        
        # Palantir API typically returns session details within an 'id' or 'rid' field
        session_id = data.get("id") or data.get("rid") or data.get("session", {}).get("id")
        if not session_id:
            logger.warning(f"Session created but couldn't parse ID from payload response structure: {data}")
            # Fallback to returning raw data payload string if map structural fields are absent
            return str(data)
            
        logger.info(f"Successfully generated new live Palantir AIP Session: {session_id}")
        return session_id
