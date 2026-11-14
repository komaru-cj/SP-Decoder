# fig9_12_duty_v3


This plan contains 40 controller runs.  Run `dry_run_campaign.ps1` first; it
generates control manifests without a USRP.  The real script pauses before every
run so the dual-channel receiver can be armed first.


Fig. 9/10 use fixed per-node duty cycles
0.0208333, 0.03125, 0.0416667.  For each run the
effective aggregate offered load is `G=N*d`; CONFIG v1 represents the requested
duty exactly through a traffic-profile load and a separate traffic-reference
population while the active mask selects the real nodes.  Every run commands
the node radios to 16 dBm.


For every Fig. 12 position, record the gateway antenna midpoint, both node
coordinates, antenna heights/orientations, measured bearing, tape-measured
distances, and a photograph.  Keep Node01 at 2 m and
place Node02 at separations
0.02, 0.05, 0.1, 0.2, 0.3 m on the
same nominal 0-degree ray.  Treat these defaults as a
site-layout template and regenerate the campaign if the room cannot support them.


Copying only control manifests is insufficient for PRR or throughput.  Transfer
all files listed in `required_transfer` in `campaign.json`.
