# Approved sources

The web search may only use pages from these six organisations. "Approved" means the site may be
searched and read. It doesn't mean every page on it has been checked, or that the summary built
from it is medically correct.

| Organisation | Website | Why it is included |
| --- | --- | --- |
| Cornell University College of Veterinary Medicine | `vet.cornell.edu` | A veterinary university and teaching hospital |
| Royal Veterinary College | `rvc.ac.uk` | A UK veterinary university |
| MSD Veterinary Manual | `msdvetmanual.com` | A professionally reviewed veterinary reference |
| ASPCA | `aspca.org` | Emergency and poison-control guidance |
| PDSA | `pdsa.org.uk` | A UK veterinary charity with pet-health guidance for owners |
| Blue Cross | `bluecross.org.uk` | A UK animal-welfare charity with pet-care guidance |

The list the code reads is [`config/approved_sources.toml`](../config/approved_sources.toml).
Change both together. Adding a site changes which outside text can reach the summary, so it
deserves the same review as a code change.

## How the list is enforced

1. Each search query is limited to these sites with a `site:` filter. The search engine may not
   honour it exactly, so the results are checked again.
2. Every result must use HTTPS.
3. Its host must be one of the sites or a real subdomain of one. `aspca.org.example.com` does not
   count as `aspca.org`.
4. Every redirect is checked the same way before it is followed.
5. Duplicate pages are dropped.
6. Page size and the text kept from each page are limited (500,000 bytes, 4,000 characters).
7. Scripts, styles, navigation and forms are removed from the page text.
8. Page text is treated as untrusted: instructions written in a page can't change the app's rules.

## If no approved page is found

If the search service fails or no page passes these checks, the summary still goes ahead, written
from widely accepted general vet guidance. It then has no sources, and the owner sees a notice that
the source search didn't work. The model is never allowed to invent a source or a link: it cites
pages by ID, and the app builds the links only from pages it actually read.

## Privacy

The search service only receives the short generated queries, never the chat. Before a query is
sent, it is checked for web addresses, email addresses and phone numbers. That reduces what leaves
the machine but doesn't make it anonymous: the search service can log queries, and the approved
sites can see which pages were requested and the machine's public IP address.

Each turn's MLflow record holds the generated queries and the page text sent to the model. It stays
on this machine in `mlflow.db`, which git and Docker ignore. Delete that file to remove it.

## Rules for the summary

- Sources give general background. They don't turn the demo into a diagnosis tool.
- Points for the vet are broad, not ranked, and phrased as things a vet may consider.
- Suggested actions stick to watching a sign, recording an episode, or simple low-risk steps. No
  medicines, doses, invasive steps, unproven remedies, forcing food or water, specific tests,
  reassurance, or advice to put off seeing a vet.
- When pages were found, every item cites at least one of them.

## Checking it

The ordinary tests check the site filter, the host checks, HTTPS, redirects, duplicates, partial
download failures, and what happens when nothing usable is found, all without a network connection.
A separate opt-in check downloads one real page (the MSD Veterinary Manual's dog-or-cat emergency
page) through the real code and looks for "heat stroke", "rapid panting" and "water":

```powershell
$env:VETAI_RUN_LIVE_SEARCH_SMOKE = "1"
uv run pytest tests/test_approved_source_smoke.py -v
```

It isn't part of the ordinary tests, because the outside website can change or go down.
