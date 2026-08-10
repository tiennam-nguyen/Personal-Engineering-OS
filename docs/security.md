# Security limits

Backup verification rejects absolute, traversal, duplicate, forbidden, unlisted, and symlink paths;
payload and object bytes are independently hashed. Hardening code invokes no shell or network client.
Expected CLI failures suppress tracebacks unless `PEOS_DEBUG=1`.

Environment secret values are not expanded into configuration or backups, and doctor checks
high-confidence control-plane sentinels. PEOS cannot prove user-authored content is non-confidential:
backups contain it, are uncompressed and unencrypted, and must be protected like the workspace.
Hashes detect corruption but not a hostile owner who can rewrite content and hashes. v1 has no remote
backup, credential manager, sandbox, multi-user authorization, or encrypted backup format.
