# fig9_10_fig12_d025_d05_d07_r1


This plan contains 15 controller runs.  Run `dry_run_campaign.ps1` first; it
generates control manifests without a USRP.  The real script pauses before every
run so the dual-channel receiver can be armed first.


Fig. 9/10 use per-node duty cycles
0.25, 0.5.  Traffic semantics: fixed per-node duty cycle; effective aggregate offered load is N*d; the firmware
profile table contains every required G and CONFIG `numActiveNodes` always equals
the active-mask population.  Every run commands
the node radios to 16 dBm.


Fig. 12 uses per-node duty cycle d=0.7 (aggregate G=1.4).


For every Fig. 12 position, record the gateway antenna midpoint, both node
coordinates, antenna heights/orientations, measured bearing, tape-measured
distances, and a photograph.  Keep Node01 at 2 m and
place Node02 at separations
0.02, 0.05, 0.1, 0.2, 0.3 m on the
same nominal 0-degree ray.  Treat these defaults as a
site-layout template and regenerate the campaign if the room cannot support them.


Copying only control manifests is insufficient for PRR or throughput.  Transfer
all files listed in `required_transfer` in `campaign.json`.
