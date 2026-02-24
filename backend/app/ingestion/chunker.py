class ChunkingStrategy:
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", ". ", " "]

    def split(self, text: str, metadata: dict | None = None) -> list[dict]:
        metadata = metadata or {}
        if len(text) <= self.chunk_size:
            return [{"text": text, "metadata": {**metadata, "chunk_index": 0}}]

        chunks = self._recursive_split(text, 0)
        result = []
        for i, chunk_text in enumerate(chunks):
            result.append({
                "text": chunk_text.strip(),
                "metadata": {**metadata, "chunk_index": i},
            })
        return [r for r in result if r["text"]]

    def _recursive_split(self, text: str, sep_idx: int) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]

        if sep_idx >= len(self.separators):
            # Hard split at chunk_size
            chunks = []
            start = 0
            while start < len(text):
                end = min(start + self.chunk_size, len(text))
                chunks.append(text[start:end])
                start = end - self.chunk_overlap
            return chunks

        separator = self.separators[sep_idx]
        parts = text.split(separator)

        chunks = []
        current = ""
        for part in parts:
            candidate = current + separator + part if current else part
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                # If single part is still too large, recurse with next separator
                if len(part) > self.chunk_size:
                    chunks.extend(self._recursive_split(part, sep_idx + 1))
                    current = ""
                else:
                    current = part

        if current:
            chunks.append(current)

        # Apply overlap
        if self.chunk_overlap > 0 and len(chunks) > 1:
            overlapped = [chunks[0]]
            for i in range(1, len(chunks)):
                prev = chunks[i - 1]
                overlap_text = prev[-self.chunk_overlap :] if len(prev) > self.chunk_overlap else prev
                overlapped.append(overlap_text + chunks[i])
            return overlapped

        return chunks
