# CSV-driven single-panel redraws

Run the following from this directory:

```bash
MPLCONFIGDIR=/tmp/ok_python_mpl python3 prepare_data.py
MPLCONFIGDIR=/tmp/ok_python_mpl python3 render_all.py
```

`data/` contains the editable CSV input for every panel. `panels/` contains one
Python entry point per output image. For example, after editing
`data/fig13_prr.csv`, run `python3 panels/fig13_sf8_prr.py` to redraw only that
one 4:3 panel. The corresponding rendering logic is named by the same panel in
`plots.py`; shared 4:3/grid/save rules are in `common.py`.

All renderers deliberately omit figure titles and `(a)/(b)` labels. Dashed gray
grids are placed behind data; bars use horizontal grids only. The four
`fig_air_within_*` renderers explicitly retain top and right outer spines.

`panels/fig_lora_css_demodulation.py` renders the separate LoRa mechanism
figure.  Its two CSV files (`fig_lora_css_demodulation_settings.csv` and
`fig_lora_css_demodulation_parameters.csv`) control the physical simulation:
SF, noise, symbol-boundary offsets, symbols, CFOs, complex phases, and gains.
The received time-frequency energy, dechirped energy, and FFT spectrum are
all recalculated from those values on every render.
