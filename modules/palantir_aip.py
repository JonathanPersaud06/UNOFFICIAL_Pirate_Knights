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

        # Simple verification
        if not self.base_url:
            logger.warning("PALANTIR_AIP_URL is not set. Palantir AIP integration will run in simulated mode.")
        if not self.token:
            logger.warning("PALANTIR_AIP_TOKEN is not set. Palantir AIP integration will run in simulated mode.")
        if not self.agent_id:
            logger.warning("PALANTIR_AIP_AGENT_ID is not set. Palantir AIP integration will run in simulated mode.")

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

    def create_session(self) -> str:
        """
        Creates a new interactive session with the AIP Agent.
        Returns the session ID (or RID).
        """
        if not self.is_configured:
            logger.info("Palantir AIP: Running in SIMULATION MODE. Creating mock session ID.")
            return "mock-session-id-12345"

        encoded_agent_id = self._encode_rid(self.agent_id)
        url = f"{self.base_url}/{self.api_path}/{encoded_agent_id}/sessions"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        try:
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

        except Exception as e:
            logger.error(f"Palantir AIP Error creating session: {e}. Falling back to simulation mode.")
            return "mock-session-id-fallback"

    def prompt_agent(self, session_id: str, prompt_text: str) -> str:
        """
        Sends a natural language prompt to the agent inside an active session.
        Returns the agent's textual response.
        """
        if not self.is_configured or session_id.startswith("mock-"):
            return self._get_simulated_response(prompt_text)

        encoded_agent_id = self._encode_rid(self.agent_id)
        encoded_session_id = self._encode_rid(session_id)
        url = f"{self.base_url}/{self.api_path}/{encoded_agent_id}/sessions/{encoded_session_id}/prompt"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # Standard AIP Agent Studio prompt payload schema
        payload = {
            "parameterValues": {},
            "prompt": prompt_text
        }

        try:
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

        except Exception as e:
            logger.error(f"Palantir AIP Error prompting agent: {e}")
            return f"⚠️ **Palantir AIP Connection Error:** Could not contact the agent orchestrator ({e}). Running automatic fallback evaluation..."

    def _get_simulated_response(self, prompt_text: str) -> str:
        """
        Provides highly accurate mock responses that simulate how your Fairy_Bit_AIP_Orchestrator
        interprets the user's prompt against your Ontology.
        """
        p_lower = prompt_text.lower()
        
        # Simulate agent detecting media titles
        media_name = "Selected Media"
        for word in ["bleach", "shrek", "naruto", "one piece", "demon slayer", "cyberpunk"]:
            if word in p_lower:
                media_name = word.title()
                break

        import shutil
        total, used, free = shutil.disk_usage("/")
        free_gb = free // (2**30)

        # Build simulated AIP Agent response demonstrating Ontology awareness
        sim_response = (
            f"🔮 **[SIMULATED AIP ORCHESTRATOR RESPONSE]**\n"
            f"I have received your request for: `{media_name}`.\n\n"
            f"**Ontology Analysis:**\n"
            f"1. Checked object type `Disk Space`: Detects **{free_gb} GB free** on disk (Status: **Sufficient**).\n"
            f"2. Initialized Action Type `Create Media Request` for **{media_name}**.\n\n"
            f"*I am dispatching this request to the High King's Court for visual file-source selection and download confirmation.*"
        )
        return sim_response
