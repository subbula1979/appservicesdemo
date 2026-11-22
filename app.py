import logging
import os

from flask import Flask, jsonify, render_template, request, session
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("Set the FLASK_SECRET_KEY App Service application setting.")

ENDPOINT = os.environ.get(
    "AZURE_AI_PROJECT_ENDPOINT",
    "https://msftfoundry20290808.services.ai.azure.com/api/projects/AI-project1",
)
AGENT_NAME = os.environ.get("AZURE_AI_AGENT_NAME", "luna-agent")
AGENT_VERSION = os.environ.get("AZURE_AI_AGENT_VERSION", "2")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))


@app.get("/")
def home():
    return render_template("index.html")


@app.post("/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = payload.get("message", "")
    if not isinstance(message, str) or not message.strip():
        return jsonify(error="Please enter a message."), 400
    if len(message) > 10000:
        return jsonify(error="Message is too long (maximum 10,000 characters)."), 400

    try:
        with (
            DefaultAzureCredential() as credential,
            AIProjectClient(endpoint=ENDPOINT, credential=credential) as project_client,
        ):
            openai_client = project_client.get_openai_client()
            conversation_id = session.get("conversation_id")
            if not conversation_id:
                conversation = openai_client.conversations.create()
                conversation_id = conversation.id
                session["conversation_id"] = conversation_id

            response = openai_client.responses.create(
                conversation=conversation_id,
                input=[{"role": "user", "content": message.strip()}],
                extra_body={
                    "agent_reference": {
                        "name": AGENT_NAME,
                        "type": "agent_reference",
                        "version": AGENT_VERSION,
                    }
                },
            )
            return jsonify(reply=response.output_text)
    except Exception:
        app.logger.exception("Foundry agent request failed")
        return jsonify(error=(
            "The Microsoft Foundry request failed. Check App Service logs, "
            "project endpoint, agent name/version, SDK compatibility, and "
            "managed identity permissions."
        )), 502


@app.post("/new-conversation")
def new_conversation():
    session.pop("conversation_id", None)
    return jsonify(status="ok")


@app.get("/health")
def health():
    return jsonify(status="healthy")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
