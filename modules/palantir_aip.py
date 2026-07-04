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
        """
        if self.agent_id and "aip-chatbots" in self.agent_id:
            return "api/v1/aip-chatbots/chatbots"
        return "api/v1/aip-agents/agents"

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
            "api/v1/aip-chatbots/chatbots",
            "api/v1/aip-agents/agents",
            "api/v2/aipChatbots/chatbots",
            "api/v2/aipAgents/agents",
            "api/v1/aip/chatbots",
            "api/v1/aip/agents",
            "api/v2/aip/chatbots",
            "api/v2/aip/agents",
            "api/v1/chatbots",
            "api/v1/agents",
            "api/v2/chatbots",
            "api/v2/agents",
            "api/v1/aip-agents",
            "api/v1/aip-chatbots",
            "api/v2/aipAgents",
            "api/v2/aipChatbots"
        ]

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        # Let's test each candidate endpoint
        for candidate in candidates:
            # Test with and without percent-encoded RID
            for use_enc in [True, False]:
                agent_id_str = self._encode_rid(self.agent_id) if use_enc else self.agent_id
                url = f"{self.base_url}/{candidate}/{agent_id_str}/sessions"
                
                try:
                    logger.debug(f"Probing: Path={candidate}, Encoded={use_enc} at URL={url}")
                    # We send a lightweight session POST. Even if it fails with 401/403/400,
                    # if the status is NOT 404, the path is VALID and exists on the server!
                    response = self._send_request("POST", url, headers=headers, json_data={}, timeout=5)
                    status = response.status_code
                    logger.info(f"Probe Result for {candidate} (Encoded={use_enc}): HTTP {status}")
                    
                    # Any response status that is NOT a 404 (or 405 Method Not Allowed/502/503/504 etc.)
                    # indicates that the routing resolved to an actual handler on the backend.
                    # Especially 200, 201, 400, 401, 403.
                    if status in [200, 201, 400, 401, 403]:
                        logger.info(f"Discovered valid endpoint path '{candidate}' with use_encoding={use_enc} (HTTP {status})")
                        self._discovered_api_path = candidate
                        self._use_encoding = use_enc
                        return candidate, use_enc
                except Exception as e:
                    logger.debug(f"Probe error for {candidate} (Encoded={use_enc}): {e}")

        # Default fallback if nothing succeeded
        fallback_path = "api/v1/aip-agents/agents"
        if self.agent_id and "aip-chatbots" in self.agent_id:
            fallback_path = "api/v1/aip-chatbots/chatbots"
        
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
        url = f"{self.base_url}/{api_path}/{agent_id_str}/sessions"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        logger.info(f"Palantir AIP: Creating session at {url}")
        # Foundry API expects a POST request with an empty JSON object
        response = self._send_request("POST", url, headers=headers, json_data={}, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        # The session ID/RID is typically under "id" or "sessionId"
        session_id = data.get("id") or data.get("sessionId")
        if not session_id:
            raise KeyError(f"Response did not contain 'id' or 'sessionId'. Keys present: {list(data.keys())}")
        
        logger.info(f"Palantir AIP: Successfully created live session '{session_id}'")
        return session_id

    def prompt_agent(self, session_id: str, prompt_text: str) -> str:
        """
        Sends a natural language prompt to the agent inside an active session.
        Returns the agent's textual response.
        """
        if not self.is_configured:
            raise ValueError("Palantir AIP is not configured.")

        # Auto-discover correct endpoint path and encoding scheme
        api_path, use_encoding = self._discover_endpoint()

        agent_id_str = self._encode_rid(self.agent_id) if use_encoding else self.agent_id
        session_id_str = self._encode_rid(session_id) if use_encoding else session_id
        url = f"{self.base_url}/{api_path}/{agent_id_str}/sessions/{session_id_str}/prompt"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # Standard AIP Agent Studio prompt payload schema
        payload = {
            "parameterValues": {},
            "prompt": prompt_text
        }

        logger.info(f"Palantir AIP: Prompting session '{session_id}' with text: '{prompt_text}'")
        response = self._send_request("POST", url, headers=headers, json_data=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # The textual response is typically nested under response -> text
        # e.g., { "response": { "text": "I created the request..." } }
        text_response = ""
        if "response" in data:
            res_obj = data["response"]
            if isinstance(res_obj, dict):
                text_response = res_obj.get("text", "")
            else:
                text_response = str(res_obj)
        elif "message" in data:
            text_response = data["message"].get("text", "")
        else:
            # Try common fallback keys
            text_response = data.get("text") or data.get("value") or str(data)

        logger.info("Palantir AIP: Received response from agent successfully.")
        return text_response
