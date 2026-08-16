# CEC-over-HTTP — archived

This repository has been superseded by
**[home-assistant-cec-control](https://github.com/Khronos31/home-assistant-cec-control)**,
and is kept only so that existing links and clones still lead somewhere.

It was a small daemon that exposed a Raspberry Pi's CEC adapter over HTTP, meant
to be called from Home Assistant with `rest_command`. Its companion,
[cec-bridge](https://github.com/Khronos31/cec-bridge), did the same job as a
Home Assistant add-on. Both saw brief experimental use; neither reached daily
service.

The successor folds both into one Home Assistant integration with a UI config
flow, and keeps an HTTP daemon as one of two interchangeable transports — for
when the adapter is attached to some other machine. What was measured about
libcec along the way is written down in the successor's
[`docs/cec-findings.md`](https://github.com/Khronos31/home-assistant-cec-control/blob/main/docs/cec-findings.md),
including a correction to the code here: the Pulse-Eight adapter takes CEC
logical address 1, not 4.

One thing worth naming rather than quietly deleting: the API this repository's
README used to describe did not match its code. `GET /power_on` and
`GET /standby` never existed. That is precisely why the successor carries a test
comparing its documented endpoints against the ones it actually serves.

Archived and read-only.
