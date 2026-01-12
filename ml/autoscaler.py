import csv
import os
import sys
import subprocess
import time

# Ensure relative paths (artifacts/, test_dataset.csv, etc.) resolve correctly
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
os.chdir(SCRIPT_DIR)

from predict import predict_next_throughput

CSV_PATH = os.path.join(SCRIPT_DIR, "test_dataset.csv")

# We set the trigger THRESHOLD lower (Safety Margin) to compensate for model lag and ensure proactive scaling before saturation.
THRESHOLD = 12.0
LOOKBACK = 20
IPERF_DURATION = 1  # Duration in seconds for each simulation step

# Configuration for Pod Labels
LABEL_UPF1 = "app.kubernetes.io/instance=upf" 
LABEL_UPF2 = "app.kubernetes.io/instance=oai-upf2"
LABEL_UE1 = "app=ueransim" 
LABEL_UE2 = "app=ueransim2"

# UPF IPs
UPF1_IP = "12.1.1.1"
UPF2_IP = "12.1.1.11"


def load_throughput_series(csv_path: str):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"{csv_path} not found")

    values = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "throughput_mbps" not in reader.fieldnames:
            raise ValueError("CSV must include a 'throughput_mbps' column")
        for row in reader:
            values.append(float(row["throughput_mbps"]))
    return values


def get_pod_name(label_selector):
    """
    Finds the pod name dynamically using its label.
    """
    for i in range(10):
        try:
            cmd = f'kubectl get pods -l {label_selector} -o jsonpath="{{.items[0].metadata.name}}"'
            pod_name = subprocess.check_output(cmd, shell=True).decode().strip()
            if pod_name:
                return pod_name
        except Exception as e:
            pass
        time.sleep(1)
        
    print(f"[ERROR] Could not find pod: {label_selector}")
    return None

def scale_up():
    print("[SCALING] Deploying UPF2 and UE2...")
    os.system("helm upgrade --install oai-upf2 ../oai-5g-core/oai-upf2 > /dev/null 2>&1") 
    os.system("kubectl apply -f ../oai-ueransim2.yaml > /dev/null 2>&1")
    
    # Wait for pods to be ready
    print("[WAITING] Waiting for UPF2/UE2 pods to be ready...")
    # Actually waiting for UE2 only since it depends on UPF2
    os.system(f"kubectl wait --for=condition=ready pod -l {LABEL_UE2} --timeout=120s")
    print("[SCALING] Scale Out Complete.")

def scale_down():
    print("[SCALING] Removing UPF2 and UE2...")
    os.system("helm uninstall oai-upf2 > /dev/null 2>&1")
    os.system("kubectl delete -f ../oai-ueransim2.yaml > /dev/null 2>&1")
    print("[SCALING] Scale In Complete.")

def run_traffic_blocking(target_load, is_scaled_up):
    """
    Runs blocking iperf commands to simulate traffic for the duration of the step.
    """
    ue1_pod = get_pod_name(LABEL_UE1)
    if not ue1_pod:
        print("[ERROR] UE1 Pod not found. Skipping traffic generation.")
        return

    if target_load <= 0:
        target_load = 0.1  # Minimum load to avoid iperf errors

    processes = []
        
    if not is_scaled_up:
        print(f"[TRAFFIC] Generating {target_load:.2f} Mbps from UE1 -> UPF1")
        cmd = [
            "kubectl", "exec", ue1_pod, "--", 
            "iperf", "-c", UPF1_IP, "-u", "-b", f"{target_load}M", "-t", str(IPERF_DURATION)
        ]
        # blocking execution of command inside pod, but async in python initially
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(p)
        
    else:
        ue2_pod = get_pod_name(LABEL_UE2)
        half_load = target_load / 2
        print(f"[TRAFFIC] Generating {target_load:.2f} Mbps SPLIT ({half_load:.2f} each) on UE1 & UE2")
        
        # UE1 -> UPF1
        cmd1 = [
            "kubectl", "exec", ue1_pod, "--", 
            "iperf", "-c", UPF1_IP, "-u", "-b", f"{half_load}M", "-t", str(IPERF_DURATION)
        ]
        processes.append(subprocess.Popen(cmd1, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        
        # UE2 -> UPF2
        if ue2_pod:
            cmd2 = [
                "kubectl", "exec", ue2_pod, "--", 
                "iperf", "-c", UPF2_IP, "-u", "-b", f"{half_load}M", "-t", str(IPERF_DURATION)
            ]
            processes.append(subprocess.Popen(cmd2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        else:
            print("[WARN] UE2 not found despite Scale Out state.")

    # Block until traffic finishes
    for p in processes:
        p.wait()

def main():
    print("--- 5G SIMULATION & PROACTIVE AUTOSCALER ---")

    try:
        series = load_throughput_series(CSV_PATH)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        sys.exit(1)

    total_rows = len(series)
    if total_rows < LOOKBACK + 1:
        print(f"Error: need at least {LOOKBACK + 1} rows, got {total_rows}.")
        sys.exit(1)

    print(f"Loaded {total_rows} rows.")

    # Initialize Buffer from real history
    buffer = list(series[:LOOKBACK])
    
    is_scaled_up = False

    for i in range(LOOKBACK, total_rows):
        actual_target = float(series[i])
        prediction = predict_next_throughput(buffer)

        print(
            f"\n[STEP {i}] Target: {actual_target:.2f} Mbps | "
            f"Pred(next): {prediction:.2f} Mbps | Scaled: {is_scaled_up}"
        )

        if prediction > THRESHOLD:
            if not is_scaled_up:
                scale_up()
                is_scaled_up = True
        else:
            if is_scaled_up and prediction <= THRESHOLD:
                scale_down()
                is_scaled_up = False

        run_traffic_blocking(actual_target, is_scaled_up)

        buffer.pop(0)
        buffer.append(actual_target)

if __name__ == "__main__":
    main()
