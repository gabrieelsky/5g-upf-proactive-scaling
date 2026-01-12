# Proactive 5G UPF Autoscaler

## Project Overview
This project implements a **proactive autoscaling controller** for the User Plane Function (UPF) of an OpenAirInterface (OAI) 5G Core network. Unlike traditional reactive scalers that respond to threshold breaches (often resulting in latency spikes), this system utilizes a **Long Short-Term Memory (LSTM)** neural network to forecast traffic load and scale resources *before* congestion occurs.

The system is designed to operate within a Kubernetes environment, orchestrating Helm charts to dynamically scale UPF instances based on a one-step-ahead prediction strategy.

### Key Objectives
* **Proactive Control:** Anticipate traffic surges to mitigate Kubernetes pod startup latency.
* **Safety Assurance:** Prevent physical saturation (15 Mbps) by triggering scaling actions at a safe margin (12 Mbps).
* **Determinism:** Ensure repeatable experiments using trace-driven simulation and blocking I/O.

---

## System Architecture

The solution is composed of three main Python modules operating in a closed control loop:

1.  **Orchestrator (`autoscaler.py`):** The main control loop that reads the traffic trace, queries the predictive engine, and executes Helm commands.
2.  **Predictive Engine (`predict.py`):** A wrapper around the LSTM model that handles input validation, caching, and inference.
3.  **Model Trainer (`train.py`):** An offline utility to train the LSTM network on historical throughput data.

### Control Logic
The autoscaler enforces the following logic at every simulation step ($t=1s$):

* **Physical Constraint:** The single UPF capacity is **15.0 Mbps**.
* **Proactive Trigger:** If predicted throughput $\hat{y}_{t+1} > \mathbf{12.0 \text{ Mbps}}$, Scale-Out is triggered.
* **Reasoning:** The 3 Mbps buffer compensates for model inertia and the actuation latency (container pull, scheduling, and boot time) required to bring the second UPF online.

---

## Project Structure

```text
.
├── ml/
│   ├── artifacts/          # Model binaries and metadata
│   │   ├── lstm_model.keras
│   │   ├── meta.json
│   │   └── scaler.pkl
│   ├── autoscaler.py       # Main proactive control loop
│   ├── dataset.csv         # Global training dataset
│   ├── predict.py          # Inference engine with Singleton caching
│   ├── test_dataset.csv    # Scenario-based evaluation trace
│   └── train.py            # Offline LSTM training script
├── oai-5g-core/            # Helm charts for 5G Core NFs
├── get_helm.sh             # Helm installation script
├── init.sh                 # Environment initialization
├── oai-ueransim.yaml       # Static UE generator manifest
├── oai-ueransim2.yaml      # On-demand UE generator manifest
└── README.md               # Project documentation
