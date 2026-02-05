************************************************************************************************
    Automated R-script to transform InstaScope sensor records into bioaerosol concentrations
************************************************************************************************
This automated package is for dashboard display.
Date: 2 February, 2026
----------------------
This package includes:
----------------------
1. [bioaerosol_script.R]: A R-script is responsible for converting InstaScope FT(Forced Trigger, baseline)/AQ (Acquisition, data) files into human-understandable concentration values.
2. [Automate.py]: A Python script is responsible for running R-script automatically and returns processed bioaerosol concentrations.
3. [Constants.py]: A Python script containing useful parameters to be imported into Automate.py.
    MEANINGS OF PARAMS :
	INPUT_DIR: Input file directory containing FT/AQ files.
	TEMP_OUTPUT_DIR: Temporary output file directory for bioaerosol_script.R.
	AUTOMATION_FILE : Output filename of automation result.
	RSCRIPT_PATH: Path of Rscript. Adjust the path according to the actual situation.
	TIME_INT: Display timeframe (Default: "mins", ["secs", "mins", "hours", "days"]
	FILENAME_PREFIX: Output filename prefix for bioaerosol_script.R.
	WAIT_TIME: Sleep time after each R-automation.

--------------------
To use this package:
--------------------
1. Put the three items above into a single directory (e.g. AutoR/).
2. Set up a sub-directory (InstaScope_data/) for InstaScope files.
3. Assign params in Constants.py to fit your needs.
4. Connect your computer to InstaScope with LAN.
5. Set up InstaScope program and output directory as InstaScope_data/ under your computer.
6. Start running InstaScope.
7. Subsequently, start Automate.py for getting processed bioaerosol concentrations.
8. Set up your dashboard to read the automation output file.

--------------------
For local development:
--------------------
Before running the application, ensure you have Python installed. It is recommended to use a virtual environment to manage dependencies.

Install the required libraries (`pandas`, `streamlit`, and `plotly`) using pip: 
pip install pandas streamlit plotly

To run the full application locally, you will need to open two separate terminal windows to handle the backend processing and the frontend display simultaneously.

Terminal 1: Backend Data Processing
In the first terminal, run the automation script:
python Automate.py

Terminal 2: Frontend Dashboard
In the second terminal, launch the Streamlit dashboard to visualize the data:
streamlit run Streamlit_dashboard.py
