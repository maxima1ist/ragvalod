from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class JobState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    JOB_STATE_UNSPECIFIED: _ClassVar[JobState]
    JOB_STATE_PENDING: _ClassVar[JobState]
    JOB_STATE_RUNNING: _ClassVar[JobState]
    JOB_STATE_SUCCEEDED: _ClassVar[JobState]
    JOB_STATE_FAILED: _ClassVar[JobState]
    JOB_STATE_PARTIAL: _ClassVar[JobState]

class SourceJobState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SOURCE_JOB_STATE_UNSPECIFIED: _ClassVar[SourceJobState]
    SOURCE_JOB_STATE_PENDING: _ClassVar[SourceJobState]
    SOURCE_JOB_STATE_RUNNING: _ClassVar[SourceJobState]
    SOURCE_JOB_STATE_SUCCEEDED: _ClassVar[SourceJobState]
    SOURCE_JOB_STATE_FAILED: _ClassVar[SourceJobState]
    SOURCE_JOB_STATE_SKIPPED: _ClassVar[SourceJobState]
JOB_STATE_UNSPECIFIED: JobState
JOB_STATE_PENDING: JobState
JOB_STATE_RUNNING: JobState
JOB_STATE_SUCCEEDED: JobState
JOB_STATE_FAILED: JobState
JOB_STATE_PARTIAL: JobState
SOURCE_JOB_STATE_UNSPECIFIED: SourceJobState
SOURCE_JOB_STATE_PENDING: SourceJobState
SOURCE_JOB_STATE_RUNNING: SourceJobState
SOURCE_JOB_STATE_SUCCEEDED: SourceJobState
SOURCE_JOB_STATE_FAILED: SourceJobState
SOURCE_JOB_STATE_SKIPPED: SourceJobState

class SourceSpec(_message.Message):
    __slots__ = ("name", "credentials", "options")
    class CredentialsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    class OptionsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    NAME_FIELD_NUMBER: _ClassVar[int]
    CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
    OPTIONS_FIELD_NUMBER: _ClassVar[int]
    name: str
    credentials: _containers.ScalarMap[str, str]
    options: _containers.ScalarMap[str, str]
    def __init__(self, name: _Optional[str] = ..., credentials: _Optional[_Mapping[str, str]] = ..., options: _Optional[_Mapping[str, str]] = ...) -> None: ...

class TriggerIngestRequest(_message.Message):
    __slots__ = ("sources", "all_with_credentials")
    SOURCES_FIELD_NUMBER: _ClassVar[int]
    ALL_WITH_CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
    sources: _containers.RepeatedCompositeFieldContainer[SourceSpec]
    all_with_credentials: bool
    def __init__(self, sources: _Optional[_Iterable[_Union[SourceSpec, _Mapping]]] = ..., all_with_credentials: _Optional[bool] = ...) -> None: ...

class TriggerIngestResponse(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class SourceJobStatus(_message.Message):
    __slots__ = ("source_name", "state", "message", "documents_processed", "chunks_written", "error")
    SOURCE_NAME_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DOCUMENTS_PROCESSED_FIELD_NUMBER: _ClassVar[int]
    CHUNKS_WRITTEN_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    source_name: str
    state: SourceJobState
    message: str
    documents_processed: int
    chunks_written: int
    error: str
    def __init__(self, source_name: _Optional[str] = ..., state: _Optional[_Union[SourceJobState, str]] = ..., message: _Optional[str] = ..., documents_processed: _Optional[int] = ..., chunks_written: _Optional[int] = ..., error: _Optional[str] = ...) -> None: ...

class GetJobStatusRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...

class GetJobStatusResponse(_message.Message):
    __slots__ = ("job_id", "state", "message", "sources", "started_at", "finished_at")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SOURCES_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    state: JobState
    message: str
    sources: _containers.RepeatedCompositeFieldContainer[SourceJobStatus]
    started_at: str
    finished_at: str
    def __init__(self, job_id: _Optional[str] = ..., state: _Optional[_Union[JobState, str]] = ..., message: _Optional[str] = ..., sources: _Optional[_Iterable[_Union[SourceJobStatus, _Mapping]]] = ..., started_at: _Optional[str] = ..., finished_at: _Optional[str] = ...) -> None: ...

class ListSourcesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SourceInfo(_message.Message):
    __slots__ = ("name", "description", "requires_credentials")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    REQUIRES_CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    requires_credentials: bool
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., requires_credentials: _Optional[bool] = ...) -> None: ...

class ListSourcesResponse(_message.Message):
    __slots__ = ("sources",)
    SOURCES_FIELD_NUMBER: _ClassVar[int]
    sources: _containers.RepeatedCompositeFieldContainer[SourceInfo]
    def __init__(self, sources: _Optional[_Iterable[_Union[SourceInfo, _Mapping]]] = ...) -> None: ...

class UpsertScheduleRequest(_message.Message):
    __slots__ = ("schedule_id", "name", "cron", "enabled", "sources", "all_with_credentials")
    SCHEDULE_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    CRON_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    SOURCES_FIELD_NUMBER: _ClassVar[int]
    ALL_WITH_CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
    schedule_id: str
    name: str
    cron: str
    enabled: bool
    sources: _containers.RepeatedCompositeFieldContainer[SourceSpec]
    all_with_credentials: bool
    def __init__(self, schedule_id: _Optional[str] = ..., name: _Optional[str] = ..., cron: _Optional[str] = ..., enabled: _Optional[bool] = ..., sources: _Optional[_Iterable[_Union[SourceSpec, _Mapping]]] = ..., all_with_credentials: _Optional[bool] = ...) -> None: ...

class UpsertScheduleResponse(_message.Message):
    __slots__ = ("schedule_id",)
    SCHEDULE_ID_FIELD_NUMBER: _ClassVar[int]
    schedule_id: str
    def __init__(self, schedule_id: _Optional[str] = ...) -> None: ...

class ListSchedulesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ScheduleInfo(_message.Message):
    __slots__ = ("schedule_id", "name", "cron", "enabled", "source_names", "all_with_credentials", "last_run_at", "last_job_id", "created_at", "updated_at")
    SCHEDULE_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    CRON_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    SOURCE_NAMES_FIELD_NUMBER: _ClassVar[int]
    ALL_WITH_CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
    LAST_RUN_AT_FIELD_NUMBER: _ClassVar[int]
    LAST_JOB_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    schedule_id: str
    name: str
    cron: str
    enabled: bool
    source_names: _containers.RepeatedScalarFieldContainer[str]
    all_with_credentials: bool
    last_run_at: str
    last_job_id: str
    created_at: str
    updated_at: str
    def __init__(self, schedule_id: _Optional[str] = ..., name: _Optional[str] = ..., cron: _Optional[str] = ..., enabled: _Optional[bool] = ..., source_names: _Optional[_Iterable[str]] = ..., all_with_credentials: _Optional[bool] = ..., last_run_at: _Optional[str] = ..., last_job_id: _Optional[str] = ..., created_at: _Optional[str] = ..., updated_at: _Optional[str] = ...) -> None: ...

class ListSchedulesResponse(_message.Message):
    __slots__ = ("schedules",)
    SCHEDULES_FIELD_NUMBER: _ClassVar[int]
    schedules: _containers.RepeatedCompositeFieldContainer[ScheduleInfo]
    def __init__(self, schedules: _Optional[_Iterable[_Union[ScheduleInfo, _Mapping]]] = ...) -> None: ...

class DeleteScheduleRequest(_message.Message):
    __slots__ = ("schedule_id",)
    SCHEDULE_ID_FIELD_NUMBER: _ClassVar[int]
    schedule_id: str
    def __init__(self, schedule_id: _Optional[str] = ...) -> None: ...

class DeleteScheduleResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RunScheduleRequest(_message.Message):
    __slots__ = ("schedule_id",)
    SCHEDULE_ID_FIELD_NUMBER: _ClassVar[int]
    schedule_id: str
    def __init__(self, schedule_id: _Optional[str] = ...) -> None: ...

class RunScheduleResponse(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...
