# ADR-011: File architecture: server-generated keys, immutable objects, processing pipeline, short presigned URLs, share tokens

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03) |
| Deciders | Sakha (proposal), Chirag (baseline rules: never trust client paths, never expose private objects) |
| Related | ADR-006, DATA_ARCHITECTURE.md section 6, SECURITY_ARCHITECTURE.md section 8, INTEGRATION_ARCHITECTURE.md section 7 |

## Context

Files carry the product's evidence: drawings, photos that must not be backdated, inspection evidence, quotes, identity documents, rendered Build Plans and build records that outlive the project and transfer to new owners. Rules from the sources: private storage, signed URLs, virus scanning, content-type and size limits (BR-030), retention per document type, never hard-delete transactional records (BR-141), the auditor never sees supplier or brand (BR-122), build records readable without an account through a share link (S05 P8).

## Decision

- Keys are server-generated: `{env}/{purpose}/{yyyy}/{mm}/{file_uuid}`; the client never supplies a path or a name that reaches storage; original names are metadata.
- Objects are immutable; a replacement is a new file row and key; references point at file ids.
- Upload: `POST /uploads` validates purpose, context rights, declared type and size, returns a presigned PUT (15 minutes); `complete` triggers the pipeline (sniff with libmagic, ClamAV scan, image re-encode stripping EXIF, PDF checks, variants) before the file is `AVAILABLE`; failures quarantine.
- Download: presigned GET from the API after authorisation on the file's context; 15 minutes (5 for identity and financial documents); `Content-Disposition: attachment`; every private document open logged.
- Sharing: hashed, single-purpose, expiring, revocable share tokens for documents and build records; the public bucket only for approved listing images.
- Rendered documents: HTML templates to PDF in the worker, stored as immutable objects with a `document_versions` row and a hash; the PDF and the web render come from the same data (S05 P3).
- Retention classes per purpose (DATA_ARCHITECTURE.md section 14); deletions only by the prune job on narrow paths (pending uploads, quarantine, expired drafts).

## Why

- Server keys and immutability close path traversal, overwrite and "replace the evidence" attacks by construction.
- A pipeline before availability means nothing unscanned is ever served.
- Presigned URLs keep file bytes off the VPS and let R2 serve them at the edge.
- Logged opens satisfy the audit expectations for sensitive documents.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Streaming files through the API | Simple authorisation, but the VPS becomes the bottleneck and the cost of every byte |
| Public bucket with unguessable URLs | Unguessable is not private; links leak; no expiry; no audit |
| Client-chosen keys with validation | One missed check is a traversal; generation is simpler than validation |
| External scanning APIs | Send private documents to a third party; ClamAV on the host avoids it |

## Consequences

- About 1.3 GB of RAM for ClamAV on the VPS (CLOUD_AND_HOSTING_ARCHITECTURE.md).
- Up to a minute between upload and availability; the UI shows "processing".
- Presigned URLs must be requested fresh; the client code handles expiry.

## Migration path

Provider-neutral keys; bucket sync; the pipeline runs anywhere the worker runs.
