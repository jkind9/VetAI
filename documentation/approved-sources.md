# Approved sources for evidence search

This is the reviewed source policy for the technical demo. “Approved” means the organisation and
domain may be used by the retrieval stage; it is not a blanket clinical endorsement of every page
or proof that generated output is medically correct.

| Organisation | Allowed domain | Why it is included |
| --- | --- | --- |
| Cornell University College of Veterinary Medicine | `vet.cornell.edu` | Veterinary teaching-hospital and university guidance |
| Royal Veterinary College | `rvc.ac.uk` | UK veterinary university and clinical guidance |
| MSD Veterinary Manual | `msdvetmanual.com` | Professionally reviewed veterinary reference material |
| ASPCA | `aspca.org` | Emergency and poison-control guidance |
| PDSA | `pdsa.org.uk` | UK veterinary charity with public pet-health guidance |
| Blue Cross | `bluecross.org.uk` | UK animal-welfare charity with public pet-care guidance |

The machine-readable copy is `config/approved_sources.toml`. Changes to either list must update the
other in the same change.

## Enforcement rules

1. The allowlist limits retrieval up front: generated queries are scoped to the approved domains
   before the external search call.
2. Domain text inside a query is still not trusted as enforcement; search providers can ignore or
   imperfectly honour operators.
3. Every result must use HTTPS.
4. A result host must equal an approved domain or be its subdomain. Substring matches do not count:
   `aspca.org.example.com` is not approved.
5. Redirect targets are checked by the same rule before content is accepted.
6. Duplicate canonical URLs are removed.
7. Page and aggregate text sizes are bounded before evidence reaches the model.
8. Scripts, forms, and navigation are not evidence.
9. Retrieved text is treated as untrusted data. Instructions found in a page cannot alter the
   system prompt, workflow order, emergency policy, or source policy.
10. At least one usable approved item is required. Otherwise no synthesis is produced.

## Search and privacy

The search provider receives only short generated queries, not the transcript. Queries are checked
for URLs and common contact-data patterns before leaving the local process. This is data
minimisation, not guaranteed anonymisation. Search services can log queries, and destination sites
can observe requested URLs and the caller's public IP.

No query, result, or page content is persisted in this milestone. Future MLflow work must decide
what can be logged safely before recording any of them.

## Editorial rules for synthesis

- Sources support broad informational context; they do not turn the demo into a diagnostic tool.
- Possible areas are non-ranked and phrased as matters a veterinarian may consider.
- Treatment instructions, doses, specific test recommendations, reassurance, and statements that
  veterinary care is unnecessary remain prohibited.
- The model cites source IDs only. The workflow resolves IDs to titles and URLs.
- A claim with no valid retrieved source ID is rejected rather than shown without a citation.
