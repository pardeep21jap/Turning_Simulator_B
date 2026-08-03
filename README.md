# CNC Lathe Simulator — PyQt6 Desktop App

A VS Code-ready educational 2D CNC lathe simulator for FANUC-style programs.

## Included

- Editable G-code with active-block highlighting
- Animated tool motion and approximate material removal
- G00/G01/G02/G03 motion, X/Z/U/W coordinates, F and S words
- Recognition/expansion for common G70, G71 and G72 two-block cycles
- Basic G76 two-block threading pass visualization
- Facing, turning, grooving and threading sample programs
- Dimensioned drawing view
- Syntax, travel, spindle, feed and possible-collision alarms
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
- **Stock Ø / Length** sets the starting cylindrical material size.
- **Cycle Start** starts or resumes animated playback.
- **Pause** stops playback at the current interpolated position.
- **Single Block** completes one generated motion segment.
- **Machine / Drawing** changes the center visualization.
- **Speed** controls animation speed only, not programmed feed.

## Supported syntax and limits

The parser accepts common FANUC-style words such as `G`, `M`, `X`, `Z`, `U`,
`W`, `R`, `P`, `Q`, `F`, `S`, `T` and `N`. Diameter programming is assumed for
X. Parenthesized and semicolon comments are supported.

G71/G72 support is intentionally educational: the simulator finds the P/Q
profile blocks and replays their motion as a roughing visualization, followed
by a finish allowance. G70 replays its P/Q contour. G76 creates representative
threading passes. Controller-specific parameters and every FANUC option are not
implemented.

## Project layout

```text
main.py                 Application entry point
cnc_sim/parser.py       FANUC-style tokenizer/parser and cycle expansion
cnc_sim/simulation.py   Playback state and material-removal model
cnc_sim/canvas.py       Machine and drawing renderers
cnc_sim/main_window.py  PyQt6 user interface
cnc_sim/examples.py     Included training programs
tests/test_parser.py    Parser/simulation smoke tests
```

## Run tests

```powershell
py -m unittest discover -s tests -v
```
