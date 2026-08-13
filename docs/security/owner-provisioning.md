# Owner authentication recovery

Production uses Supabase only for identity. Canonical application data remains in the
deployment PostgreSQL database. Creating a Supabase Auth user does not grant workspace access.

Run the provisioning command inside the API deployment environment, where
`MIL_DATABASE_URL` is already supplied securely. The command defaults to a dry run:

```bash
python scripts/provision_owner.py \
  --email owner@example.com \
  --subject SUPABASE_USER_UUID \
  --workspace-slug existing-workspace-slug \
  --profile-id EXISTING_APPLICATION_PROFILE_UUID
```

Review the safe summary, take a database backup, then repeat with `--apply`. The command refuses
ambiguous profiles or workspaces, does not create a workspace, never downgrades an owner, and
records `auth.owner_provisioned` in the audit log. Obtain the subject in the Supabase dashboard;
do not place passwords, tokens, keys, or database URLs on the command line.
