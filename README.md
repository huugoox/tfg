# Data-Efficient Electricity Price Forecasting Using Event-Based Market Representations

This repository contains the implementation of the Final Degree Thesis focused on one-hour-ahead electricity price forecasting using different data representations of Nord Pool day-ahead electricity market information.

The main objective of the project is not to propose a new forecasting model, but to analyse whether the same electricity market information can be organised in different ways and still preserve useful predictive information while reducing the amount of raw data used for model training.

## Project overview

The project compares three training data representations:

1. **Full dataset**  
   Uses the complete set of available raw market observations.

2. **rbaTheta event representation**  
   Uses automatically detected event timestamps obtained from the rbaTheta event detection method.

3. **Own market event representation**  
   Uses market-informed events defined from prices, volumes, flows and capacities. These events are calibrated on historical data and then applied to the training period using frozen thresholds.

The forecasting task is one-hour-ahead electricity price prediction.

## Data

The experiments use Nord Pool day-ahead market data, including:

- Electricity prices
- Buy and sell volumes
- Cross-border flows
- Transmission capacities

The data are stored in a SQLite database and processed into training and testing datasets.

## Final experiment

The final experiment focuses on two Norwegian bidding zones:

- **NO2**: high-volatility bidding zone
- **NO4**: low-volatility bidding zone

The own event representation is evaluated under three calibration periods:

- 2020
- 2020--2021
- 2020--2022

The models are trained using data from 2023 and evaluated on five independent test weeks from 2024.

## Forecasting models

The following forecasting models are evaluated:

- ARIMA
- Linear Regression
- Decision Tree
- Random Forest
- XGBoost

The main evaluation metric is RMSE.

## Repository structure

```text
tfg/
├── NordPoool/
│   └── data/
├── src/
│   └── experiments/
├── results/
│   └── final_event_training_experiment/
├── README.md
├── requirements.txt
└── thesis_database.db / data files if included
```

The most relevant parts of the repository are:

- `src/`: source code used for data preparation, event extraction and model evaluation.
- `NordPoool/data/`: database and market data files used in the experiments, if included.
- `results/`: final result tables, generated figures and experiment outputs.
- `requirements.txt`: Python dependencies required to execute the project.
- `README.md`: project documentation and execution instructions.

## Installation

Create a Python virtual environment:

```bash
python -m venv .venv
```

Activate the environment on Windows:

```bash
.venv\Scripts\activate
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Execution

The final experiment can be executed from the corresponding experiment notebook or from the Python scripts inside the `src/experiments/` directory.

The main outputs are saved in:

```text
results/final_event_training_experiment/
```

The generated outputs include:

- Weekly RMSE result tables
- Average RMSE tables across the five test weeks
- Raw value usage tables
- Event category contribution tables
- RMSE versus raw values plots
- Model prediction files

## Reproducibility

The final version of the project is available in the `main` branch. The repository was organised to emulate a reproducible software project, including source code, data processing scripts, experiment outputs and documentation.

The final thesis version is tagged as release:

```text
v1.0.0
```

The computational environment used in the experiments is described in the thesis, including:

- Python version
- Main package versions
- Hardware specifications
- Database engine

## Notes

Some outputs may depend on the local availability of the Nord Pool SQLite database and rbaTheta event files. If these files are not included in the repository because of size or storage limitations, they should be placed in the paths specified in the experiment notebook before execution.

## Author

Hugo Fernández Sisquella  
Final Degree Thesis  
Bachelor's Degree in Computer Engineering
