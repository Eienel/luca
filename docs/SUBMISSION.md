# Submission readiness

## Product artifacts complete

- [x] Public Apache-2.0 repository
- [x] Focused problem statement and setup instructions
- [x] No-paid-API deterministic demo
- [x] Official DataHub MCP transport and tool-schema contract tests
- [x] Real SQL break/repair execution
- [x] Review package generation
- [x] Real Git branch and commit proof
- [x] Local and MCP document write-back paths
- [x] Judge-readable sample output
- [x] GitHub Actions verification

## External gates before Devpost submission

- [x] Run MCP mode against DataHub OSS Quickstart on a 16 GB GitHub runner using
      `scripts/verify_live_datahub.py`.
- [x] Capture the successful `live-datahub` proof artifact and workflow URL.
- [x] Capture a real cross-tool column example from DataHub's official sample:
      `logging_events.event_data` to `fct_users_created.user_name`.
- [x] Generate a 1:51 English narrated demo at `demo/changesafe-demo.mp4`.
- [ ] Optionally replace the narrated draft with a team-led live walkthrough.
- [ ] Add the video URL and final screenshots to the Devpost project.
- [x] Select **Metadata-Aware Development** as the primary category; use broader
      Luca tools only as the roadmap.
- [x] Re-check the repository without GitHub credentials; the public page
      returned HTTP 200 on August 7, 2026.
- [x] Confirm GitHub's unauthenticated license endpoint detects Apache-2.0.
- [ ] Submit before the deadline and do not change judged materials afterward.

The unchecked items require external credentials, a larger deployment target,
or a human video/submission action. They are not disguised as completed tests.
