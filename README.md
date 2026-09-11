# OpenSSF Criticality Tracker

Daily [OpenSSF Criticality Scores](https://github.com/ossf/criticality_score) for all repositories accessible to my GitHub account, including owned, collaborator, and organization repositories. Scores range from **0 to 1** and estimate project importance to the open-source ecosystem.

Updated: **Awaiting first workflow run** · **0/0** repositories scored.

| Repository | Criticality score | Status |
| --- | ---: | --- |

<details>
<summary>How this tracker works</summary>

- Runs on every push, manually, and daily at midnight in `America/New_York` (GitHub may delay scheduled runs).
- Uses the official OpenSSF Criticality Score **v2.0.4** default scoring configuration. Google Cloud/deps.dev collection is disabled; the default score uses GitHub signals.
- Discovers all repositories returned by GitHub’s authenticated `/user/repos` API, including private, archived, and forked repositories. Access is limited by the token and any organization SSO restrictions.
- Private repositories are attempted too, but open-source ecosystem signals may be incomplete. This is a criticality metric, not a security rating.
- Unavailable scores are shown explicitly; previous scores are never presented as fresh results. Raw results are in [scores.json](scores.json).
- `TRACKER_GITHUB_TOKEN` is an Actions secret initialized from the existing GitHub CLI login. Replace it if that credential expires or is revoked: `gh auth token | gh secret set TRACKER_GITHUB_TOKEN`. A replacement token needs access to the repositories being tracked (`repo` and `read:org` for a classic token, plus organization SSO authorization where required).
- README commits use the repository’s built-in `GITHUB_TOKEN`, preventing recursive workflow runs. Push runs update the pushed branch; scheduled runs update the default branch.
- Local use: install `gh` and `criticality_score` v2.0.4, export `GH_TOKEN`, then run `python3 scripts/update_readme.py`. Run checks with `python3 -m unittest discover -s tests`.

</details>
