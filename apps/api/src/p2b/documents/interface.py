"""Public interface of the documents module. Other modules import only this file.

The staff functions skip project membership: call them only from routes that require an
operations role (API 18)."""

from p2b.documents.service import (
    FileFacts,
    FileRef,
    FileSummary,
    complete_personal_upload,
    complete_project_file_upload,
    concept_files,
    concept_image_url,
    create_personal_upload,
    create_project_file_upload,
    file_facts,
    file_purpose,
    files_for_staff,
    personal_file_url,
    personal_files,
    project_file_url,
    public_image_urls,
    requirement_files,
    shared_file_url,
    staff_download_url,
    store_generated_file,
    store_staff_upload,
)

__all__ = [
    "FileFacts",
    "FileRef",
    "FileSummary",
    "complete_personal_upload",
    "complete_project_file_upload",
    "concept_files",
    "concept_image_url",
    "create_personal_upload",
    "create_project_file_upload",
    "file_facts",
    "file_purpose",
    "files_for_staff",
    "personal_file_url",
    "personal_files",
    "project_file_url",
    "public_image_urls",
    "requirement_files",
    "shared_file_url",
    "staff_download_url",
    "store_generated_file",
    "store_staff_upload",
]
