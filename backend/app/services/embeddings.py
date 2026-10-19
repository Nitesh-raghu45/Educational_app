import threading


class MiniLMEmbedder:
    """all-MiniLM-L6-v2 run locally on CPU via ONNX Runtime (fastembed): 384-dim, L2-normalised.

    Produces the same vectors as sentence-transformers but without PyTorch, which keeps the
    Docker image and memory use small.
    """

    def __init__(self, model_name: str, cache_dir: str | None = None, batch_size: int = 8):
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self):
        with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding

                self._model = TextEmbedding(self._model_name, cache_dir=self._cache_dir)
            return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._get_model().embed(texts, batch_size=self._batch_size)]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
