# Disaster recovery

Private-beta targets are RPO 24 hours and RTO 4 hours after a verified backup exists; these are
targets, not high-availability guarantees. Container loss is recovered from immutable images and
configuration templates. Worker/scheduler crashes recover through expired leases. After host reboot,
Compose restart policies start API, worker, scheduler, and web after readiness. Database or object
loss requires a verified backup restore. Provider outage opens a circuit and defers work. A bad
deployment rolls back the image and explicitly restores schema/data only when required.
