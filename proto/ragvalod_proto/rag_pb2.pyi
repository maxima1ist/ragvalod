from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RetrievalParams(_message.Message):
    __slots__ = ("top_k", "rerank_top_n")
    TOP_K_FIELD_NUMBER: _ClassVar[int]
    RERANK_TOP_N_FIELD_NUMBER: _ClassVar[int]
    top_k: int
    rerank_top_n: int
    def __init__(self, top_k: _Optional[int] = ..., rerank_top_n: _Optional[int] = ...) -> None: ...

class GenerationParams(_message.Message):
    __slots__ = ("temperature", "max_tokens")
    TEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    MAX_TOKENS_FIELD_NUMBER: _ClassVar[int]
    temperature: float
    max_tokens: int
    def __init__(self, temperature: _Optional[float] = ..., max_tokens: _Optional[int] = ...) -> None: ...

class GenerateAnswerRequest(_message.Message):
    __slots__ = ("query", "retrieval", "generation")
    QUERY_FIELD_NUMBER: _ClassVar[int]
    RETRIEVAL_FIELD_NUMBER: _ClassVar[int]
    GENERATION_FIELD_NUMBER: _ClassVar[int]
    query: str
    retrieval: RetrievalParams
    generation: GenerationParams
    def __init__(self, query: _Optional[str] = ..., retrieval: _Optional[_Union[RetrievalParams, _Mapping]] = ..., generation: _Optional[_Union[GenerationParams, _Mapping]] = ...) -> None: ...

class UsedChunk(_message.Message):
    __slots__ = ("id", "text", "source", "title", "section_path", "score")
    ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    SECTION_PATH_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    id: str
    text: str
    source: str
    title: str
    section_path: str
    score: float
    def __init__(self, id: _Optional[str] = ..., text: _Optional[str] = ..., source: _Optional[str] = ..., title: _Optional[str] = ..., section_path: _Optional[str] = ..., score: _Optional[float] = ...) -> None: ...

class GenerateAnswerResponse(_message.Message):
    __slots__ = ("answer", "used_chunks")
    ANSWER_FIELD_NUMBER: _ClassVar[int]
    USED_CHUNKS_FIELD_NUMBER: _ClassVar[int]
    answer: str
    used_chunks: _containers.RepeatedCompositeFieldContainer[UsedChunk]
    def __init__(self, answer: _Optional[str] = ..., used_chunks: _Optional[_Iterable[_Union[UsedChunk, _Mapping]]] = ...) -> None: ...

class SourceMarker(_message.Message):
    __slots__ = ("source_name", "ingested_at", "document_count")
    SOURCE_NAME_FIELD_NUMBER: _ClassVar[int]
    INGESTED_AT_FIELD_NUMBER: _ClassVar[int]
    DOCUMENT_COUNT_FIELD_NUMBER: _ClassVar[int]
    source_name: str
    ingested_at: str
    document_count: int
    def __init__(self, source_name: _Optional[str] = ..., ingested_at: _Optional[str] = ..., document_count: _Optional[int] = ...) -> None: ...

class GetDataStatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetDataStatusResponse(_message.Message):
    __slots__ = ("data_initialized", "sources")
    DATA_INITIALIZED_FIELD_NUMBER: _ClassVar[int]
    SOURCES_FIELD_NUMBER: _ClassVar[int]
    data_initialized: bool
    sources: _containers.RepeatedCompositeFieldContainer[SourceMarker]
    def __init__(self, data_initialized: _Optional[bool] = ..., sources: _Optional[_Iterable[_Union[SourceMarker, _Mapping]]] = ...) -> None: ...
