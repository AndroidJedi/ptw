---
name: landing-template-restore
description: Restore a private PTW Landing JSON backup onto the current matching Landing template after the owner starts Restore from JSON.
---

# Landing template restore

Use only after the owner selects **Restore from JSON** in the private Landing
editor. The backup is Project content, not a reusable template or training
reference. Check the backup schema, Project ID, whole-document digest, each
file digest, approved-version records, and source Post version before creating
a replacement. Never copy a contact, claim or customer quote from a different
Project.

The server performs the copy. Historical App Showcase v1/v2 maps to the current
v3 definition; Project landing maps to its current definition. Preserve copy,
selected artwork and image history. Seed the v3 eyebrow and three-bullet
controls deterministically from the saved page. A repeated request ID for the
same backup returns the same replacement draft; a different backup conflicts.

The replacement is private and unapproved. Keep the original Landing, approved
versions, publication events and public URL intact. Report missing or corrupt
files and unsupported template references without a partial publication or
provider call. The owner reviews the new draft and separately approves and
publishes it if desired.
