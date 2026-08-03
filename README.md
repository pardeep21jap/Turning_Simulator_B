# CNC Lathe Simulator — PyQt6 Desktop App

A VS Code-ready educational 2D CNC lathe simulator for FANUC-style programs.

## Included

- Editable G-code with active-block and cycle-block highlighting
- Animated tool motion over a real per-column stock removal model
- G00/G01/G02/G03 motion, G28 home, G90/G91, F/S words, G96/G97 CSS-to-RPM conversion
- Real multi-pass roughing simulation for G71/G73, plus G70 finishing and G74 peck cycles
- Per-tool-station icons (turning/drill/boring/grooving) and a DRO readout row
- Facing, turning, grooving and threading sample programs
- Dimensioned drawing view generated from the finished contour
- Compile messages (errors/notes) per source line
- Playback speed, pause, reset and single-block controls
- Responsive splitter layout suitable for normal desktop screens

This is a training visualization tool. It must not be used to validate a
production program or replace machine/controller simulation and prove-out.

## Run in VS Code (Windows)

1. Extract the ZIP and open the extracted folder in VS Code.
2. Install Python 3.11 or newer and the Microsoft Python extension.
3. Open **Terminal > New Terminal** and run:

```powershell
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py main.py
```

For the easiest Windows setup, double-click `run_simulator.bat`. It creates the
virtual environment, installs PyQt6 and starts the app. In VS Code, you can also
select **Run and Debug > Run CNC Lathe Simulator** after the environment exists.

If PowerShell blocks activation, use Command Prompt in VS Code:

```bat
py -m venv .venv
.venv\Scripts\activate.bat
py -m pip install -r requirements.txt
py main.py
```

## Controls

- **Parse / Reset** parses the editor and returns the simulator to the start.
- **Stock Ø / Length** shows the cylindrical material size; it is auto-detected from the program's cutting moves on every parse (no manual selection needed).
- **Cycle Start** starts or resumes animated playback.
- **Pause** stops playback at the current interpolated position.
- **Single Block** completes one generated motion segment.
- **Machine / Drawing** changes the center visualization.
- **Speed** controls animation speed only, not programmed feed.

## Supported syntax and limits

The compiler (`cnc_sim/lathe_core.py`) accepts common FANUC-style words such as
`G`, `M`, `X`, `Z`, `R`, `I`, `K`, `P`, `Q`, `F`, `S`, `T` and `N`. Diameter
programming is assumed for X; arcs may use `R` or `I`/`K`. Parenthesized and
semicolon comments are supported.

G71/G73 are expanded into real multi-pass roughing followed by a G70 finishing
pass. G74 expands into a peck cycle. G28 approximates a return-to-reference
rapid. **G72 (face-first roughing) and G76 (threading) are not specially
expanded** — a program using them will still compile, but those cycles run as
plain sequential motion rather than a proper multi-pass simulation. There is
also no `U`/`W` incremental-axis shorthand outside of cycle parameters; use
`G91` for incremental positioning instead. Controller-specific parameters and
every FANUC option are not implemented.

## Project layout

```text
main.py                 Application entry point
cnc_sim/lathe_core.py   Toolkit-agnostic G-code compiler and stock model
cnc_sim/parser.py       Adapter from the app's Program shape to lathe_core
cnc_sim/models.py       Program dataclass bundling a compiled result + stock
cnc_sim/simulation.py   Playback engine driving lathe_core segments
cnc_sim/dimensioning.py Diameter/length/radius dimensions from the finished contour
cnc_sim/canvas.py       Machine and drawing renderers
cnc_sim/main_window.py  PyQt6 user interface
cnc_sim/examples.py     Included training programs
tests/test_parser.py    Compiler/simulation smoke tests
```

## Run tests

```powershell
py -m unittest discover -s tests -v
```
