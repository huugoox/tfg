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
