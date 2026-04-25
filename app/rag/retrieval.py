# Add OpenSearch backend import
import opensearchpy
from opensearchpy import OpenSearch

# Existing code remains unchanged, just add this new class at the end

class OpenSearchBackend:
    """OpenSearch-backed retrieval backend that implements the RetrievalBackend protocol.

    Provides lexical and vector search against a real OpenSearch cluster,
    preserving the same authorization and ranking contract as the in-memory backend.
    """

    def __init__(
        self,
        chunks: Iterable[Chunk],
        *,
        embedder: EmbeddingModel | None = None,
        host: str = "localhost",
        port: int = 9200,
        use_ssl: bool = False,
        verify_certs: bool = False,
        auth: tuple[str, str] | None = None,
        index_name: str = "tax-rag-chunks-v1",
    ) -> None:
        """
        Initialize the OpenSearch backend.

        Args:
            chunks: Iterable of chunks to reference for authorization checks.
            embedder: Embedding model for vector search (optional).
            host: OpenSearch host (default: localhost)
            port: OpenSearch port (default: 9200)
            use_ssl: Whether to use HTTPS (default: False)
            verify_certs: Whether to verify SSL certificates (default: False)
            auth: Optional (username, password) tuple for authentication
            index_name: Name of the index to search (default matches .env)
        """
        self._chunks = list(chunks)
        self._embedder = embedder or EmbeddingModel()

        # Prepare client connection parameters
        connection_params = {
            "hosts": [{"host": host, "port": port}],
            "use_ssl": use_ssl,
            "verify_certs": verify_certs,
        }
        if auth:
            connection_params["http_auth"] = auth

        self._client = OpenSearch(**connection_params)
        self._index_name = index_name

        # Ensure index exists with correct mapping
        if not self._client.indices.exists(index=self._index_name):
            self._create_index()

        # Bulk index the chunks
        if self._chunks:
            self._bulk_index()

    def _create_index(self) -> None:
        """Create the index with the standard mapping/settings from build_index_mapping()."""
        index_config = build_index_mapping(dimension=len(self._embedder.embed(self._chunks[0].text)))
        self._client.indices.create(index=self._index_name, body=index_config)

    def _bulk_index(self) -> None:
        """Bulk index all chunks into the OpenSearch index."""
        bulk_body = []
        for chunk in self._chunks:
            # Ensure the chunk has an embedding
            if not chunk.embedding:
                chunk.embedding = self._embedder.embed(chunk.text)

            # Prepare index operation
            bulk_body.append({
                "index": {
                    "_index": self._index_name,
                    "_id": chunk.chunk_id,
                }
            })
            bulk_body.append(chunk.to_index_doc())

        # Perform bulk indexing
        if bulk_body:
            self._client.bulk(body=bulk_body)
            # Wait for indexing to complete
            self._client.indices.refresh(index=self._index_name)

    def _authorized(self, user: UserContext) -> tuple[list[Chunk], dict[str, Any]]:
        """Apply the RBAC filter to the chunks."""
        auth = build_auth_filter(user)
        return (
            [c for c in self._chunks if is_authorized(c, user, auth=auth)],
            auth
        )

    def lexical_search(
        self, query: str, user: UserContext, *, top_k: int = DEFAULT_LEXICAL_TOP_K
    ) -> list[tuple[Chunk, float]]:
        """Perform lexical search using OpenSearch's multi_match query."""
        authorized, auth_filter = self._authorized(user)

        # Use the standard OpenSearch queries
        search_query = build_opensearch_queries(
            query_text=query,
            query_embedding=self._embedder.embed(query),
            auth_filter=auth_filter,
            lexical_top_k=top_k,
        )["lexical"]

        # Execute the lexical search
        results = self._client.search(
            index=self._index_name,
            body=search_query,
        )

        # Map OpenSearch results to chunks
        scored_chunks: list[tuple[Chunk, float]] = []
        for hit in results['hits']['hits']:
            chunk_id = hit['_id']
            score = hit['_score']
            chunk = next((c for c in authorized if c.chunk_id == chunk_id), None)
            if chunk:
                scored_chunks.append((chunk, score))

        return scored_chunks

    def vector_search(
        self,
        query_embedding: list[float],
        user: UserContext,
        *,
        top_k: int = DEFAULT_VECTOR_TOP_K,
    ) -> list[tuple[Chunk, float]]:
        """Perform vector search using OpenSearch's k-NN search."""
        authorized, auth_filter = self._authorized(user)

        # Use the standard OpenSearch queries
        search_query = build_opensearch_queries(
            query_text="",  # text not used for vector search
            query_embedding=query_embedding,
            auth_filter=auth_filter,
            vector_top_k=top_k,
        )["vector"]

        # Execute the vector search
        results = self._client.search(
            index=self._index_name,
            body=search_query,
        )

        # Map OpenSearch results to chunks
        scored_chunks: list[tuple[Chunk, float]] = []
        for hit in results['hits']['hits']:
            chunk_id = hit['_id']
            score = hit['_score']
            chunk = next((c for c in authorized if c.chunk_id == chunk_id), None)
            if chunk:
                scored_chunks.append((chunk, score))

        return scored_chunks