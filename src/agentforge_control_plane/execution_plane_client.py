import uuid

import httpx

from agentforge_control_plane.config import get_settings


class ExecutionPlaneError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"execution-plane returned {status_code}: {detail}")


class ExecutionPlaneClient:
    """Thin httpx client for the execution-plane's document ingest API.

    Per ADR-0007, the `documents` table on this side holds only metadata --
    the actual chunking/embedding/indexing happens on the execution plane
    against OpenSearch. Control-plane orchestrates (owns the metadata row,
    decides when ingestion happens); execution-plane executes (owns the
    actual indexing I/O), mirroring the reverse control_plane_client.py on
    the execution-platform side.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = httpx.Client(
            base_url=settings.execution_plane_url,
            headers={"Authorization": f"Bearer {settings.dev_bearer_token}"},
            timeout=30.0,
        )

    def close(self) -> None:
        self._client.close()

    def ingest_document(
        self,
        knowledge_base_id: uuid.UUID,
        document_id: uuid.UUID,
        source_uri: str,
        title: str | None,
        content: str,
    ) -> dict:
        resp = self._client.post(
            f"/knowledge-bases/{knowledge_base_id}/documents/{document_id}/ingest",
            json={"source_uri": source_uri, "title": title, "content": content},
        )
        if resp.status_code != 200:
            raise ExecutionPlaneError(resp.status_code, resp.text)
        return resp.json()
